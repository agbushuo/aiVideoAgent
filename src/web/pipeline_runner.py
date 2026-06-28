"""管线执行器

从 NiceGUI 解耦的完整管线执行逻辑。
通过 REST API 触发，使用 SSE 广播进度。

流程：
1. 转录 → 2. [审核暂停点] → 3. 分析 → 4. 剪辑
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
from pathlib import Path
from typing import Any

# Windows GBK 编码兼容：强制 stdout/stderr 使用 UTF-8
if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.utils.i18n import _ as i18n
from src.transcribe.models import TranscriptResult


async def run_pipeline(task_id: str) -> None:
    """运行完整的处理管线（独立于 NiceGUI）

    通过 REST API create_task 触发，使用 SSE 广播事件。
    """
    from src.web.task_manager import TaskManager, TaskStatus

    task_manager = TaskManager()
    task = task_manager.get_task(task_id)
    if not task:
        return

    from src.main import load_config
    config = load_config()

    # 合并用户设置（优先级高于 config.yaml）
    from src.web.settings_manager import merge_llm_into_config
    config = merge_llm_into_config(config)

    # 验证视频文件存在
    video_path = Path(task.video_path)
    if not video_path.exists():
        task.status = TaskStatus.ERROR
        task.add_log("error", i18n("pipe.videoNotFound", path=task.video_path))
        await _broadcast(task_manager, task)
        await task_manager.sse_broadcast("error", {
            "task_id": task_id,
            "error": i18n("pipe.videoNotFound", path=task.video_path),
        })
        return

    loop = asyncio.get_event_loop()

    try:
        # ========== Stage 1: 转录 ==========
        task.status = TaskStatus.TRANSCRIBING
        task.update_progress(i18n("pipe.stepTranscribe"), i18n("pipe.stepLoadingModel"), 5)
        task.add_log("info", i18n("pipe.startTranscribe"))
        await _broadcast(task_manager, task)

        # 获取输出路径（用于检查已有转录）
        output_dir, stem = _get_output_paths(task)
        subtitles_dir = output_dir / "subtitles"
        json_file = subtitles_dir / f"{stem}.json"
        srt_file = subtitles_dir / f"{stem}.srt"

        transcript = None

        # 检查是否可以跳过已有转录
        if task.skip_existing_transcript and json_file.exists():
            task.update_progress(i18n("pipe.stepTranscribe"), i18n("pipe.stepSkippingTranscribe"), 20)
            task.add_log("info", i18n("pipe.loadingExistingTranscript", file=str(json_file)))
            await _broadcast(task_manager, task)

            transcript = TranscriptResult.from_json(json_file)
            task.transcript = transcript
            task.output_files["srt"] = str(srt_file)
            task.output_files["transcript_json"] = str(json_file)

            task.add_log("info", i18n("pipe.existingTranscriptLoaded", count=len(transcript.segments)))
            await _broadcast(task_manager, task)
            await task_manager.sse_broadcast("stage_complete", {
                "task_id": task_id,
                "stage_id": "transcribe",
                "stage_name": i18n("sse.transcribe"),
            })
        else:
            # 正常转录流程
            task.update_progress(i18n("pipe.stepTranscribe"), i18n("pipe.stepInitEngine"), 10)
            whisper_cfg = config.get("whisper", {})
            seg_cfg = whisper_cfg.get("segment_transcribe", {})
            ffmpeg_cfg = config.get("ffmpeg", {})

            task.add_log("info", i18n("pipe.loadingModel", model=whisper_cfg.get("model_name", "large-v3")))
            await _broadcast(task_manager, task)

            from src.transcribe.whisper_engine import WhisperEngine

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

            task.update_progress(i18n("pipe.stepTranscribe"), i18n("pipe.stepProcessingAudio"), 20)
            task.add_log("info", i18n("pipe.processingAudio", file=Path(task.video_path).name))
            await _broadcast(task_manager, task)

            transcript = await loop.run_in_executor(
                None, engine.transcribe, task.video_path, task.language
            )

            task.update_progress(i18n("pipe.stepTranscribe"), i18n("pipe.stepExportSubs"), 45)
            task.add_log("info", i18n("pipe.transcribeDone", count=len(transcript.segments)))
            await _broadcast(task_manager, task)

            # 保存转录结果
            subtitles_dir.mkdir(parents=True, exist_ok=True)

            transcript.export_srt(srt_file)
            transcript.export_json(json_file)

            task.transcript = transcript
            task.output_files["srt"] = str(srt_file)
            task.output_files["transcript_json"] = str(json_file)

            engine.unload()

            # 广播转录完成
            await task_manager.sse_broadcast("stage_complete", {
                "task_id": task_id,
                "stage_id": "transcribe",
                "stage_name": i18n("sse.transcribe"),
            })

        # ========== Stage 1.5: 字幕审核（可选暂停点） ==========
        if task.review_enabled:
            task.status = TaskStatus.REVIEW_SUBTITLES
            task.update_progress(i18n("pipe.stepReview"), i18n("pipe.stepWaitingReview"), 50)
            task.add_log("info", i18n("pipe.reviewPause"))
            await _broadcast(task_manager, task)
            task_manager.save()  # 持久化：审核暂停点
            await task_manager.sse_broadcast("pause", {
                "task_id": task_id,
                "reason": "subtitle_review",
                "message": i18n("sse.subtitleReview"),
            })

            continued = await task.wait_for_resume()
            if not continued:
                return  # 任务被取消

            task.add_log("info", i18n("pipe.reviewResume"))
            await _broadcast(task_manager, task)

        # ========== Stage 2: 分析 ==========
        task.status = TaskStatus.ANALYZING
        task.update_progress(i18n("pipe.stepAnalyze"), i18n("pipe.stepLLMAnalyze"), 60)
        task.add_log("info", i18n("pipe.startAnalyze"))
        await _broadcast(task_manager, task)

        llm_cfg = config.get("llm", {})

        from src.analyze.llm_analyzer import LLMAnalyzer, AnalysisReport, Highlight

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

        selected: Any = None

        # Smart Clip 模式
        if task.smart_clip:
            # Scene Detection
            task.update_progress(i18n("pipe.stepAnalyze"), i18n("pipe.stepSceneDetect"), 62)
            task.add_log("info", i18n("pipe.sceneDetect"))
            await _broadcast(task_manager, task)
            await task_manager.sse_broadcast("stage_start", {
                "task_id": task_id,
                "stage_id": "scene_detection",
                "stage_name": i18n("sse.sceneDetection"),
            })

            from src.clip_engine.scene_detector import WhisperSegmentDetector
            detector = WhisperSegmentDetector()
            scenes = detector.detect_scenes(task.transcript.segments)
            task._scenes = scenes
            task.add_log("info", i18n("pipe.scenesFound", count=len(scenes)))
            await _broadcast(task_manager, task)
            await task_manager.sse_broadcast("stage_complete", {
                "task_id": task_id,
                "stage_id": "scene_detection",
                "stage_name": i18n("sse.sceneDetection"),
                "duration": 0,
            })

            # LLM 标注
            task.update_progress(i18n("pipe.stepAnalyze"), i18n("pipe.stepSceneAnnotate"), 65)
            task.add_log("info", i18n("pipe.sceneAnnotate"))
            await _broadcast(task_manager, task)
            await task_manager.sse_broadcast("stage_start", {
                "task_id": task_id,
                "stage_id": "llm_annotation",
                "stage_name": i18n("sse.llmAnnotation"),
            })

            scenes = await loop.run_in_executor(
                None, analyzer.analyze_scenes, scenes, task.user_prompt
            )
            task._scenes = scenes
            task.add_log("info", i18n("pipe.annotateDone", count=len(scenes)))
            await _broadcast(task_manager, task)
            await task_manager.sse_broadcast("stage_complete", {
                "task_id": task_id,
                "stage_id": "llm_annotation",
                "stage_name": i18n("sse.llmAnnotation"),
                "duration": 0,
            })

            # Score Engine
            task.status = TaskStatus.SCORING
            task.update_progress(i18n("pipe.stepScoring"), i18n("pipe.stepComputeScore"), 72)
            task.add_log("info", i18n("pipe.scoreEngine", preset=task.preset, mode=task.clip_mode))
            await _broadcast(task_manager, task)
            await task_manager.sse_broadcast("stage_start", {
                "task_id": task_id,
                "stage_id": "scoring",
                "stage_name": i18n("sse.scoring"),
            })

            from src.clip_engine.scorer import ScoreEngine
            scorer = ScoreEngine(preset=task.preset, clip_mode=task.clip_mode)
            candidates = scorer.compute(scenes)
            task._candidates = candidates
            task.add_log("info", i18n("pipe.candidatesGen", count=len(candidates)))
            await _broadcast(task_manager, task)
            await task_manager.sse_broadcast("stage_complete", {
                "task_id": task_id,
                "stage_id": "scoring",
                "stage_name": i18n("sse.scoring"),
                "duration": 0,
            })

            # Filter Engine
            task.status = TaskStatus.FILTERING
            task.update_progress(i18n("pipe.stepFiltering"), i18n("pipe.stepDiversity"), 78)
            task.add_log("info", i18n("pipe.filterEngine"))
            await _broadcast(task_manager, task)
            await task_manager.sse_broadcast("stage_start", {
                "task_id": task_id,
                "stage_id": "filtering",
                "stage_name": i18n("sse.filtering"),
            })

            from src.clip_engine.filter import ClipFilter
            clip_filter = ClipFilter(
                max_clips=task.num_clips,
                target_duration=task.target_duration if not task.use_duration_planner else 0.0,
            )
            selected = clip_filter.filter(candidates)
            task._selected = selected
            task.add_log("info", i18n("pipe.selected", count=len(selected)))
            await _broadcast(task_manager, task)
            await task_manager.sse_broadcast("stage_complete", {
                "task_id": task_id,
                "stage_id": "filtering",
                "stage_name": i18n("sse.filtering"),
                "duration": 0,
            })

            # Duration Planner (optional)
            if task.use_duration_planner and task.target_duration > 0 and selected:
                task.update_progress(i18n("pipe.stepPlanning"), i18n("pipe.stepPlanCombo"), 82)
                task.add_log("info", i18n("pipe.durationPlan", target=task.target_duration))
                await _broadcast(task_manager, task)
                await task_manager.sse_broadcast("stage_start", {
                    "task_id": task_id,
                    "stage_id": "duration_planning",
                    "stage_name": i18n("sse.durationPlanning"),
                })

                from src.clip_engine.planner import DurationPlanner
                planner = DurationPlanner(target_duration=task.target_duration)
                plan = planner.plan(selected)
                selected = plan.selected
                task._selected = selected
                task.add_log("info", i18n("pipe.planDone", count=len(selected), duration=plan.total_duration))
                await _broadcast(task_manager, task)
                await task_manager.sse_broadcast("stage_complete", {
                    "task_id": task_id,
                    "stage_id": "duration_planning",
                    "stage_name": i18n("sse.durationPlanning"),
                    "duration": 0,
                })

            # Final Review (optional)
            if task.use_final_review and selected:
                task.update_progress(i18n("pipe.stepReviewFinal"), i18n("pipe.stepLLMReview"), 86)
                task.add_log("info", i18n("pipe.finalReview"))
                await _broadcast(task_manager, task)
                await task_manager.sse_broadcast("stage_start", {
                    "task_id": task_id,
                    "stage_id": "final_review",
                    "stage_name": i18n("sse.finalReview"),
                })

                from src.clip_engine.reviewer import FinalReviewer
                reviewer = FinalReviewer(
                    llm_analyzer=analyzer,
                    num_to_select=task.num_clips if task.num_clips > 0 else None,
                    platform=task.preset,
                    target_duration=task.target_duration,
                    user_prompt=task.user_prompt,
                )
                review_result = reviewer.review(selected)
                selected = review_result.candidates
                task._selected = selected
                task.add_log("info", i18n("pipe.reviewDone", count=len(selected)))
                await _broadcast(task_manager, task)
                await task_manager.sse_broadcast("stage_complete", {
                    "task_id": task_id,
                    "stage_id": "final_review",
                    "stage_name": i18n("sse.finalReview"),
                    "duration": 0,
                })

            # 构建报告
            highlights = []
            for i, c in enumerate(selected or []):
                highlights.append(
                    Highlight(
                        segment_id=c.scene_id,
                        start=c.start,
                        end=c.end,
                        title=c.scene.summary[:50] if c.scene.summary else f"片段 {i + 1}",
                        reason=c.scene.summary or "",
                        score=min(c.composite_score / 10.0, 1.0),
                    )
                )
            report = AnalysisReport(
                summary="",
                highlights=highlights,
                video_path=task.video_path,
            )
        else:
            # 传统分析模式
            report = await loop.run_in_executor(
                None, analyzer.analyze, task.transcript
            )
            report.video_path = task.video_path

        # 导出报告
        reports_dir = output_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_json = reports_dir / f"{stem}.json"
        report_md = reports_dir / f"{stem}.md"

        from src.utils.io import export_analysis_json, export_markdown_report
        export_analysis_json(report, report_json)
        export_markdown_report(report, report_md)

        task.output_files["report_json"] = str(report_json)
        task.output_files["report_md"] = str(report_md)
        task.add_log("info", i18n("pipe.analysisDone", count=len(report.highlights)))
        await _broadcast(task_manager, task)

        # ========== Stage 3: 剪辑 ==========
        task.status = TaskStatus.CLIPPING
        task.update_progress(i18n("pipe.stepClipping"), i18n("pipe.stepFFmpegClip"), 90)
        task.add_log("info", i18n("pipe.startClipping"))
        await _broadcast(task_manager, task)
        await task_manager.sse_broadcast("stage_start", {
            "task_id": task_id,
            "stage_id": "clipping",
            "stage_name": i18n("sse.clipping"),
        })

        from src.edit.clipper import Clipper
        clipper = Clipper(
            ffmpeg_path=ffmpeg_cfg.get("path", "ffmpeg"),
            ffprobe_path=ffmpeg_cfg.get("probe_path", "ffprobe"),
        )

        clips_dir = output_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        clip_times = [(h.start, h.end) for h in report.highlights]
        clip_paths = []

        for i, (start, end) in enumerate(clip_times):
            clip_file = clips_dir / f"{stem}_clip_{i + 1:02d}.mp4"
            clip_result = clipper.extract_segment(
                video_path=task.video_path,
                start=start,
                end=end,
                output_path=clip_file,
            )
            if clip_result.success:
                clip_paths.append(clip_result.clip_path)

        merged_path = None
        if task.merge_clips and len(clip_paths) > 1:
            merged_file = clips_dir / f"{stem}_highlight.mp4"
            merge_result = clipper.merge_clips(
                clip_paths=[str(p) for p in clip_paths],
                output_path=merged_file,
                transition_duration=task.transition_duration,
            )
            merged_path = str(merge_result)

        task.output_files["merged_video"] = merged_path or ""
        task.update_progress(i18n("pipe.stepDone"), "", 100)
        task.add_log("success", i18n("pipe.clipDone", count=len(clip_times)))
        await _broadcast(task_manager, task)
        await task_manager.sse_broadcast("stage_complete", {
            "task_id": task_id,
            "stage_id": "clipping",
            "stage_name": i18n("sse.clipping"),
            "duration": 0,
        })

        # 完成
        task.status = TaskStatus.COMPLETED
        task.add_log("success", i18n("pipe.allDone", dir=str(output_dir)))
        await _broadcast(task_manager, task)
        task_manager.save()  # 持久化：管线完成
        await task_manager.sse_broadcast("complete", {
            "task_id": task_id,
            "output_files": task.output_files,
        })

    except Exception as e:
        import traceback

        error_detail = traceback.format_exc()
        task.status = TaskStatus.ERROR
        task.add_log("error", i18n("task.failed", error=str(e)[:200]))
        # Store traceback in logs for debugging
        for line in error_detail.strip().split("\n")[1:]:
            task.add_log("error", line.strip())
        await _broadcast(task_manager, task)
        task_manager.save()  # 持久化：管线失败
        await task_manager.sse_broadcast("error", {
            "task_id": task_id,
            "error": str(e)[:200],
            "traceback": error_detail[-500:],
        })


async def _broadcast(task_manager: "TaskManager", task: "PipelineTask") -> None:
    """广播任务更新（WebSocket + SSE）"""
    await task_manager.notify_task_update(task)
    await task_manager.sse_broadcast("progress", {
        "task_id": task.task_id,
        "step": task.progress.step,
        "step_detail": task.progress.step_detail,
        "percent": task.progress.percent,
    })
    await task_manager.sse_broadcast("task_status", {
        "task_id": task.task_id,
        "status": task.status_str,
        "percent": task.progress.percent,
    })


def _get_output_paths(task: "PipelineTask") -> tuple[Path, str]:
    """获取输出目录和视频文件名"""
    output_dir = Path(task.output_dir) / Path(task.video_path).stem
    stem = Path(task.video_path).stem
    return output_dir, stem
