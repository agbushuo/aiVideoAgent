"""单视频全流程处理接口

封装 转录 → 分析 → (可选)剪辑 的完整管线，每次调用独立创建和释放资源。

用法:
    from src.pipeline import process_video, VideoProcessResult

    result = process_video(
        "input.mp4",
        output_dir="./outputs",
        language="zh",
        clip=True,
        min_score=0.7,
    )
    print(f"状态: {result.status}, 亮点数: {result.highlight_count}")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from src.transcribe.models import TranscriptResult
    from src.analyze.llm_analyzer import AnalysisReport

console = Console()


@dataclass
class VideoProcessResult:
    """单个视频处理结果"""
    # 输入
    video_path: Path
    # 状态
    status: str = ""  # "success" | "error" | "transcribed"
    error: str = ""
    # 转录
    segment_count: int = 0
    duration: float = 0.0
    transcript_path: Path | None = None  # 字幕 JSON 路径
    srt_path: Path | None = None         # SRT 字幕路径
    # 分析
    highlight_count: int = 0
    report_json_path: Path | None = None   # 报告 JSON 路径
    report_md_path: Path | None = None     # 报告 Markdown 路径
    # 剪辑
    clip_count: int = 0
    clips: list = field(default_factory=list)  # ClipResult 列表
    merged_clip_path: str = ""
    # 输出目录
    output_dir: Path | None = None
    # 耗时
    elapsed_seconds: float = 0.0


def process_video(
    video_path: str | Path,
    *,
    output_dir: str | Path = "outputs",
    language: str = "zh",
    clip: bool = False,
    min_score: float | None = None,
    merge_clips: bool = True,
    transition_duration: float = 0.5,
    # Whisper 配置（可选覆盖，不传则从 config.yaml 读取）
    whisper_model_path: str | None = None,
    whisper_model_name: str | None = None,
    whisper_device: str | None = None,
    whisper_fp16: bool | None = None,
    # LLM 配置（可选覆盖）
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_endpoint: str | None = None,
    llm_api_key: str | None = None,
    llm_temperature: float | None = None,
    llm_max_tokens: int | None = None,
    llm_timeout: int | None = None,
    llm_context_size: int | None = None,
    # ffmpeg 配置（可选覆盖）
    ffmpeg_path: str | None = None,
    ffprobe_path: str | None = None,
) -> VideoProcessResult:
    """处理单个视频的完整管线

    流程：
    1. 加载 Whisper 模型 → 转录视频 → 导出字幕 → 释放模型
    2. 调用 LLM 分析字幕 → 生成亮点报告
    3. (可选) 从报告提取亮点片段 → 拼接精华视频

    每次调用独立创建和释放所有资源，适合串行批处理。

    Args:
        video_path: 视频文件路径
        output_dir: 输出根目录（会在其下创建 {video_stem}/subtitles, reports, clips）
        language: 字幕语言代码
        clip: 是否执行剪辑
        min_score: 剪辑时最低评分阈值
        merge_clips: 是否拼接精华视频（clip=True 时生效）
        transition_duration: 转场时长（秒）
        whisper_*: Whisper 配置覆盖
        llm_*: LLM 配置覆盖
        ffmpeg_*: ffmpeg 配置覆盖

    Returns:
        VideoProcessResult: 包含处理状态和所有输出路径

    Example:
        >>> result = process_video("input.mp4", clip=True)
        >>> print(f"亮点数: {result.highlight_count}")
        >>> print(f"精华视频: {result.merged_clip_path}")
    """
    video_path = Path(video_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    # 每个视频独立的输出目录
    video_dir = output_root / video_path.stem
    video_dir.mkdir(parents=True, exist_ok=True)

    result = VideoProcessResult(
        video_path=video_path,
        output_dir=video_dir,
    )

    start_time = time.time()

    # ================================================================
    # Stage 1: 转录
    # ================================================================
    try:
        console.print(f"\n[bold blue]VideoAgent[/bold blue] - 处理视频")
        console.print(f"  文件: {video_path.name}")
        console.print(f"  语言: {language}")
        console.rule()

        console.print("[bold]Stage 1/3[/bold]: Whisper 转录...")

        # 加载配置
        config = _load_config()
        whisper_cfg = config.get("whisper", {})

        from src.transcribe.whisper_engine import WhisperEngine

        engine = WhisperEngine(
            model_path=whisper_model_path or whisper_cfg.get("model_path"),
            model_name=whisper_model_name or whisper_cfg.get("model_name", "large-v3"),
            device=whisper_device or whisper_cfg.get("device", "auto"),
            fp16=whisper_fp16 if whisper_fp16 is not None else whisper_cfg.get("fp16", True),
        )

        transcript: TranscriptResult = engine.transcribe(
            str(video_path), language=language
        )

        # 导出字幕
        from src.utils.io import export_srt, export_transcript_json

        subtitles_dir = video_dir / "subtitles"
        subtitles_dir.mkdir(parents=True, exist_ok=True)

        srt_file = subtitles_dir / f"{video_path.stem}.srt"
        json_file = subtitles_dir / f"{video_path.stem}.json"

        export_srt(transcript, srt_file)
        export_transcript_json(transcript, json_file)

        result.segment_count = len(transcript.segments)
        result.duration = transcript.duration
        result.transcript_path = json_file
        result.srt_path = srt_file

        console.print(f"[green]✓[/green] 转录完成 ({result.segment_count} 个片段)")
        console.rule()

        # 释放 Whisper 模型，回收 GPU 显存
        engine.unload()

    except Exception as e:
        result.status = "error"
        result.error = f"转录失败: {str(e)[:200]}"
        result.elapsed_seconds = time.time() - start_time
        console.print(f"[red]✗[/red] 转录失败: {result.error}")
        return result

    # ================================================================
    # Stage 2: 分析
    # ================================================================
    try:
        console.print("[bold]Stage 2/3[/bold]: LLM 分析...")

        llm_cfg = config.get("llm", {})

        from src.analyze.llm_analyzer import LLMAnalyzer

        analyzer = LLMAnalyzer(
            provider=llm_provider or llm_cfg.get("provider", "llama_cpp"),
            model=llm_model or llm_cfg.get("model", "Qwen3.6-27B-Q4_K_M.gguf"),
            endpoint=llm_endpoint or llm_cfg.get("endpoint", "http://localhost:8080/v1"),
            api_key=llm_api_key or llm_cfg.get("api_key", ""),
            temperature=llm_temperature if llm_temperature is not None else llm_cfg.get("temperature", 0.3),
            max_tokens=llm_max_tokens or llm_cfg.get("max_tokens", 16384),
            timeout=llm_timeout or llm_cfg.get("timeout", 600),
            context_size=llm_context_size or llm_cfg.get("context_size", 131072),
        )

        report: AnalysisReport = analyzer.analyze(transcript)
        report.video_path = str(video_path)

        # 导出报告
        from src.utils.io import export_analysis_json, export_markdown_report

        reports_dir = video_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        report_json = reports_dir / f"{video_path.stem}.json"
        report_md = reports_dir / f"{video_path.stem}.md"

        export_analysis_json(report, report_json)
        export_markdown_report(report, report_md)

        result.highlight_count = len(report.highlights)
        result.report_json_path = report_json
        result.report_md_path = report_md

        console.print(f"[green]✓[/green] 分析完成 ({result.highlight_count} 个亮点)")
        console.rule()

    except Exception as e:
        result.status = "error"
        result.error = f"分析失败: {str(e)[:200]}"
        result.elapsed_seconds = time.time() - start_time
        console.print(f"[red]✗[/red] 分析失败: {result.error}")
        return result

    # ================================================================
    # Stage 3: 剪辑 (可选)
    # ================================================================
    if clip:
        try:
            console.print("[bold]Stage 3/3[/bold]: ffmpeg 剪辑...")

            ffmpeg_cfg = config.get("ffmpeg", {})

            from src.edit.clipper import Clipper

            clipper = Clipper(
                ffmpeg_path=ffmpeg_path or ffmpeg_cfg.get("path", "ffmpeg"),
                ffprobe_path=ffprobe_path or ffmpeg_cfg.get("probe_path", "ffprobe"),
            )

            clip_result = clipper.clips_from_report(
                report_path=report_json,
                video_path=video_path,
                merge=merge_clips,
                merge_transition=transition_duration if merge_clips else None,
                filter_by_score=min_score,
            )

            result.clip_count = clip_result.success_count
            result.clips = clip_result.clips
            if clip_result.merged_path:
                result.merged_clip_path = str(clip_result.merged_path)

            console.print(f"[green]✓[/green] 剪辑完成 ({result.clip_count} 个片段)")
            if clip_result.errors:
                for err in clip_result.errors:
                    console.print(f"    [red]✗[/red] {err}")
            console.rule()

        except Exception as e:
            result.status = "error"
            result.error = f"剪辑失败: {str(e)[:200]}"
            result.elapsed_seconds = time.time() - start_time
            console.print(f"[red]✗[/red] 剪辑失败: {result.error}")
            return result

    # 完成
    result.status = "success"
    result.elapsed_seconds = time.time() - start_time

    console.print("[bold green]✓ 全流程完成![/bold green]")
    console.print(f"  输出目录: {video_dir}")
    console.print(f"  总耗时: {result.elapsed_seconds:.1f}秒")

    return result


def _load_config() -> dict:
    """加载配置文件"""
    import yaml

    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}
