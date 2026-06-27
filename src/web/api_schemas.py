"""API 请求/响应 Pydantic 模型

为 Next.js 前端提供结构化的请求和响应验证。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ===================================================================== #
# 任务管理
# ===================================================================== #


class PipelineStageConfig(BaseModel):
    """单个管线阶段的配置"""
    stage_id: str
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    """完整的管线配置（含所有阶段）"""
    stages: list[PipelineStageConfig]


class TaskCreateRequest(BaseModel):
    """创建任务的请求体"""
    video_path: str
    language: str = "zh"
    review_enabled: bool = True
    output_dir: str = "outputs"
    pipeline_config: PipelineConfig | None = None

    # 是否自动启动管线执行
    start: bool = True

    # 跳过已有转录：如果字幕 JSON 已存在，直接加载而非重新跑 Whisper
    skip_existing_transcript: bool = False

    # 兼容旧模式的简化字段
    smart_clip: bool = False
    clip_mode: str = "viral"
    preset: str = "viral"
    num_clips: int = 0
    target_duration: float = 0.0
    user_prompt: str | None = None
    use_duration_planner: bool = False
    use_final_review: bool = False
    min_score: float | None = None
    merge_clips: bool = True
    transition_duration: float = 0.5


class TaskResponse(BaseModel):
    """任务基本信息响应"""
    task_id: str
    status: str
    video_path: str
    output_dir: str
    progress: dict[str, Any] = Field(default_factory=dict)
    stage_results: dict[str, Any] = Field(default_factory=dict)


class TaskDetailResponse(TaskResponse):
    """任务详情响应（含日志、产物）"""
    logs: list[dict[str, Any]] = Field(default_factory=list)
    output_files: dict[str, str] = Field(default_factory=dict)
    pipeline_config: PipelineConfig | None = None


# ===================================================================== #
# 阶段级执行
# ===================================================================== #


class StageResultResponse(BaseModel):
    """阶段执行结果"""
    stage_id: str
    status: str  # pending | running | completed | failed | skipped
    started_at: float | None = None
    completed_at: float | None = None
    duration_seconds: float | None = None
    output_artifacts: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


class StageRunRequest(BaseModel):
    """单阶段执行请求"""
    params: dict[str, Any] = Field(default_factory=dict)


# ===================================================================== #
# Scene 数据
# ===================================================================== #


class SceneResponse(BaseModel):
    """场景数据响应"""
    scene_id: int
    start: float
    end: float
    duration: float
    segment_ids: list[int] = Field(default_factory=list)
    text: str = ""
    scene_type: str = "Other"
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    multi_score: dict[str, float] = Field(default_factory=dict)


class SceneListResponse(BaseModel):
    """场景列表（带分页和筛选信息）"""
    total: int
    scenes: list[SceneResponse]


class SceneUpdateRequest(BaseModel):
    """手动修改场景"""
    scene_type: str | None = None
    tags: list[str] | None = None
    summary: str | None = None
    multi_score: dict[str, float] | None = None


# ===================================================================== #
# ClipCandidate 数据
# ===================================================================== #


class ClipCandidateResponse(BaseModel):
    """剪辑候选响应"""
    scene: SceneResponse
    composite_score: float
    rank: int
    selected: bool


class CandidateListResponse(BaseModel):
    """候选列表"""
    total: int
    candidates: list[ClipCandidateResponse]


class BulkSelectRequest(BaseModel):
    """批量选中/取消"""
    scene_ids: list[int]
    selected: bool


# ===================================================================== #
# 字幕
# ===================================================================== #


class SegmentResponse(BaseModel):
    """字幕片段"""
    segment_id: int
    start: float
    end: float
    text: str


class TranscriptResponse(BaseModel):
    """转录结果"""
    language: str
    duration: float
    segments: list[SegmentResponse]


class TranscriptUpdateRequest(BaseModel):
    """更新字幕"""
    segments: list[SegmentResponse]


class SegmentUpdateRequest(BaseModel):
    """更新单个片段"""
    text: str


# ===================================================================== #
# 配置参考数据
# ===================================================================== #


class PresetInfo(BaseModel):
    """预设信息"""
    name: str
    weights: dict[str, float]


class ClipModeInfo(BaseModel):
    """剪辑模式信息"""
    name: str
    weights: dict[str, float]


class ScoreDimensionInfo(BaseModel):
    """评分维度"""
    name: str
    description: str


class PipelineStageInfo(BaseModel):
    """管线阶段定义"""
    stage_id: str
    label: str
    description: str
    icon: str
    default_params: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)


class DurationTemplate(BaseModel):
    """时长模板"""
    name: str
    duration_seconds: float
    num_clips: int


class ConfigResponse(BaseModel):
    """通用配置响应"""
    items: list[Any]


# ===================================================================== #
# SSE 事件
# ===================================================================== #


class SSEEvent(BaseModel):
    """SSE 事件"""
    event_type: str  # task_status | stage_start | stage_complete | log | progress | error | pause | complete
    data: dict[str, Any]
