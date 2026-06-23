"""文件 I/O 工具

处理 SRT 字幕、JSON 转录结果、分析报告的读写。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.analyze.llm_analyzer import AnalysisReport, Highlight
from src.transcribe.models import Segment, TranscriptResult


def _seconds_to_srt_time(seconds: float) -> str:
    """秒数转 SRT 时间格式 (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def export_srt(transcript: TranscriptResult, output_path: str | Path) -> Path:
    """
    导出 SRT 字幕文件

    Args:
        transcript: 转录结果
        output_path: 输出路径

    Returns:
        输出文件路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for i, seg in enumerate(transcript.segments, 1):
        start_time = _seconds_to_srt_time(seg.start)
        end_time = _seconds_to_srt_time(seg.end)
        lines.append(f"{i}")
        lines.append(f"{start_time} --> {end_time}")
        lines.append(seg.text)
        lines.append("")  # 空行分隔

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def export_transcript_json(
    transcript: TranscriptResult, output_path: str | Path
) -> Path:
    """
    导出转录结果为 JSON

    Args:
        transcript: 转录结果
        output_path: 输出路径

    Returns:
        输出文件路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "language": transcript.language,
        "duration": transcript.duration,
        "text": transcript.text,
        "segments": [
            {
                "id": i,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
            }
            for i, seg in enumerate(transcript.segments)
        ],
    }

    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


def load_transcript_json(input_path: str | Path) -> TranscriptResult:
    """
    从 JSON 文件加载转录结果

    Args:
        input_path: JSON 文件路径

    Returns:
        TranscriptResult
    """
    input_path = Path(input_path)
    data = json.loads(input_path.read_text(encoding="utf-8"))

    segments = [
        Segment(
            start=seg["start"],
            end=seg["end"],
            text=seg["text"],
        )
        for seg in data["segments"]
    ]

    return TranscriptResult(
        language=data.get("language", "unknown"),
        segments=segments,
        text=data.get("text", ""),
        duration=data.get("duration", 0.0),
    )


def export_analysis_json(report: AnalysisReport, output_path: str | Path) -> Path:
    """
    导出分析报告为 JSON

    Args:
        report: 分析报告
        output_path: 输出路径

    Returns:
        输出文件路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "video_path": report.video_path,
        "summary": report.summary,
        "highlights": [
            {
                "segment_id": h.segment_id,
                "start": h.start,
                "end": h.end,
                "title": h.title,
                "reason": h.reason,
                "score": h.score,
            }
            for h in report.highlights
        ],
        "metadata": {
            "language": report.language,
            "duration": report.duration,
            "model": report.model,
            "analyzed_at": report.analyzed_at,
        },
    }

    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


def load_analysis_json(input_path: str | Path) -> AnalysisReport:
    """
    从 JSON 文件加载分析报告

    Args:
        input_path: 分析报告 JSON 文件路径

    Returns:
        AnalysisReport

    Example:
        >>> report = load_analysis_json("outputs/reports/testvideo.json")
        >>> print(report.summary)
        >>> for h in report.highlights:
        ...     print(f"{h.title}: {h.start:.1f}s - {h.end:.1f}s")
    """
    input_path = Path(input_path)
    data = json.loads(input_path.read_text(encoding="utf-8"))

    highlights = []
    for h in data.get("highlights", []):
        highlights.append(
            Highlight(
                segment_id=h.get("segment_id", 0),
                start=h.get("start", 0.0),
                end=h.get("end", 0.0),
                title=h.get("title", ""),
                reason=h.get("reason", ""),
                score=float(h.get("score", 0.5)),
            )
        )

    metadata = data.get("metadata", {})

    return AnalysisReport(
        summary=data.get("summary", ""),
        highlights=highlights,
        video_path=data.get("video_path", ""),
        language=metadata.get("language", ""),
        duration=metadata.get("duration", 0.0),
        model=metadata.get("model", ""),
        analyzed_at=metadata.get("analyzed_at", ""),
    )


def export_markdown_report(report: AnalysisReport, output_path: str | Path) -> Path:
    """
    导出分析报告为 Markdown

    Args:
        report: 分析报告
        output_path: 输出路径

    Returns:
        输出文件路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# 视频分析报告",
        "",
        f"> 分析时间: {report.analyzed_at}",
        f"> 模型: {report.model}",
        "",
        "## 概要",
        "",
        report.summary,
        "",
        "## 亮点片段",
        "",
    ]

    for i, h in enumerate(report.highlights, 1):
        start_str = _format_duration(h.start)
        end_str = _format_duration(h.end)
        stars = "⭐" * round(h.score)

        lines.extend([
            f"### {i}. {h.title} ({start_str} - {end_str}) {stars}",
            "",
            f"**评分**: {h.score:.2f}",
            "",
            f"**为什么值得剪**: {h.reason}",
            "",
        ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _format_duration(seconds: float) -> str:
    """格式化时长为 MM:SS"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"
