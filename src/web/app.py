"""FastAPI 主应用

启动 Web 控制台服务，提供 REST API 和 SSE 事件流。
配合 Next.js 前端使用。
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# Windows GBK 编码兼容：强制 stdout/stderr 使用 UTF-8
if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import ValidationError

from src.utils.i18n import _ as i18n, resolve_locale as _resolve_locale
from src.web.api_schemas import (
    BulkSelectRequest,
    CandidateListResponse,
    ClipCandidateResponse,
    ClipModeInfo,
    ConfigResponse,
    DurationTemplate,
    PresetInfo,
    SceneListResponse,
    SceneResponse,
    SceneUpdateRequest,
    SegmentResponse,
    SegmentUpdateRequest,
    StageResultResponse,
    StageRunRequest,
    TaskCreateRequest,
    TaskDetailResponse,
    TaskResponse,
    TranscriptResponse,
    TranscriptUpdateRequest,
)
from src.web.stage_executor import (
    STAGE_MAP,
    get_pipeline_stages,
)
from src.web.task_manager import (
    PipelineStageConfig,
    PipelineTask,
    StageResult,
    TaskManager,
    TaskStatus,
)
from src.web.preset_manager import PresetManager
from src.web.sse import event_stream as sse_event_stream


# ===================================================================== #
# 应用生命周期
# ===================================================================== #


@asynccontextmanager
async def lifespan(application: FastAPI):
    """应用生命周期管理"""
    print(i18n("app.starting"))
    # 启动时恢复持久化的任务
    from src.web.task_manager import TaskManager
    TaskManager().load()
    yield
    # 关闭时保存任务状态
    TaskManager().save()
    print(i18n("app.closing"))


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""

    app_instance = FastAPI(
        title=i18n("app.title"),
        version="0.4.0",
        lifespan=lifespan,
    )

    # CORS
    app_instance.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API 路由
    setup_routes(app_instance)

    return app_instance


def _locale(request: Request) -> str:
    """从请求提取语言代码"""
    accept_lang = request.headers.get("accept-language", "")
    return _resolve_locale(accept_lang)


# ===================================================================== #
# API 路由
# ===================================================================== #


def setup_routes(app: FastAPI):

    # ----------------------------------------------------------------- #
    # 任务管理
    # ----------------------------------------------------------------- #

    @app.get("/api/tasks")
    async def list_tasks(
        status: str | None = Query(None, description="筛选状态"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        """列出所有任务"""
        manager = TaskManager()
        tasks = manager.list_tasks()

        if status:
            tasks = [t for t in tasks if t.status_str == status]

        tasks = tasks[offset : offset + limit]
        return [
            {
                "task_id": t.task_id,
                "status": t.status_str,
                "video_path": t.video_path,
                "progress": {
                    "step": t.progress.step,
                    "percent": t.progress.percent,
                },
            }
            for t in tasks
        ]

    @app.post("/api/tasks")
    async def create_task(request: Request, task_req: TaskCreateRequest):
        """创建新的管线任务并异步启动执行"""
        manager = TaskManager()

        # 构建阶段配置
        pipeline_stages = []
        if task_req.pipeline_config:
            for stage in task_req.pipeline_config.stages:
                pipeline_stages.append(
                    PipelineStageConfig(
                        stage_id=stage.stage_id,
                        enabled=stage.enabled,
                        params=stage.params,
                    )
                )

        task = manager.create_task(
            video_path=task_req.video_path,
            output_dir=task_req.output_dir,
            language=task_req.language,
            review_enabled=task_req.review_enabled,
            smart_clip=task_req.smart_clip,
            clip_mode=task_req.clip_mode,
            preset=task_req.preset,
            num_clips=task_req.num_clips,
            target_duration=task_req.target_duration,
            user_prompt=task_req.user_prompt,
            use_duration_planner=task_req.use_duration_planner,
            use_final_review=task_req.use_final_review,
            clip=task_req.smart_clip or True,
            min_score=task_req.min_score,
            merge_clips=task_req.merge_clips,
            transition_duration=task_req.transition_duration,
            pipeline_stages=pipeline_stages,
        )

        # 异步启动管线执行（如果请求中指定）
        if task_req.start:
            from src.web.pipeline_runner import run_pipeline
            asyncio.create_task(run_pipeline(task.task_id))

        locale = _locale(request)
        return {
            "task_id": task.task_id,
            "status": task.status_str,
            "message": i18n("task.created", locale=locale),
        }

    @app.get("/api/tasks/{task_id}")
    async def get_task(request: Request, task_id: str):
        """获取任务详情"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        result = {
            "task_id": task.task_id,
            "status": task.status_str,
            "video_path": task.video_path,
            "output_dir": task.output_dir,
            "progress": {
                "step": task.progress.step,
                "step_detail": task.progress.step_detail,
                "percent": task.progress.percent,
            },
            "stage_results": {
                sid: {
                    "status": sr.status,
                    "started_at": sr.started_at,
                    "completed_at": sr.completed_at,
                    "duration_seconds": sr.duration_seconds,
                    "output_artifacts": sr.output_artifacts,
                    "error": sr.error,
                }
                for sid, sr in task.stage_results.items()
            },
            "logs": [
                {
                    "timestamp": log.timestamp,
                    "level": log.level,
                    "message": log.message,
                    "step": log.step,
                }
                for log in task.logs
            ],
            "output_files": task.output_files,
        }

        if task.pipeline_stages:
            result["pipeline_config"] = {
                "stages": [
                    {
                        "stage_id": s.stage_id,
                        "enabled": s.enabled,
                        "params": s.params,
                    }
                    for s in task.pipeline_stages
                ]
            }

        return result

    @app.delete("/api/tasks/{task_id}")
    async def delete_task(request: Request, task_id: str):
        """删除任务"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        if task.status_str in ("transcribing", "analyzing", "scoring", "filtering", "clipping"):
            raise HTTPException(
                status_code=409,
                detail=i18n("task.deletingRunning", locale=_locale(request)),
            )

        manager.remove_task(task_id)
        manager.save()  # 持久化：任务删除
        locale = _locale(request)
        return {"status": "deleted", "message": i18n("task.deleted", locale=locale)}

    @app.delete("/api/tasks/bulk-delete")
    async def bulk_delete_tasks(
        request: Request,
        task_ids: list[str] = Query(..., description="要删除的任务 ID 列表"),
        delete_outputs: bool = Query(False, description="是否同时删除输出文件"),
    ):
        """批量删除任务（可选同时删除输出文件）"""
        manager = TaskManager()
        deleted = 0
        errors = []
        output_dirs_removed = 0

        for task_id in task_ids:
            task = manager.get_task(task_id)
            if not task:
                errors.append({"task_id": task_id, "error": "任务不存在"})
                continue

            running_statuses = ("transcribing", "analyzing", "scoring", "filtering", "clipping")
            if task.status_str in running_statuses:
                errors.append({"task_id": task_id, "error": "任务正在运行中，无法删除"})
                continue

            # 删除输出文件
            if delete_outputs:
                try:
                    output_dir = Path(task.output_dir) / Path(task.video_path).stem
                    if output_dir.exists():
                        import shutil
                        shutil.rmtree(output_dir)
                        output_dirs_removed += 1

                    # 也尝试删除 clips 目录（旧格式）
                    clips_dir = Path(task.output_dir) / "clips"
                    if clips_dir.exists():
                        # 只删除以视频名为前缀的文件
                        base = Path(task.video_path).stem[:20]  # 前 20 字符匹配
                        for f in clips_dir.glob(f"{base}*"):
                            f.unlink()
                except Exception as e:
                    errors.append({"task_id": task_id, "error": f"删除输出文件失败: {str(e)[:50]}"})

            manager.remove_task(task_id)
            deleted += 1

        manager.save()  # 持久化
        locale = _locale(request)
        return {
            "deleted": deleted,
            "output_dirs_removed": output_dirs_removed,
            "errors": errors,
            "message": i18n("task.deleted", locale=locale),
        }

    @app.post("/api/tasks/{task_id}/resume")
    async def resume_task(request: Request, task_id: str):
        """恢复任务（字幕审核通过后）"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))
        task.resume()
        locale = _locale(request)
        return {"status": "resumed", "message": i18n("task.resumed", locale=locale)}

    @app.post("/api/tasks/{task_id}/cancel")
    async def cancel_task(request: Request, task_id: str):
        """取消任务"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))
        task.cancel()
        manager.save()  # 持久化：任务取消
        locale = _locale(request)
        return {"status": "cancelled", "message": i18n("task.cancelled", locale=locale)}

    @app.post("/api/tasks/{task_id}/rerun-stage")
    async def rerun_stage(request: Request, task_id: str, stage_id: str = Query(...)):
        """重跑指定阶段"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        from src.main import load_config
        config = load_config()
        from src.web.settings_manager import merge_llm_into_config
        config = merge_llm_into_config(config)

        stage_config = task.get_stage_config(stage_id)
        params = stage_config.params if stage_config else {}

        result = await manager.run_stage(task, stage_id, config, params)
        return StageResultResponse(**{
            "stage_id": result.stage_id,
            "status": result.status,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "duration_seconds": result.duration_seconds,
            "output_artifacts": result.output_artifacts,
            "error": result.error,
        })

    # ----------------------------------------------------------------- #
    # 阶段级执行
    # ----------------------------------------------------------------- #

    @app.get("/api/tasks/{task_id}/stages")
    async def list_stages(request: Request, task_id: str):
        """列出任务的所有阶段状态"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        return [
            {
                "stage_id": sid,
                "status": sr.status,
                "started_at": sr.started_at,
                "completed_at": sr.completed_at,
                "duration_seconds": sr.duration_seconds,
                "output_artifacts": sr.output_artifacts,
                "error": sr.error,
            }
            for sid, sr in task.stage_results.items()
        ]

    @app.get("/api/tasks/{task_id}/stages/{stage_id}")
    async def get_stage(request: Request, task_id: str, stage_id: str):
        """获取阶段详情和产物"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        sr = task.stage_results.get(stage_id)
        if not sr:
            raise HTTPException(status_code=404, detail=i18n("stage.notFound", locale=_locale(request)))

        return StageResultResponse(**{
            "stage_id": sr.stage_id,
            "status": sr.status,
            "started_at": sr.started_at,
            "completed_at": sr.completed_at,
            "duration_seconds": sr.duration_seconds,
            "output_artifacts": sr.output_artifacts,
            "error": sr.error,
        })

    @app.post("/api/tasks/{task_id}/stages/{stage_id}/run")
    async def run_stage(request: Request, task_id: str, stage_id: str, request_body: StageRunRequest | None = None):
        """执行单个阶段"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        from src.main import load_config
        config = load_config()
        from src.web.settings_manager import merge_llm_into_config
        config = merge_llm_into_config(config)

        params = request_body.params if request_body else {}
        result = await manager.run_stage(task, stage_id, config, params)

        return StageResultResponse(**{
            "stage_id": result.stage_id,
            "status": result.status,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "duration_seconds": result.duration_seconds,
            "output_artifacts": result.output_artifacts,
            "error": result.error,
        })

    # ----------------------------------------------------------------- #
    # Scene 数据
    # ----------------------------------------------------------------- #

    @app.get("/api/tasks/{task_id}/scenes")
    async def list_scenes(
        request: Request,
        task_id: str,
        tag: str | None = Query(None),
        min_score: float | None = Query(None),
        search: str | None = Query(None),
        sort: str = "score",
        order: str = "desc",
    ):
        """列出所有检测到的场景"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        scenes = task._scenes if hasattr(task, "_scenes") else []
        if not scenes:
            # 尝试从文件加载
            artifacts_file = (
                Path(task.output_dir) / Path(task.video_path).stem
                / "artifacts" / "scenes_annotated.json"
            )
            if artifacts_file.exists():
                with open(artifacts_file, "r", encoding="utf-8") as f:
                    scene_data = json.load(f)
                from src.clip_engine.models import Scene
                scenes = [Scene.from_dict(s) for s in scene_data]

        # 筛选
        filtered = scenes
        if tag:
            filtered = [s for s in filtered if tag in s.tags]
        if min_score is not None:
            filtered = [
                s for s in filtered
                if any(v >= min_score for v in s.multi_score.values())
            ]
        if search:
            search_lower = search.lower()
            filtered = [
                s for s in filtered
                if search_lower in s.text.lower()
                or search_lower in s.summary.lower()
                or any(search_lower in t.lower() for t in s.tags)
            ]

        # 排序
        reverse = order == "desc"
        if sort == "score":
            filtered.sort(
                key=lambda s: max(s.multi_score.values()) if s.multi_score else 0,
                reverse=reverse,
            )
        elif sort == "start":
            filtered.sort(key=lambda s: s.start, reverse=reverse)

        return {
            "total": len(filtered),
            "scenes": [SceneResponse(**s.to_dict()).model_dump() for s in filtered],
        }

    @app.get("/api/tasks/{task_id}/scenes/{scene_id}")
    async def get_scene(request: Request, task_id: str, scene_id: int):
        """获取单个场景详情"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        scenes = task._scenes if hasattr(task, "_scenes") else []
        for s in scenes:
            if s.scene_id == scene_id:
                return SceneResponse(**s.to_dict()).model_dump()

        raise HTTPException(status_code=404, detail=i18n("scene.notFound", locale=_locale(request)))

    @app.put("/api/tasks/{task_id}/scenes/{scene_id}")
    async def update_scene(request: Request, task_id: str, scene_id: int, scene_req: SceneUpdateRequest):
        """手动修改场景标签/评分"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        scenes = task._scenes if hasattr(task, "_scenes") else []
        for s in scenes:
            if s.scene_id == scene_id:
                if scene_req.scene_type is not None:
                    s.scene_type = scene_req.scene_type
                if scene_req.tags is not None:
                    s.tags = scene_req.tags
                if scene_req.summary is not None:
                    s.summary = scene_req.summary
                if scene_req.multi_score is not None:
                    s.multi_score = scene_req.multi_score
                task._scenes = scenes
                return SceneResponse(**s.to_dict()).model_dump()

        raise HTTPException(status_code=404, detail=i18n("scene.notFound", locale=_locale(request)))

    # ----------------------------------------------------------------- #
    # ClipCandidate 数据
    # ----------------------------------------------------------------- #

    @app.get("/api/tasks/{task_id}/candidates")
    async def list_candidates(
        request: Request,
        task_id: str,
        sort: str = "score",
        order: str = "desc",
    ):
        """列出所有剪辑候选"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        candidates = task._candidates if hasattr(task, "_candidates") else []
        if not candidates:
            # 尝试从文件加载
            candidates_file = (
                Path(task.output_dir) / Path(task.video_path).stem
                / "artifacts" / "candidates.json"
            )
            if candidates_file.exists():
                with open(candidates_file, "r", encoding="utf-8") as f:
                    cand_data = json.load(f)
                from src.clip_engine.models import ClipCandidate
                candidates = [ClipCandidate.from_dict(c) for c in cand_data]

        reverse = order == "desc"
        if sort == "score":
            candidates.sort(key=lambda c: c.composite_score, reverse=reverse)
        elif sort == "start":
            candidates.sort(key=lambda c: c.start, reverse=reverse)

        return {
            "total": len(candidates),
            "candidates": [
                ClipCandidateResponse(
                    scene=SceneResponse(**c.scene.to_dict()),
                    composite_score=c.composite_score,
                    rank=c.rank,
                    selected=c.selected,
                ).model_dump()
                for c in candidates
            ],
        }

    @app.patch("/api/tasks/{task_id}/candidates/bulk-select")
    async def bulk_select_candidates(request: Request, task_id: str, bulk_req: BulkSelectRequest):
        """批量选中/取消候选"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        candidates = task._candidates if hasattr(task, "_candidates") else []
        updated = 0
        for c in candidates:
            if c.scene_id in bulk_req.scene_ids:
                c.selected = bulk_req.selected
                updated += 1
        task._candidates = candidates

        return {"updated": updated, "selected": bulk_req.selected}

    # ----------------------------------------------------------------- #
    # 字幕
    # ----------------------------------------------------------------- #

    @app.get("/api/tasks/{task_id}/transcript")
    async def get_transcript(request: Request, task_id: str):
        """获取转录结果"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        if not task.transcript:
            raise HTTPException(status_code=404, detail=i18n("transcript.notReady", locale=_locale(request)))

        return TranscriptResponse(
            language=task.transcript.language,
            duration=task.transcript.duration,
            segments=[
                SegmentResponse(
                    segment_id=i,
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                )
                for i, seg in enumerate(task.transcript.segments)
            ],
        ).model_dump()

    @app.put("/api/tasks/{task_id}/transcript")
    async def update_transcript(request: Request, task_id: str, transcript_req: TranscriptUpdateRequest):
        """保存修改后的字幕"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        from src.transcribe.models import Segment, TranscriptResult

        segments = [
            Segment(
                start=seg.start,
                end=seg.end,
                text=seg.text,
                words=[],
            )
            for seg in transcript_req.segments
        ]

        task.transcript = TranscriptResult(
            language=transcript_req.language if hasattr(transcript_req, "language") else task.language,
            segments=segments,
            text=" ".join(s.text for s in segments),
            duration=segments[-1].end if segments else 0,
        )

        # 保存文件
        if task.transcript:
            output_dir = Path(task.output_dir) / Path(task.video_path).stem
            subtitles_dir = output_dir / "subtitles"
            subtitles_dir.mkdir(parents=True, exist_ok=True)

            stem = Path(task.video_path).stem
            json_file = subtitles_dir / f"{stem}.json"
            srt_file = subtitles_dir / f"{stem}.srt"

            task.transcript.export_json(json_file)
            task.transcript.export_srt(srt_file)

        locale = _locale(request)
        return {"status": "saved", "segment_count": len(transcript_req.segments),
                "message": i18n("transcript.saved", locale=locale)}

    @app.put("/api/tasks/{task_id}/transcript/segments/{seg_index}")
    async def update_segment(request: Request, task_id: str, seg_index: int, segment_req: SegmentUpdateRequest):
        """更新单个字幕片段"""
        manager = TaskManager()
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=i18n("task.notFound", locale=_locale(request)))

        if not task.transcript or seg_index >= len(task.transcript.segments):
            raise HTTPException(status_code=404, detail=i18n("transcript.segmentNotFound", locale=_locale(request)))

        task.transcript.segments[seg_index].text = segment_req.text
        return {"status": "updated", "text": segment_req.text}

    # ----------------------------------------------------------------- #
    # 配置参考数据
    # ----------------------------------------------------------------- #

    @app.get("/api/config/presets")
    async def get_presets():
        """获取可用预设"""
        from src.clip_engine.scorer import _get_preset_table
        preset_table = _get_preset_table()
        return {
            "items": [
                {"name": name, "weights": weights}
                for name, weights in preset_table.items()
            ]
        }

    @app.get("/api/config/clip-modes")
    async def get_clip_modes():
        """获取可用剪辑模式"""
        from src.clip_engine.scorer import _get_clip_mode_table
        clip_mode_table = _get_clip_mode_table()
        return {
            "items": [
                {"name": name, "weights": weights}
                for name, weights in clip_mode_table.items()
            ]
        }

    @app.get("/api/config/scene-types")
    async def get_scene_types():
        """获取场景类型"""
        from src.clip_engine.models import SCENE_TYPES
        return {"items": SCENE_TYPES}

    @app.get("/api/config/score-dimensions")
    async def get_score_dimensions(request: Request):
        """获取评分维度"""
        from src.clip_engine.models import MULTI_SCORE_DIMENSIONS

        locale = _locale(request)
        descriptions: dict[str, dict[str, str]] = {
            "hook": {"zh": "开头吸引力", "en": "Hook Appeal"},
            "emotion": {"zh": "情绪强度", "en": "Emotion"},
            "comedy": {"zh": "搞笑程度", "en": "Comedy"},
            "action": {"zh": "动作/冲突", "en": "Action/Conflict"},
            "information": {"zh": "信息密度", "en": "Information"},
            "suspense": {"zh": "悬念感", "en": "Suspense"},
            "climax": {"zh": "高潮程度", "en": "Climax"},
            "viral": {"zh": "传播潜力", "en": "Viral Potential"},
        }
        return {
            "items": [
                {"name": d, "description": descriptions.get(d, {}).get(locale, d)}
                for d in MULTI_SCORE_DIMENSIONS
            ]
        }

    @app.get("/api/config/pipeline-stages")
    async def get_pipeline_stages_config(request: Request):
        """获取管线阶段定义（用于构建 DAG）"""
        from src.utils.i18n import get_stage_label, get_stage_description

        locale = _locale(request)
        stages = get_pipeline_stages()
        result = []
        for s in stages:
            result.append({
                **s,
                "label": get_stage_label(s["stage_id"], locale),
                "description": get_stage_description(s["stage_id"], locale),
            })
        return {"items": result}

    @app.get("/api/config/weights")
    async def get_weights():
        """获取完整权重配置"""
        from src.clip_engine.scorer import _get_weights
        return _get_weights()

    @app.get("/api/config/duration-templates")
    async def get_duration_templates():
        """获取时长模板"""
        from src.clip_engine.planner import DURATION_TEMPLATES
        templates = []
        for name, slots in DURATION_TEMPLATES.items():
            # 解析名称中的秒数
            dur_secs = int(name.replace("s", ""))
            num_clips = len(slots)
            templates.append(
                DurationTemplate(
                    name=name,
                    duration_seconds=dur_secs,
                    num_clips=num_clips,
                ).model_dump()
            )
        return {"items": templates}

    # ----------------------------------------------------------------- #
    # 文件操作
    # ----------------------------------------------------------------- #

    @app.get("/api/files/{file_path:path}")
    async def download_file(request: Request, file_path: str):
        """下载输出文件"""
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=i18n("file.notFound", locale=_locale(request)))
        return FileResponse(path, filename=path.name)

    @app.get("/api/files/{file_path:path}/thumbnail")
    async def get_thumbnail(
        request: Request,
        file_path: str,
        timestamp: float = Query(0, ge=0),
        width: int = Query(320, ge=100, le=1920),
    ):
        """生成视频缩略图"""
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=i18n("file.notFound", locale=_locale(request)))

        from src.main import load_config
        config = load_config()
        ffmpeg_path = config.get("ffmpeg", {}).get("path", "ffmpeg")

        import subprocess
        import tempfile
        output_dir = Path(tempfile.gettempdir()) / "videoagent_thumbnails"
        output_dir.mkdir(parents=True, exist_ok=True)

        thumb_file = output_dir / f"{path.stem}_{timestamp:.1f}_{width}.jpg"
        cmd = [
            ffmpeg_path, "-y",
            "-ss", str(timestamp),
            "-i", str(path),
            "-vframes", "1",
            "-vf", f"scale={width}:-1",
            "-q:v", "2",
            str(thumb_file),
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=10)
            if thumb_file.exists():
                return FileResponse(thumb_file, media_type="image/jpeg")
        except Exception:
            pass

        raise HTTPException(status_code=500, detail=i18n("file.thumbFailed", locale=_locale(request)))

    # ----------------------------------------------------------------- #
    # 文件系统浏览
    # ----------------------------------------------------------------- #

    VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"}

    @app.get("/api/fs/drives")
    async def list_drives():
        """列出可用驱动器/根目录"""
        import os
        if sys.platform == "win32":
            # Windows: enumerate drive letters
            drives = []
            # Check all possible drive letters
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:"
                if os.path.exists(drive):
                    drives.append({
                        "name": f"{letter}:",
                        "path": f"{letter}:",
                        "type": "directory",
                    })
        else:
            # Unix: just return /
            drives = [{
                "name": "/",
                "path": "/",
                "type": "directory",
            }]
        return {"items": drives}

    @app.get("/api/fs/list")
    async def list_directory(path: str = Query(..., description="目录绝对路径")):
        """列出目录内容，返回文件和子目录"""
        dir_path = Path(path)
        if not dir_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

        try:
            entries = []
            for entry in sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                try:
                    stat = entry.stat()
                    ext = entry.suffix.lower() if entry.is_file() else ""
                    is_video = ext in VIDEO_EXTENSIONS
                    entries.append({
                        "name": entry.name,
                        "path": str(entry),
                        "type": "directory" if entry.is_dir() else "file",
                        "size": stat.st_size if entry.is_file() else None,
                        "is_video": is_video,
                        "extension": ext if entry.is_file() else "",
                    })
                except (PermissionError, OSError):
                    continue
        except PermissionError:
            raise HTTPException(status_code=403, detail=f"Permission denied: {path}")

        return {"path": str(dir_path), "items": entries}

    # ----------------------------------------------------------------- #
    # 预设管理
    # ----------------------------------------------------------------- #

    @app.get("/api/presets")
    async def list_presets():
        """列出所有预设"""
        manager = PresetManager()
        return {"items": manager.list()}

    @app.get("/api/presets/{name}")
    async def get_preset(name: str):
        """获取预设详情"""
        manager = PresetManager()
        preset = manager.get(name)
        if not preset:
            raise HTTPException(status_code=404, detail=f"Preset not found: {name}")
        return preset

    @app.put("/api/presets/{name}")
    async def save_preset(name: str, body: dict[str, Any]):
        """创建或更新预设"""
        body["name"] = name
        manager = PresetManager()
        preset = manager.save(body)
        return preset

    @app.delete("/api/presets/{name}")
    async def delete_preset(name: str):
        """删除预设"""
        manager = PresetManager()
        ok = manager.delete(name)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Preset not found: {name}")
        return {"status": "deleted"}

    @app.post("/api/presets/{name}/duplicate")
    async def duplicate_preset(name: str, new_name: str = Query(..., alias="new_name")):
        """复制预设"""
        manager = PresetManager()
        preset = manager.duplicate(name, new_name)
        if not preset:
            raise HTTPException(status_code=404, detail=f"Preset not found: {name}")
        return preset

    # ----------------------------------------------------------------- #
    # Prompt 管理
    # ----------------------------------------------------------------- #

    @app.get("/api/prompts")
    async def list_prompts():
        """列出可用 Prompt 模板"""
        manager = PresetManager()
        prompts_list = manager.list_prompts()
        items = []
        for name in prompts_list:
            content = manager.get_prompt(name)
            items.append({"name": name, "hasContent": content is not None})
        return {"items": items}

    @app.get("/api/prompts/{name}")
    async def get_prompt(name: str):
        """获取 Prompt 模板内容"""
        manager = PresetManager()
        content = manager.get_prompt(name)
        if content is None:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {name}")
        return {"name": name, "content": content}

    @app.put("/api/prompts/{name}")
    async def save_prompt(name: str, body: dict[str, str]):
        """保存 Prompt 模板文件"""
        content = body.get("content", "")
        manager = PresetManager()
        manager.save_prompt(name, content)
        return {"status": "saved", "name": name}

    # ----------------------------------------------------------------- #
    # 用户设置
    # ----------------------------------------------------------------- #

    @app.get("/api/settings")
    async def get_settings():
        """获取用户设置"""
        from src.web.settings_manager import load_settings
        return load_settings()

    @app.put("/api/settings")
    async def save_settings_api(body: dict[str, Any]):
        """保存用户设置"""
        from src.web.settings_manager import save_settings, merge_llm_into_config, load_settings
        current = load_settings()
        # 合并提交的数据
        if "localLlm" in body:
            current["localLlm"] = {**current.get("localLlm", {}), **body["localLlm"]}
        if "onlineLlm" in body:
            current["onlineLlm"] = {**current.get("onlineLlm", {}), **body["onlineLlm"]}
        for k in ("modelType", "theme", "accentColor"):
            if k in body:
                current[k] = body[k]
        save_settings(current)
        return {"status": "ok", "settings": current}

    # ----------------------------------------------------------------- #
    # SSE 事件流
    # ----------------------------------------------------------------- #

    @app.get("/api/events")
    async def events(task_id: str | None = Query(None)):
        """SSE 事件流"""
        return StreamingResponse(
            sse_event_stream(task_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/tasks/{task_id}/events")
    async def task_events(task_id: str):
        """特定任务的 SSE 事件流"""
        return StreamingResponse(
            sse_event_stream(task_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )


# ===================================================================== #
# 启动入口
# ===================================================================== #


def run(host: str = "127.0.0.1", port: int = 8501, reload: bool = False):
    """启动 Web 服务"""
    import uvicorn

    print(f"\n{'='*50}")
    print(f"  {i18n('app.title')}")
    print(i18n("app.address", host=host, port=port))
    print(f"{'='*50}\n")

    uvicorn.run(
        "src.web.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )
