"""后端国际化（i18n）模块

字典式翻译，支持 zh/en 两种语言。
通过 Accept-Language 请求头或显式 locale 参数获取语言。
"""

from __future__ import annotations

from typing import Any

# ===================================================================== #
# 翻译字典
# ===================================================================== #

MESSAGES: dict[str, dict[str, str]] = {
    # ---------- 应用生命周期 ----------
    "zh": {
        "app.starting": "VideoAgent Web 控制台启动...",
        "app.closing": "VideoAgent Web 控制台关闭",
        "app.title": "VideoAgent Web 控制台",
        "app.address": "  地址: http://{host}:{port}",
        # 任务管理
        "task.notFound": "任务不存在",
        "task.created": "任务已创建",
        "task.deletingRunning": "正在运行的任务不能删除，请先取消",
        "task.resumed": "已恢复",
        "task.cancelled": "已取消",
        "task.deleted": "已删除",
        "task.failed": "任务失败: {error}",
        # 阶段
        "stage.notFound": "阶段未执行",
        "stage.unknown": "未知的阶段: {stage_id}",
        # 场景
        "scene.notFound": "场景不存在",
        "scene.missingTranscript": "需要先执行转录阶段",
        "scene.missingScenes": "需要先执行场景检测阶段",
        "scene.missingAnnotation": "需要先执行 LLM 标注阶段",
        # 候选
        "candidate.missingScoring": "需要先执行评分阶段",
        "candidate.missingFiltering": "需要先执行筛选阶段",
        # 剪辑
        "clip.noCandidates": "没有可剪辑的片段",
        # 字幕
        "transcript.notReady": "转录尚未完成",
        "transcript.segmentNotFound": "片段不存在",
        "transcript.saved": "已保存",
        # 文件
        "file.notFound": "文件不存在",
        "file.thumbFailed": "缩略图生成失败",
        # 管线日志
        "pipe.videoNotFound": "视频文件不存在: {path}",
        "pipe.startTranscribe": "开始转录",
        "pipe.loadingModel": "加载 Whisper {model}",
        "pipe.processingAudio": "转录视频: {file}",
        "pipe.transcribeDone": "转录完成: {count} 个片段",
        "pipe.reviewPause": "暂停：请审核字幕后点击确认并继续",
        "pipe.reviewResume": "字幕审核通过，继续分析",
        "pipe.startAnalyze": "开始 LLM 分析",
        "pipe.sceneDetect": "Scene Detection...",
        "pipe.scenesFound": "检测到 {count} 个场景",
        "pipe.sceneAnnotate": "LLM Scene 标注中...",
        "pipe.annotateDone": "Scene 标注完成: {count} 个场景",
        "pipe.scoreEngine": "Score Engine (preset={preset}, mode={mode})",
        "pipe.candidatesGen": "生成 {count} 个候选",
        "pipe.filterEngine": "Filter Engine...",
        "pipe.selected": "选中 {count} 个片段",
        "pipe.durationPlan": "Duration Planner (target={target:.0f}s)",
        "pipe.planDone": "时长规划: {count} 个片段, {duration:.1f}s",
        "pipe.finalReview": "LLM Final Review...",
        "pipe.reviewDone": "Final Review: {count} 个片段",
        "pipe.analysisDone": "分析完成: {count} 个亮点",
        "pipe.startClipping": "开始 ffmpeg 剪辑",
        "pipe.clipDone": "剪辑完成: {count} 个片段",
        "pipe.allDone": "全流程完成! 输出目录: {dir}",
        # 进度步骤名
        "pipe.stepTranscribe": "转录",
        "pipe.stepLoadingModel": "加载 Whisper 模型...",
        "pipe.stepInitEngine": "初始化引擎...",
        "pipe.stepProcessingAudio": "处理音频...",
        "pipe.stepExportSubs": "导出字幕文件...",
        "pipe.stepSkippingTranscribe": "加载已有转录...",
        "pipe.loadingExistingTranscript": "加载已有转录文件: {file}",
        "pipe.existingTranscriptLoaded": "已加载 {count} 个片段，跳过 Whisper 转录",
        "pipe.stepReview": "审核",
        "pipe.stepWaitingReview": "等待人工审核字幕...",
        "pipe.stepAnalyze": "分析",
        "pipe.stepLLMAnalyze": "LLM 分析中...",
        "pipe.stepSceneDetect": "Scene Detection...",
        "pipe.stepSceneAnnotate": "LLM Scene 标注...",
        "pipe.stepScoring": "评分",
        "pipe.stepComputeScore": "计算综合分...",
        "pipe.stepFiltering": "筛选",
        "pipe.stepDiversity": "Diversity 去重...",
        "pipe.stepPlanning": "规划",
        "pipe.stepPlanCombo": "按目标时长组合...",
        "pipe.stepReviewFinal": "评审",
        "pipe.stepLLMReview": "LLM 最终精选...",
        "pipe.stepClipping": "剪辑",
        "pipe.stepFFmpegClip": "ffmpeg 裁剪中...",
        "pipe.stepDone": "完成",
        # SSE 阶段名
        "sse.transcribe": "转录",
        "sse.sceneDetection": "场景检测",
        "sse.llmAnnotation": "LLM 标注",
        "sse.scoring": "评分引擎",
        "sse.filtering": "筛选引擎",
        "sse.durationPlanning": "时长规划",
        "sse.finalReview": "最终评审",
        "sse.clipping": "FFmpeg 剪辑",
        "sse.subtitleReview": "转录完成，等待字幕审核",
    },
    "en": {
        "app.starting": "VideoAgent Web Console starting...",
        "app.closing": "VideoAgent Web Console shutting down",
        "app.title": "VideoAgent Web Console",
        "app.address": "  Address: http://{host}:{port}",
        # Task management
        "task.notFound": "Task not found",
        "task.created": "Task created",
        "task.deletingRunning": "Cannot delete a running task, cancel it first",
        "task.resumed": "Resumed",
        "task.cancelled": "Cancelled",
        "task.deleted": "Deleted",
        "task.failed": "Task failed: {error}",
        # Stages
        "stage.notFound": "Stage not executed",
        "stage.unknown": "Unknown stage: {stage_id}",
        # Scenes
        "scene.notFound": "Scene not found",
        "scene.missingTranscript": "Transcribe stage must be executed first",
        "scene.missingScenes": "Scene detection stage must be executed first",
        "scene.missingAnnotation": "LLM annotation stage must be executed first",
        # Candidates
        "candidate.missingScoring": "Scoring stage must be executed first",
        "candidate.missingFiltering": "Filtering stage must be executed first",
        # Clipping
        "clip.noCandidates": "No clips to process",
        # Transcript
        "transcript.notReady": "Transcription not yet complete",
        "transcript.segmentNotFound": "Segment not found",
        "transcript.saved": "Saved",
        # Files
        "file.notFound": "File not found",
        "file.thumbFailed": "Thumbnail generation failed",
        # Pipeline logs
        "pipe.videoNotFound": "Video file not found: {path}",
        "pipe.startTranscribe": "Starting transcription",
        "pipe.loadingModel": "Loading Whisper {model}",
        "pipe.processingAudio": "Transcribing video: {file}",
        "pipe.transcribeDone": "Transcription complete: {count} segments",
        "pipe.reviewPause": "Paused: please review subtitles and click continue",
        "pipe.reviewResume": "Subtitles approved, continuing analysis",
        "pipe.startAnalyze": "Starting LLM analysis",
        "pipe.sceneDetect": "Scene Detection...",
        "pipe.scenesFound": "Detected {count} scenes",
        "pipe.sceneAnnotate": "LLM Scene Annotation...",
        "pipe.annotateDone": "Scene annotation complete: {count} scenes",
        "pipe.scoreEngine": "Score Engine (preset={preset}, mode={mode})",
        "pipe.candidatesGen": "Generated {count} candidates",
        "pipe.filterEngine": "Filter Engine...",
        "pipe.selected": "Selected {count} clips",
        "pipe.durationPlan": "Duration Planner (target={target:.0f}s)",
        "pipe.planDone": "Duration plan: {count} clips, {duration:.1f}s",
        "pipe.finalReview": "LLM Final Review...",
        "pipe.reviewDone": "Final Review: {count} clips",
        "pipe.analysisDone": "Analysis complete: {count} highlights",
        "pipe.startClipping": "Starting ffmpeg clipping",
        "pipe.clipDone": "Clipping complete: {count} clips",
        "pipe.allDone": "Pipeline complete! Output dir: {dir}",
        # Progress step names
        "pipe.stepTranscribe": "Transcribing",
        "pipe.stepLoadingModel": "Loading Whisper model...",
        "pipe.stepInitEngine": "Initializing engine...",
        "pipe.stepProcessingAudio": "Processing audio...",
        "pipe.stepExportSubs": "Exporting subtitles...",
        "pipe.stepSkippingTranscribe": "Loading existing transcript...",
        "pipe.loadingExistingTranscript": "Loading existing transcript file: {file}",
        "pipe.existingTranscriptLoaded": "Loaded {count} segments, skipped Whisper transcription",
        "pipe.stepReview": "Review",
        "pipe.stepWaitingReview": "Waiting for subtitle review...",
        "pipe.stepAnalyze": "Analyzing",
        "pipe.stepLLMAnalyze": "LLM analyzing...",
        "pipe.stepSceneDetect": "Scene Detection...",
        "pipe.stepSceneAnnotate": "LLM Scene Annotation...",
        "pipe.stepScoring": "Scoring",
        "pipe.stepComputeScore": "Computing scores...",
        "pipe.stepFiltering": "Filtering",
        "pipe.stepDiversity": "Diversity dedup...",
        "pipe.stepPlanning": "Planning",
        "pipe.stepPlanCombo": "Combining by target duration...",
        "pipe.stepReviewFinal": "Reviewing",
        "pipe.stepLLMReview": "LLM final selection...",
        "pipe.stepClipping": "Clipping",
        "pipe.stepFFmpegClip": "ffmpeg clipping...",
        "pipe.stepDone": "Complete",
        # SSE stage names
        "sse.transcribe": "Transcription",
        "sse.sceneDetection": "Scene Detection",
        "sse.llmAnnotation": "LLM Annotation",
        "sse.scoring": "Score Engine",
        "sse.filtering": "Filter Engine",
        "sse.durationPlanning": "Duration Planning",
        "sse.finalReview": "Final Review",
        "sse.clipping": "FFmpeg Clipping",
        "sse.subtitleReview": "Transcription complete, waiting for subtitle review",
    },
}

# 阶段定义的多语言标签
STAGE_LABELS: dict[str, dict[str, str]] = {
    "transcribe": {"zh": "转录", "en": "Transcription"},
    "scene_detection": {"zh": "场景检测", "en": "Scene Detection"},
    "llm_annotation": {"zh": "LLM 标注", "en": "LLM Annotation"},
    "scoring": {"zh": "评分引擎", "en": "Score Engine"},
    "filtering": {"zh": "筛选引擎", "en": "Filter Engine"},
    "duration_planning": {"zh": "时长规划", "en": "Duration Planning"},
    "final_review": {"zh": "最终评审", "en": "Final Review"},
    "clipping": {"zh": "FFmpeg 剪辑", "en": "FFmpeg Clipping"},
}

STAGE_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "transcribe": {
        "zh": "Whisper 音频转录，生成字幕",
        "en": "Whisper audio transcription, generate subtitles",
    },
    "scene_detection": {
        "zh": "基于字幕时间间隔检测场景边界",
        "en": "Detect scene boundaries from subtitle gaps",
    },
    "llm_annotation": {
        "zh": "AI 对每个场景进行类型识别、标签和评分",
        "en": "AI type classification, tagging and scoring for each scene",
    },
    "scoring": {
        "zh": "根据预设权重计算多维综合评分",
        "en": "Multi-dimensional scoring based on preset weights",
    },
    "filtering": {
        "zh": "Diversity 去重、数量控制、时长约束",
        "en": "Diversity dedup, count control, duration constraints",
    },
    "duration_planning": {
        "zh": "按目标时长智能组合片段（可选）",
        "en": "Intelligently combine clips by target duration (optional)",
    },
    "final_review": {
        "zh": "LLM 二阶段精选和排序（可选）",
        "en": "LLM two-stage selection and ranking (optional)",
    },
    "clipping": {
        "zh": "ffmpeg 裁剪片段和拼接精华视频",
        "en": "ffmpeg clip extraction and highlight video merge",
    },
}


