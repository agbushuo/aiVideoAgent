"""数据模型 (无重型依赖)

这些数据类不依赖 torch 或 whisper，可以在测试和轻量场景中使用。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
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

    def to_dict(self, include_words: bool = False) -> dict[str, Any]:
        """
        转换为字典。

        Args:
            include_words: 是否包含词级时间戳（默认不包含，减少体积）

        Returns:
            字典表示
        """
        data: dict[str, Any] = {
            "start": self.start,
            "end": self.end,
            "text": self.text,
        }
        if include_words and self.words:
            data["words"] = self.words
        return data

    def to_srt_block(self, index: int) -> str:
        """
        转换为单个 SRT 字幕块。

        Args:
            index: 字幕序号（从 1 开始）

        Returns:
            SRT 格式的字符串块
        """
        start_str = _seconds_to_srt_time(self.start)
        end_str = _seconds_to_srt_time(self.end)
        return f"{index}\n{start_str} --> {end_str}\n{self.text}"


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

    def to_dict(self, include_words: bool = False) -> dict[str, Any]:
        """
        转换为结构化字典。

        Args:
            include_words: 是否包含词级时间戳

        Returns:
            结构化字典，包含 language, duration, text, segments
        """
        return {
            "language": self.language,
            "duration": self.duration,
            "text": self.text,
            "segments": [seg.to_dict(include_words) for seg in self.segments],
        }

    def to_json(self, indent: int = 2, include_words: bool = False) -> str:
        """
        转换为 JSON 字符串。

        Args:
            indent: JSON 缩进空格数
            include_words: 是否包含词级时间戳

        Returns:
            JSON 字符串
        """
        return json.dumps(self.to_dict(include_words), ensure_ascii=False, indent=indent)

    def to_srt(self) -> str:
        """
        转换为完整的 SRT 字幕文本。

        Returns:
            SRT 格式的完整字符串
        """
        blocks = [seg.to_srt_block(i + 1) for i, seg in enumerate(self.segments)]
        return "\n\n".join(blocks) + "\n" if blocks else ""

    def export_json(
        self, output_path: str | Path, include_words: bool = False
    ) -> Path:
        """
        导出为 JSON 文件。

        Args:
            output_path: 输出文件路径
            include_words: 是否包含词级时间戳

        Returns:
            输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.to_json(include_words=include_words), encoding="utf-8")
        return output_path

    def export_srt(self, output_path: str | Path) -> Path:
        """
        导出为 SRT 字幕文件。

        Args:
            output_path: 输出文件路径

        Returns:
            输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.to_srt(), encoding="utf-8")
        return output_path

    @classmethod
    def from_json(cls, input_path: str | Path) -> "TranscriptResult":
        """
        从 JSON 文件加载转录结果。

        Args:
            input_path: JSON 文件路径

        Returns:
            TranscriptResult 对象
        """
        input_path = Path(input_path)
        data = json.loads(input_path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranscriptResult":
        """
        从字典构建转录结果。

        Args:
            data: 包含 language, segments, text, duration 的字典

        Returns:
            TranscriptResult 对象
        """
        segments = []
        for seg in data.get("segments", []):
            segments.append(
                Segment(
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"],
                    words=seg.get("words", []),
                )
            )
        return cls(
            language=data.get("language", "unknown"),
            segments=segments,
            text=data.get("text", ""),
            duration=data.get("duration", 0.0),
        )


def _seconds_to_srt_time(seconds: float) -> str:
    """秒数转 SRT 时间格式 (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = round((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
