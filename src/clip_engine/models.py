"""Smart Clip Engine v2.0 数据模型

定义 Scene（场景）和 ClipCandidate（剪辑候选）数据结构，
替代原有单维度 Highlight 模型，支持多维评分和规则引擎筛选。

数据流:
    Whisper Segments → Scene Detection → Scene[]
    Scene[] → LLM 标注 → Scene[] (含 tags, multi_score)
    Scene[] → Score Engine → ClipCandidate[] (含 composite_score)
    ClipCandidate[] → Filter Engine → 选中的 ClipCandidate[]
    选中的 ClipCandidate[] → Clipper → 最终片段
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.transcribe.models import Segment


# ===================================================================== #
# 多维评分维度定义
# ===================================================================== #

MULTI_SCORE_DIMENSIONS = [
    "hook",      # 开头吸引力 (0-10)
    "emotion",   # 情绪强度 (0-10)
    "comedy",    # 搞笑程度 (0-10)
    "action",    # 动作/冲突 (0-10)
    "information",  # 信息密度 (0-10)
    "suspense",  # 悬念感 (0-10)
    "climax",    # 高潮程度 (0-10)
    "viral",     # 传播潜力 (0-10)
]

SCENE_TYPES = [
    "Dialogue",   # 对话
    "Comedy",     # 搞笑
    "Fight",      # 打斗
    "Romance",    # 浪漫
    "Speech",     # 演讲/独白
    "Teaching",   # 教学/知识
    "Transition", # 过渡
    "Music",      # 音乐
    "B-roll",     # 空镜
    "Other",      # 其他
]


# ===================================================================== #
# Scene — 场景
# ===================================================================== #

@dataclass
class Scene:
    """场景 — 由多个 Whisper segment 逻辑分组而成

    场景是 Smart Clip Engine 的核心分析单元，替代了原来直接基于
    单个 segment 的 Highlight 模型。每个 Scene 包含一段连续的、
    语义相关的内容块。

    Attributes:
        scene_id: 场景编号（从 0 开始递增）
        start: 开始时间（秒）
        end: 结束时间（秒）
        segment_ids: 包含的 Whisper segment 索引列表
        text: 场景完整文本（所有 segment 文本拼接）
        scene_type: 场景类型（LLM 标注）
        tags: 标签列表（LLM 标注，如 [搞笑, 情绪爆发, 冲突]）
        summary: 场景简短描述（LLM 标注，1-2 句话）
        multi_score: 多维评分字典（LLM 标注，0-10 分制）
    """

    scene_id: int
    start: float
    end: float
    segment_ids: list[int] = field(default_factory=list)
    text: str = ""

    # LLM 标注结果
    scene_type: str = "Other"
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    multi_score: dict[str, float] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """场景时长（秒）"""
        return self.end - self.start

    @property
    def mid_point(self) -> float:
        """场景中间点时间（秒），用于封面截取等"""
        return (self.start + self.end) / 2

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "scene_id": self.scene_id,
            "start": self.start,
            "end": self.end,
            "duration": self.duration,
            "segment_ids": self.segment_ids,
            "text": self.text,
            "scene_type": self.scene_type,
            "tags": self.tags,
            "summary": self.summary,
            "multi_score": self.multi_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scene":
        """从字典构建 Scene"""
        return cls(
            scene_id=data["scene_id"],
            start=data["start"],
            end=data["end"],
            segment_ids=data.get("segment_ids", []),
            text=data.get("text", ""),
            scene_type=data.get("scene_type", "Other"),
            tags=data.get("tags", []),
            summary=data.get("summary", ""),
            multi_score=data.get("multi_score", {}),
        )

    @classmethod
    def from_segments(
        cls,
        segments: list[Any],  # list[Segment] — TYPE_CHECKING guard
        scene_id: int,
    ) -> "Scene":
        """从一组 Whisper segment 构建 Scene（未标注版本）

        Args:
            segments: Whisper Segment 对象列表（需有 segment_id, start, end, text 属性）
            scene_id: 场景编号
        """
        if not segments:
            raise ValueError("Cannot create Scene from empty segments")

        seg_ids = [getattr(s, "segment_id", i) for i, s in enumerate(segments)]
        text = " ".join(s.text for s in segments if s.text.strip())
        start = segments[0].start
        end = segments[-1].end

        return cls(
            scene_id=scene_id,
            start=start,
            end=end,
            segment_ids=seg_ids,
            text=text,
        )


# ===================================================================== #
# ClipCandidate — 剪辑候选
# ===================================================================== #

@dataclass
class ClipCandidate:
    """剪辑候选 — 由 Scene 经规则引擎筛选后生成

    ClipCandidate 是 Scene 经过 Score Engine 计算综合分后的产物，
    包含排序信息和选中状态。Filter Engine 对 ClipCandidate 进行
    去重、排序、数量控制等操作。

    Attributes:
        scene: 关联的 Scene 对象
        composite_score: 根据 preset 权重计算的综合分（0-10）
        rank: 排序位置（从 1 开始）
        selected: 是否被最终选中
    """

    scene: Scene
    composite_score: float = 0.0
    rank: int = 0
    selected: bool = False

    @property
    def scene_id(self) -> int:
        return self.scene.scene_id

    @property
    def start(self) -> float:
        return self.scene.start

    @property
    def end(self) -> float:
        return self.scene.end

    @property
    def duration(self) -> float:
        return self.scene.duration

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "scene": self.scene.to_dict(),
            "composite_score": self.composite_score,
            "rank": self.rank,
            "selected": self.selected,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClipCandidate":
        """从字典构建 ClipCandidate"""
        scene = Scene.from_dict(data["scene"])
        return cls(
            scene=scene,
            composite_score=data.get("composite_score", 0.0),
            rank=data.get("rank", 0),
            selected=data.get("selected", False),
        )


# ===================================================================== #
# ClipResult — 智能剪辑结果
# ===================================================================== #

@dataclass
class ClipResult:
    """智能剪辑引擎的完整输出结果

    包含所有候选片段和最终选中的片段列表。

    Attributes:
        all_candidates: 所有评分后的候选片段（按综合分排序）
        selected_candidates: 经过筛选后最终选中的片段
        total_duration: 选中片段的总时长（秒）
        preset: 使用的预设名称
        clip_mode: 使用的剪辑模式
    """

    all_candidates: list[ClipCandidate] = field(default_factory=list)
    selected_candidates: list[ClipCandidate] = field(default_factory=list)
    total_duration: float = 0.0
    preset: str = "viral"
    clip_mode: str = "all"

    @property
    def selected_count(self) -> int:
        return len(self.selected_candidates)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "all_candidates": [c.to_dict() for c in self.all_candidates],
            "selected_candidates": [c.to_dict() for c in self.selected_candidates],
            "total_duration": self.total_duration,
            "preset": self.preset,
            "clip_mode": self.clip_mode,
            "selected_count": self.selected_count,
        }

    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClipResult":
        """从字典构建 ClipResult"""
        all_candidates = [
            ClipCandidate.from_dict(c) for c in data.get("all_candidates", [])
        ]
        selected_candidates = [
            ClipCandidate.from_dict(c)
            for c in data.get("selected_candidates", [])
        ]
        return cls(
            all_candidates=all_candidates,
            selected_candidates=selected_candidates,
            total_duration=data.get("total_duration", 0.0),
            preset=data.get("preset", "viral"),
            clip_mode=data.get("clip_mode", "all"),
        )
