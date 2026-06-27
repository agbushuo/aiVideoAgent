"""阶段调度器

将 stage_id 映射到具体的 pipeline 执行函数。
每个阶段独立执行，支持中间产物缓存和恢复。

阶段定义:
  transcribe → scene_detection → llm_annotation → scoring
  → filtering → duration_planning → final_review → clipping
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from src.web.api_schemas import StageResultResponse
from src.web.sse import broadcast_event

from src.utils.i18n import _ as i18n


# ===================================================================== #
# 阶段定义元数据
# ===================================================================== #

STAGE_DEFINITIONS = [
    {
        "stage_id": "transcribe",
        "label": "转录",
        "description": "Whisper 音频转录，生成字幕",
        "icon": "mic",
        "default_params": {"language": "zh"},
        "dependencies": [],
    },
    {
        "stage_id": "scene_detection",
        "label": "场景检测",
        "description": "基于字幕时间间隔检测场景边界",
        "icon": "scissors",
        "default_params": {"gap_threshold": 5.0, "min_scene_duration": 3.0, "max_scene_duration": 120.0},
        "dependencies": ["transcribe"],
    },
    {
        "stage_id": "llm_annotation",
        "label": "LLM 标注",
        "description": "AI 对每个场景进行类型识别、标签和评分",
        "icon": "brain",
        "default_params": {"user_prompt": None},
        "dependencies": ["scene_detection"],
    },
    {
        "stage_id": "scoring",
        "label": "评分引擎",
        "description": "根据预设权重计算多维综合评分",
        "icon": "star",
        "default_params": {"preset": "viral", "clip_mode": "viral"},
        "dependencies": ["llm_annotation"],
    },
    {
        "stage_id": "filtering",
        "label": "筛选引擎",
        "description": "Diversity 去重、数量控制、时长约束",
        "icon": "filter",
        "default_params": {"max_clips": 0, "min_gap": 120.0, "target_duration": 0.0},
        "dependencies": ["scoring"],
    },
    {
        "stage_id": "duration_planning",
        "label": "时长规划",
        "description": "按目标时长智能组合片段（可选）",
        "icon": "clock",
        "default_params": {"target_duration": 0.0},
        "dependencies": ["filtering"],
    },
    {
        "stage_id": "final_review",
        "label": "最终评审",
        "description": "LLM 二阶段精选和排序（可选）",
        "icon": "check",
        "default_params": {"num_to_select": None},
        "dependencies": ["duration_planning", "filtering"],
    },
    {
        "stage_id": "clipping",
        "label": "FFmpeg 剪辑",
        "description": "ffmpeg 裁剪片段和拼接精华视频",
        "icon": "film",
        "default_params": {"merge": True, "transition": 0.5},
        "dependencies": ["final_review", "filtering"],
    },
]

STAGE_MAP = {s["stage_id"]: s for s in STAGE_DEFINITIONS}


def get_pipeline_stages() -> list[dict[str, Any]]:
    """获取管线阶段定义（用于前端 DAG 构建）"""
    return STAGE_DEFINITIONS


# ===================================================================== #
# 阶段执行
# ===================================================================== #


async def execute_stage(
    stage_id: str,
    task: "PipelineTask",
    config: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, str]:
    """执行单个阶段，返回产物文件路径

    Args:
        stage_id: 阶段 ID
        task: 管线任务
        config: 全局配置 (config.yaml 内容)
        params: 阶段参数

    Returns:
        产物文件路径字典 {"key": "/path/to/file"}
    """
    executor = STAGE_EXECUTORS.get(stage_id)
    if not executor:
        raise ValueError(i18n("stage.unknown", stage_id=stage_id))

    # 在后台线程执行（避免阻塞事件循环）
    import asyncio
    loop = asyncio.get_event_loop()

    artifacts = await loop.run_in_executor(
        None,
        lambda: executor(stage_id, task, config, params),
    )
    return artifacts or {}


def _execute_transcribe(
    stage_id: str,
    task: "PipelineTask",
    config: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, str]:
    """转录阶段"""
    from src.transcribe.whisper_engine import WhisperEngine
    from src.transcribe.models import TranscriptResult

    whisper_cfg = config.get("whisper", {})
    seg_cfg = whisper_cfg.get("segment_transcribe", {})
    ffmpeg_cfg = config.get("ffmpeg", {})

    engine = WhisperEngine(
        model_path=whisper_cfg.get("model_path"),
        model_name=whisper_cfg.get("model_name", "large-v3"),
        device=whisper_cfg.get("device", "auto"),
        fp16=whisper_cfg.get("fp16", True),
        chunk_duration=seg_cfg.get("chunk_duration", 900.0),
        overlap=seg_cfg.get("overlap", 10.0),
        segment_threshold_minutes=seg_cfg.get("threshold_minutes", 30.0),
        similarity_threshold=seg_cfg.get("similarity_threshold", 0.8),
        normalize_loudness=seg_cfg.get("normalize_loudness", False),
        ffmpeg_path=ffmpeg_cfg.get("path", "ffmpeg"),
        ffprobe_path=ffmpeg_cfg.get("probe_path", "ffprobe"),
        beam_size=seg_cfg.get("beam_size", 5),
        temperature_fallback=seg_cfg.get("temperature_fallback", True),
    )

    transcript = engine.transcribe(task.video_path, params.get("language", task.language))
    engine.unload()

    # 保存转录结果到任务
    task.transcript = transcript

    # 导出文件
    output_dir = Path(task.output_dir) / Path(task.video_path).stem
    subtitles_dir = output_dir / "subtitles"
    subtitles_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(task.video_path).stem
    srt_file = subtitles_dir / f"{stem}.srt"
    json_file = subtitles_dir / f"{stem}.json"

    transcript.export_srt(srt_file)
    transcript.export_json(json_file)

    task.output_files["srt"] = str(srt_file)
    task.output_files["transcript_json"] = str(json_file)

    return {
        "transcript_json": str(json_file),
        "srt": str(srt_file),
        "segment_count": str(len(transcript.segments)),
    }


def _execute_scene_detection(
    stage_id: str,
    task: "PipelineTask",
    config: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, str]:
    """场景检测阶段"""
    from src.clip_engine.scene_detector import WhisperSegmentDetector

    if not task.transcript:
        raise ValueError(i18n("scene.missingTranscript"))

    detector = WhisperSegmentDetector(
        gap_threshold=params.get("gap_threshold", 5.0),
        min_scene_duration=params.get("min_scene_duration", 3.0),
        max_scene_duration=params.get("max_scene_duration", 120.0),
    )
    scenes = detector.detect_scenes(task.transcript.segments)

    # 缓存场景数据
    task._scenes = scenes

    # 保存到文件
    artifacts_dir = _get_artifacts_dir(task)
    scenes_file = artifacts_dir / "scenes.json"
    _save_artifact(scenes_file, [s.to_dict() for s in scenes])

    return {"scenes_json": str(scenes_file), "scene_count": str(len(scenes))}


def _execute_llm_annotation(
    stage_id: str,
    task: "PipelineTask",
    config: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, str]:
    """LLM 标注阶段"""
    from src.analyze.llm_analyzer import LLMAnalyzer

    scenes = task._scenes
    if not scenes:
        raise ValueError(i18n("scene.missingScenes"))

    llm_cfg = config.get("llm", {})
    analyzer = LLMAnalyzer(
        provider=llm_cfg.get("provider", "llama_cpp"),
        model=llm_cfg.get("model", "Qwen3.6-27B-Q4_K_M.gguf"),
        endpoint=llm_cfg.get("endpoint", "http://localhost:8080/v1"),
        api_key=llm_cfg.get("api_key", ""),
        temperature=llm_cfg.get("temperature", 0.3),
        max_tokens=llm_cfg.get("max_tokens", 16384),
        timeout=llm_cfg.get("timeout", 600),
        context_size=llm_cfg.get("context_size", 131072),
    )

    scenes = analyzer.analyze_scenes(scenes, user_prompt=params.get("user_prompt"))
    task._scenes = scenes

    # 保存
    artifacts_dir = _get_artifacts_dir(task)
    scenes_file = artifacts_dir / "scenes_annotated.json"
    _save_artifact(scenes_file, [s.to_dict() for s in scenes])

    return {"annotated_scenes_json": str(scenes_file)}


def _execute_scoring(
    stage_id: str,
    task: "PipelineTask",
    config: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, str]:
    """评分引擎阶段"""
    from src.clip_engine.scorer import ScoreEngine

    scenes = task._scenes
    if not scenes:
        raise ValueError(i18n("scene.missingAnnotation"))

    scorer = ScoreEngine(
        preset=params.get("preset", "viral"),
        clip_mode=params.get("clip_mode", "viral"),
    )
    candidates = scorer.compute(scenes)
    task._candidates = candidates

    # 保存
    artifacts_dir = _get_artifacts_dir(task)
    candidates_file = artifacts_dir / "candidates.json"
    _save_artifact(candidates_file, [c.to_dict() for c in candidates])

    return {"candidates_json": str(candidates_file), "candidate_count": str(len(candidates))}


def _execute_filtering(
    stage_id: str,
    task: "PipelineTask",
    config: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, str]:
    """筛选引擎阶段"""
    from src.clip_engine.filter import ClipFilter

    candidates = task._candidates
    if not candidates:
        raise ValueError(i18n("candidate.missingScoring"))

    clip_filter = ClipFilter(
        min_gap=params.get("min_gap", 120.0),
        max_clips=params.get("max_clips", 0),
        target_duration=params.get("target_duration", 0.0),
    )
    selected = clip_filter.filter(candidates)
    task._selected = selected

    # 保存
    artifacts_dir = _get_artifacts_dir(task)
    selected_file = artifacts_dir / "selected.json"
    _save_artifact(selected_file, [c.to_dict() for c in selected])

    return {"selected_json": str(selected_file), "selected_count": str(len(selected))}


def _execute_duration_planning(
    stage_id: str,
    task: "PipelineTask",
    config: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, str]:
    """时长规划阶段"""
    from src.clip_engine.planner import DurationPlanner

    selected = task._selected
    if not selected:
        raise ValueError(i18n("candidate.missingFiltering"))

    target_duration = params.get("target_duration", 0.0)
    if target_duration <= 0:
        return {}  # 跳过

    planner = DurationPlanner(
        target_duration=target_duration,
        min_gap=params.get("min_gap", 5.0),
    )
    plan_result = planner.plan(selected)
    task._selected = plan_result.selected

    # 保存
    artifacts_dir = _get_artifacts_dir(task)
    plan_file = artifacts_dir / "duration_plan.json"
    _save_artifact(plan_file, {
        "target_duration": target_duration,
        "total_duration": plan_result.total_duration,
        "score": plan_result.score,
        "selected": [c.to_dict() for c in plan_result.selected],
    })

    return {
        "duration_plan_json": str(plan_file),
        "planned_duration": str(plan_result.total_duration),
    }


def _execute_final_review(
    stage_id: str,
    task: "PipelineTask",
    config: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, str]:
    """最终评审阶段"""
    from src.analyze.llm_analyzer import LLMAnalyzer
    from src.clip_engine.reviewer import FinalReviewer

    selected = task._selected
    if not selected:
        raise ValueError(i18n("candidate.missingFiltering"))

    llm_cfg = config.get("llm", {})
    analyzer = LLMAnalyzer(
        provider=llm_cfg.get("provider", "llama_cpp"),
        model=llm_cfg.get("model", "Qwen3.6-27B-Q4_K_M.gguf"),
        endpoint=llm_cfg.get("endpoint", "http://localhost:8080/v1"),
        api_key=llm_cfg.get("api_key", ""),
        temperature=llm_cfg.get("temperature", 0.3),
        max_tokens=llm_cfg.get("max_tokens", 16384),
        timeout=llm_cfg.get("timeout", 600),
        context_size=llm_cfg.get("context_size", 131072),
    )

    reviewer = FinalReviewer(
        llm_analyzer=analyzer,
        num_to_select=params.get("num_to_select"),
        platform=task.preset,
        target_duration=task.target_duration,
        user_prompt=task.user_prompt,
    )
    review_result = reviewer.review(selected)
    task._selected = review_result.candidates

    # 保存
    artifacts_dir = _get_artifacts_dir(task)
    review_file = artifacts_dir / "final_review.json"
    _save_artifact(review_file, {
        "selected": [c.to_dict() for c in review_result.candidates],
        "overall_comment": review_result.overall_comment,
    })

    return {"final_review_json": str(review_file)}


def _execute_clipping(
    stage_id: str,
    task: "PipelineTask",
    config: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, str]:
    """FFmpeg 剪辑阶段"""
    from src.edit.clipper import Clipper

    selected = task._selected
    if not selected:
        raise ValueError(i18n("clip.noCandidates"))

    ffmpeg_cfg = config.get("ffmpeg", {})
    clipper = Clipper(
        ffmpeg_path=ffmpeg_cfg.get("path", "ffmpeg"),
        ffprobe_path=ffmpeg_cfg.get("probe_path", "ffprobe"),
    )

    output_dir = Path(task.output_dir) / Path(task.video_path).stem
    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(task.video_path).stem
    clip_paths = []

    for i, candidate in enumerate(selected):
        clip_file = clips_dir / f"{stem}_clip_{i+1:02d}.mp4"
        clip_result = clipper.extract_segment(
            video_path=task.video_path,
            start=candidate.start,
            end=candidate.end,
            output_path=clip_file,
        )
        if clip_result.success:
            clip_paths.append(clip_result.clip_path)

    artifacts = {}
    merged_path = None

    if params.get("merge", True) and len(clip_paths) > 1:
        merged_file = clips_dir / f"{stem}_highlight.mp4"
        merge_result = clipper.merge_clips(
            clip_paths=[str(p) for p in clip_paths],
            output_path=merged_file,
            transition=params.get("transition", 0.5),
        )
        merged_path = str(merge_result)
        artifacts["merged_video"] = merged_path
        task.output_files["merged_video"] = merged_path

    artifacts["clip_count"] = str(len(clip_paths))
    task.output_files["clips_dir"] = str(clips_dir)

    return artifacts


# ===================================================================== #
# 阶段执行器映射
# ===================================================================== #

STAGE_EXECUTORS: dict[str, callable] = {
    "transcribe": _execute_transcribe,
    "scene_detection": _execute_scene_detection,
    "llm_annotation": _execute_llm_annotation,
    "scoring": _execute_scoring,
    "filtering": _execute_filtering,
    "duration_planning": _execute_duration_planning,
    "final_review": _execute_final_review,
    "clipping": _execute_clipping,
}


# ===================================================================== #
# 辅助函数
# ===================================================================== #

def _get_artifacts_dir(task: "PipelineTask") -> Path:
    """获取任务中间产物目录"""
    output_dir = Path(task.output_dir) / Path(task.video_path).stem
    artifacts_dir = output_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def _save_artifact(path: Path, data: Any) -> None:
    """保存中间产物到 JSON 文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