# ===================================================================== #
# 公共 API
# ===================================================================== #

def _(key: str, locale: str = "zh", **params: Any) -> str:
    """获取翻译字符串

    Args:
        key: 翻译键名
        locale: 语言代码（zh / en），默认 zh
        **params: 格式化参数

    Returns:
        翻译后的字符串，如果键不存在则返回键名本身
    """
    msg_dict = MESSAGES.get(locale, MESSAGES["zh"])
    result = msg_dict.get(key, key)

    if params and "{" in result:
        try:
            result = result.format(**params)
        except (KeyError, ValueError, IndexError):
            pass  # 格式化失败时返回原始字符串

    return result


def get_stage_label(stage_id: str, locale: str = "zh") -> str:
    """获取阶段显示名称"""
    return STAGE_LABELS.get(stage_id, {}).get(locale, stage_id)


def get_stage_description(stage_id: str, locale: str = "zh") -> str:
    """获取阶段描述"""
    return STAGE_DESCRIPTIONS.get(stage_id, {}).get(locale, "")


def resolve_locale(accept_language: str | None = None, default: str = "zh") -> str:
    """从 Accept-Language 头解析语言代码

    简化版解析：只提取第一个高质量的语言标签。
    """
    if not accept_language:
        return default

    for part in accept_language.split(","):
        part = part.strip()
        if "zh" in part:
            return "zh"
        if "en" in part:
            return "en"

    return default
