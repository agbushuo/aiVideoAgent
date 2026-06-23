"""数据模型 (无重型依赖)

这些数据类不依赖 torch 或 whisper，可以在测试和轻量场景中使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Segment:
    """字幕片段"""
    start: float
    end: float
    text: str
    words: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_whisper_segment(cls, seg: dict[str, Any]) -> "Segment":
        return cls(
            start=seg["start"],
            end=seg["end"],
            text=seg["text"].strip(),
            words=seg.get("words", []),
        )


@dataclass
class TranscriptResult:
    """转录结果"""
    language: str
    segments: list[Segment]
    text: str
    duration: float = 0.0

    @classmethod
    def from_whisper_result(
        cls, result: dict[str, Any], duration: float = 0.0
    ) -> "TranscriptResult":
        segments = [Segment.from_whisper_segment(seg) for seg in result["segments"]]
        return cls(
            language=result.get("language", "unknown"),
            segments=segments,
            text=result.get("text", ""),
            duration=duration,
        )
