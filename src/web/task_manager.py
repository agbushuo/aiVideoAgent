"""任务管理器

管理视频处理任务的生命周期，支持：
- 任务状态追踪
- 字幕审核暂停/恢复
- WebSocket 实时推送进度
- 任务取消
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator

from src.transcribe.models import Segment, TranscriptResult


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"              # 等待执行
    TRANSCRIBING = "transcribing"    # 转录中
    REVIEW_SUBTITLES = "review_subtitles"  # 等待字幕审核（暂停点）
    ANALYZING = "analyzing"          # LLM 分析中
    SCORING = "scoring"              # Smart Clip 评分中
    FILTERING = "filtering"          # Smart Clip 筛选中
    CLIPPING = "clipping"            # ffmpeg 剪辑中
    COMPLETED = "completed"          # 完成
    CANCELLED = "cancelled"          # 已取消
    ERROR = "error"                  # 错误


class PipelineStep(str, Enum):
    """管线步骤"""
    TRANSCRIBE = "transcribe"
    REVIEW = "review"
    ANALYZE = "analyze"
    CLIP = "clip"


@dataclass
class PipelineStageConfig:
    """单个管线阶段的配置"""
    stage_id: str
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class StageResult:
    """阶段执行结果"""
    stage_id: str
    status: str = "pending"  # pending | running | completed | failed | skipped
    started_at: float | None = None
    completed_at: float | None = None
    duration_seconds: float | None = None
    output_artifacts: dict[str, str] = field(default_factory=dict)
    error: str | None = None

    @property
    def is_done(self) -> bool:
        return self.status in ("completed", "failed", "skipped")


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: float
    level: str          # info / warning / error / success
    message: str
    step: str = ""      # 当前步骤


@dataclass
class TaskProgress:
    """任务进度"""
    step: str = ""                  # 当前步骤名称
    step_detail: str = ""           # 步骤详情
    percent: float = 0.0            # 总体进度百分比 (0-100)
    status: str = TaskStatus.PENDING


@dataclass
class PipelineTask:
    """管线任务"""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    video_path: str = ""
    output_dir: str = "outputs"
    status: TaskStatus = TaskStatus.PENDING

    # 转录配置
    language: str = "zh"

    # Smart Clip 配置
    smart_clip: bool = False
    clip_mode: str = "viral"
    preset: str = "viral"
    num_clips: int = 0
    target_duration: float = 0.0
    user_prompt: str = ""
    use_duration_planner: bool = False
    use_final_review: bool = False

    # 传统剪辑配置
    clip: bool = False
    min_score: float | None = None
    merge_clips: bool = True
    transition_duration: float = 0.5

    # 审核配置
    review_enabled: bool = True     # 是否启用字幕审核暂停点

    # 断点续跑配置
    skip_existing_transcript: bool = False  # 跳过已有转录文件

    # 阶段级配置（新）
    pipeline_stages: list[PipelineStageConfig] = field(default_factory=list)
    stage_results: dict[str, StageResult] = field(default_factory=dict)

    # 进度和日志
    progress: TaskProgress = field(default_factory=TaskProgress)
    logs: list[LogEntry] = field(default_factory=list)

    # 转录结果（审核用）
    transcript: TranscriptResult | None = None

    # 输出文件路径
    output_files: dict[str, str] = field(default_factory=dict)

    # 中间产物（运行时缓存）
    _scenes: list[Any] = field(default_factory=list)  # Scene[]
    _candidates: list[Any] = field(default_factory=list)  # ClipCandidate[]
    _selected: list[Any] = field(default_factory=list)  # 选中的 ClipCandidate[]

    # 控制信号
    _resume_event: asyncio.Event | None = None
    _cancelled: bool = False

    @property
    def status_str(self) -> str:
        """安全获取状态字符串，兼容枚举和字符串两种形式"""
        if isinstance(self.status, TaskStatus):
            return self.status.value
        return self.status

    def add_log(self, level: str, message: str, step: str = ""):
        """添加日志条目"""
        import time
        self.logs.append(LogEntry(
            timestamp=time.time(),
            level=level,
            message=message,
            step=step or self.progress.step,
        ))

    def update_progress(self, step: str, detail: str = "", percent: float = 0.0):
        """更新进度"""
        self.progress.step = step
        self.progress.step_detail = detail
        self.progress.percent = percent
        self.progress.status = self.status

    async def wait_for_resume(self, timeout: float | None = None) -> bool:
        """等待用户点击"继续"（在字幕审核暂停点）

        Returns:
            True 如果用户继续，False 如果任务被取消
        """
        if not self._resume_event:
            self._resume_event = asyncio.Event()
        else:
            self._resume_event.clear()

        try:
            await asyncio.wait_for(self._resume_event.wait(), timeout=timeout)
            return not self._cancelled
        except asyncio.TimeoutError:
            return False

    def resume(self):
        """用户点击"继续"，恢复任务执行"""
        if self._resume_event:
            self._resume_event.set()

    def cancel(self):
        """取消任务"""
        self._cancelled = True
        self.status = TaskStatus.CANCELLED
        if self._resume_event:
            self._resume_event.set()

    def get_stage_config(self, stage_id: str) -> PipelineStageConfig | None:
        """获取指定阶段的配置"""
        for stage in self.pipeline_stages:
            if stage.stage_id == stage_id:
                return stage
        return None

    def is_stage_enabled(self, stage_id: str) -> bool:
        """检查阶段是否启用"""
        config = self.get_stage_config(stage_id)
        return config is not None and config.enabled

    def init_stage_results(self, stage_ids: list[str]):
        """初始化所有阶段结果为 pending"""
        for stage_id in stage_ids:
            if stage_id not in self.stage_results:
                self.stage_results[stage_id] = StageResult(stage_id=stage_id)


class TaskManager:
    """任务管理器 - 单例模式"""

    _instance: TaskManager | None = None
    _tasks: dict[str, PipelineTask]
    _subscribers: list  # WebSocket 连接列表
    _sse_queues: list[asyncio.Queue]  # SSE 连接队列

    def __new__(cls) -> "TaskManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tasks = {}
            cls._instance._subscribers = []
            cls._instance._sse_queues = []
        return cls._instance

    # ---- 持久化 ----

    def _task_to_dict(self, task: PipelineTask) -> dict:
        """将任务序列化为字典，手动构建以排除不可序列化的运行时字段"""

        def _serialize(obj):
            try:
                if obj is None:
                    return None
                if isinstance(obj, Enum):
                    return obj.value
                if isinstance(obj, dict):
                    return {k: _serialize(v) for k, v in obj.items()}
                if isinstance(obj, (list, tuple)):
                    return [_serialize(item) for item in obj]
                if is_dataclass(obj) and not isinstance(obj, type):
                    # 递归序列化 dataclass，跳过不可序列化的字段
                    return {
                        f.name: _serialize(getattr(obj, f.name))
                        for f in obj.__dataclass_fields__.values()
                    }
                # 字符串布尔值修复（旧数据中 "True"/"False" 存为字符串）
                if isinstance(obj, str) and obj == "True":
                    return True
                if isinstance(obj, str) and obj == "False":
                    return False
                # 基本类型（str, int, float, bool, Path, datetime 等）
                return obj
            except Exception:
                # 兜底：任何无法序列化的对象转为字符串
                return str(obj)

        # 手动选取可持久化的字段（跳过运行时字段）
        skip_fields = {"_resume_event", "_cancelled", "_scenes", "_candidates", "_selected"}
        d = {}
        for f in task.__dataclass_fields__.values():
            if f.name in skip_fields:
                continue
            d[f.name] = _serialize(getattr(task, f.name))
        return d

    def save(self, path: str | Path | None = None):
        """保存所有任务到 JSON 文件"""
        if path is None:
            path = Path(__file__).parent.parent.parent / "data" / "tasks.json"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {tid: self._task_to_dict(t) for tid, t in self._tasks.items()}
        path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")

    def _parse_bool(self, value: Any) -> Any:
        """将字符串布尔值转为 Python bool，非布尔值原样返回"""
        if value == "True":
            return True
        if value == "False":
            return False
        return value

    def _parse_float(self, value: Any) -> Any:
        """将字符串数字转为 float，失败时原样返回"""
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
        return value

    def _parse_task_status(self, value: Any) -> TaskStatus:
        """解析任务状态，兼容旧版 'TaskStatus.COMPLETED' 格式"""
        if isinstance(value, TaskStatus):
            return value
        if isinstance(value, str):
            # 去掉 'TaskStatus.' 前缀，转为小写匹配
            cleaned = value.replace("TaskStatus.", "").lower()
            try:
                return TaskStatus(cleaned)
            except ValueError:
                pass
        # 兜底：返回 unknown 状态（映射到 error）
        return TaskStatus.ERROR

    def _parse_repr_string(self, text: str) -> dict | None:
        """从 Python repr() 字符串中提取关键字段

        例如:
            "TaskProgress(step='完成', step_detail='', percent=100, status=<TaskStatus.CLIPPING: 'clipping'>)"
            → {"step": "完成", "step_detail": "", "percent": 100, "status": "clipping"}

            "LogEntry(timestamp=1782535975.99, level='info', message='开始转录', step='转录')"
            → {"timestamp": 1782535975.99, "level": "info", "message": "开始转录", "step": "转录"}
        """
        import re

        # 匹配 ClassName(key=value, key2='value2', ...)
        m = re.match(r"^(\w+)\((.*)\)$", text.strip(), re.DOTALL)
        if not m:
            return None

        class_name = m.group(1)
        body = m.group(2)

        result = {}
        # 用正则逐个提取 key=value 对
        # 处理字符串值、数字值、枚举值
        for km in re.finditer(r"(\w+)\s*=\s*", body):
            key = km.group(1)
            rest = body[km.end():]

            # 尝试匹配字符串 '...'
            str_match = re.match(r"'((?:[^'\\]|\\.)*)'", rest)
            if str_match:
                result[key] = str_match.group(1)
                continue

            # 尝试匹配枚举 <TaskStatus.X: 'y'>
            enum_match = re.match(r"<\w+\.\w+:\s*'(\w+)'>", rest)
            if enum_match:
                result[key] = enum_match.group(1)
                continue

            # 尝试匹配数字
            num_match = re.match(r"(\d+(?:\.\d+)?)", rest)
            if num_match:
                val = num_match.group(1)
                if "." in val:
                    result[key] = float(val)
                else:
                    result[key] = int(val)
                continue

            # 尝试匹配 None, True, False
            if rest.lstrip().startswith("None"):
                result[key] = None
            elif rest.lstrip().startswith("True"):
                result[key] = True
            elif rest.lstrip().startswith("False"):
                result[key] = False

        if class_name == "TaskProgress":
            # 确保 percent 是数字
            if "percent" in result:
                result["percent"] = float(result.get("percent", 0))
            # 解析 status 枚举字符串
            if "status" in result and isinstance(result["status"], str):
                try:
                    result["status"] = TaskStatus(result["status"])
                except ValueError:
                    pass
            return result

        if class_name == "LogEntry":
            if "timestamp" in result:
                result["timestamp"] = float(result["timestamp"])
            return result

        return result

    def load(self, path: str | Path | None = None):
        """从 JSON 文件恢复任务（兼容旧版序列化格式）"""
        if path is None:
            path = Path(__file__).parent.parent.parent / "data" / "tasks.json"
        path = Path(path)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for tid, td in data.items():
                try:
                    # --- 修复任务状态 ---
                    if "status" in td:
                        td["status"] = self._parse_task_status(td["status"])

                    # --- 修复布尔值 ---
                    bool_fields = [
                        "smart_clip", "use_duration_planner", "use_final_review",
                        "clip", "merge_clips", "review_enabled", "skip_existing_transcript",
                    ]
                    for f in bool_fields:
                        if f in td:
                            td[f] = self._parse_bool(td[f])

                    # --- 修复数字字段 ---
                    float_fields = ["target_duration", "transition_duration", "min_score"]
                    for f in float_fields:
                        if f in td:
                            td[f] = self._parse_float(td[f])

                    int_fields = ["num_clips"]
                    for f in int_fields:
                        if f in td:
                            td[f] = int(float(td[f])) if td[f] is not None else 0

                    # --- 修复 progress（可能是 repr 字符串） ---
                    if "progress" in td and isinstance(td["progress"], str):
                        parsed = self._parse_repr_string(td["progress"])
                        if parsed:
                            td["progress"] = TaskProgress(**{
                                k: v for k, v in parsed.items()
                                if k in TaskProgress.__dataclass_fields__
                            })
                        else:
                            td["progress"] = TaskProgress()

                    # --- 修复 logs（可能是 repr 字符串数组） ---
                    if "logs" in td and isinstance(td["logs"], list):
                        parsed_logs = []
                        for log_entry in td["logs"]:
                            if isinstance(log_entry, dict):
                                parsed_logs.append(LogEntry(**log_entry))
                            elif isinstance(log_entry, str):
                                parsed = self._parse_repr_string(log_entry)
                                if parsed:
                                    parsed_logs.append(LogEntry(**{
                                        k: v for k, v in parsed.items()
                                        if k in LogEntry.__dataclass_fields__
                                    }))
                        td["logs"] = parsed_logs

                    # --- 重建 StageResult ---
                    if "stage_results" in td and isinstance(td["stage_results"], dict):
                        sr = {}
                        for sid, srd in td["stage_results"].items():
                            if isinstance(srd, dict):
                                sr[sid] = StageResult(**srd)
                            else:
                                sr[sid] = srd
                        td["stage_results"] = sr

                    # --- 重建 PipelineStageConfig ---
                    if "pipeline_stages" in td and isinstance(td["pipeline_stages"], list):
                        td["pipeline_stages"] = [
                            PipelineStageConfig(**s) if isinstance(s, dict) else s
                            for s in td["pipeline_stages"]
                        ]

                    # --- 重建 transcript ---
                    if td.get("transcript") is not None and isinstance(td["transcript"], dict):
                        from src.transcribe.models import TranscriptResult
                        td["transcript"] = TranscriptResult(**td["transcript"])
                    elif isinstance(td.get("transcript"), str):
                        # 旧版可能是 repr 字符串，跳过
                        td["transcript"] = None

                    task = PipelineTask(**td)
                    # 重置运行时字段
                    task._resume_event = None
                    task._cancelled = False
                    task._scenes = []
                    task._candidates = []
                    task._selected = []
                    self._tasks[tid] = task

                except Exception as e:
                    print(f"警告: 加载任务 {tid} 失败: {e}（已跳过）")

        except Exception as e:
            print(f"警告: 加载任务文件失败: {e}")

    def _save_now(self):
        """立即持久化（内部调用）"""
        try:
            self.save()
        except Exception:
            pass  # 静默失败，不影响主流程

    def create_task(self, **kwargs) -> PipelineTask:
        """创建新任务"""
        task = PipelineTask(**kwargs)
        self._tasks[task.task_id] = task
        self._save_now()
        return task

    def get_task(self, task_id: str) -> PipelineTask | None:
        """获取任务"""
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[PipelineTask]:
        """列出所有任务"""
        return list(self._tasks.values())

    def remove_task(self, task_id: str):
        """移除已完成的任务"""
        self._tasks.pop(task_id, None)

    def add_subscriber(self, ws: Any):
        """添加 WebSocket 订阅者"""
        self._subscribers.append(ws)

    def remove_subscriber(self, ws: Any):
        """移除 WebSocket 订阅者"""
        if ws in self._subscribers:
            self._subscribers.remove(ws)

    async def broadcast(self, data: dict[str, Any]):
        """广播消息给所有 WebSocket 订阅者"""
        import json
        message = json.dumps(data, ensure_ascii=False, default=str)
        dead = []
        for ws in self._subscribers:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.remove_subscriber(ws)

    async def notify_task_update(self, task: PipelineTask):
        """通知任务状态更新"""
        await self.broadcast({
            "type": "task_update",
            "task_id": task.task_id,
            "status": task.status_str,
            "progress": {
                "step": task.progress.step,
                "step_detail": task.progress.step_detail,
                "percent": task.progress.percent,
            },
            "logs": [
                {
                    "timestamp": log.timestamp,
                    "level": log.level,
                    "message": log.message,
                    "step": log.step,
                }
                for log in task.logs[-50:]  # 最近 50 条日志
            ],
        })

    async def sse_broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """SSE 事件广播"""
        from src.web.sse import broadcast_event as sse_send
        await sse_send(event_type, data)

    async def run_stage(
        self,
        task: PipelineTask,
        stage_id: str,
        config: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> StageResult:
        """执行单个阶段

        Args:
            task: 管线任务
            stage_id: 阶段 ID
            config: 全局配置 (config.yaml)
            params: 阶段参数覆盖

        Returns:
            阶段执行结果
        """
        from src.web.stage_executor import execute_stage, STAGE_MAP

        stage_meta = STAGE_MAP.get(stage_id)
        if not stage_meta:
            raise ValueError(f"未知的阶段: {stage_id}")

        # 检查依赖
        merged_params = {**stage_meta.get("default_params", {}), **(params or {})}

        # 创建阶段结果
        stage_result = StageResult(
            stage_id=stage_id,
            status="running",
            started_at=__import__("time").time(),
        )
        task.stage_results[stage_id] = stage_result

        # 广播阶段开始
        await self.notify_task_update(task)
        await self.sse_broadcast("stage_start", {
            "task_id": task.task_id,
            "stage_id": stage_id,
            "stage_name": stage_meta["label"],
        })

        try:
            # 执行阶段
            artifacts = await execute_stage(stage_id, task, config, merged_params)

            stage_result.status = "completed"
            stage_result.output_artifacts = artifacts
            stage_result.completed_at = __import__("time").time()
            stage_result.duration_seconds = (
                stage_result.completed_at - stage_result.started_at
            )

            await self.sse_broadcast("stage_complete", {
                "task_id": task.task_id,
                "stage_id": stage_id,
                "artifacts": artifacts,
                "duration": stage_result.duration_seconds,
            })

        except Exception as e:
            import traceback
            stage_result.status = "failed"
            stage_result.error = str(e)[:500]
            stage_result.completed_at = __import__("time").time()
            stage_result.duration_seconds = (
                stage_result.completed_at - stage_result.started_at
            )

            await self.sse_broadcast("error", {
                "task_id": task.task_id,
                "stage_id": stage_id,
                "error": str(e)[:200],
                "traceback": traceback.format_exc()[-500:],
            })

        return stage_result

    def register_sse_queue(self, queue: asyncio.Queue):
        """注册 SSE 连接队列"""
        self._sse_queues.append(queue)

    def unregister_sse_queue(self, queue: asyncio.Queue):
        """注销 SSE 连接队列"""
        if queue in self._sse_queues:
            self._sse_queues.remove(queue)

    @classmethod
    def reset(cls):
        """重置单例（测试用）"""
        cls._instance = None
