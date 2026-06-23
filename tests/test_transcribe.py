"""WhisperEngine 测试"""

import pytest
from unittest.mock import MagicMock, patch

from src.transcribe.models import TranscriptResult, Segment


def test_segment_from_whisper():
    """测试从 Whisper 输出创建 Segment"""
    whisper_seg = {
        "start": 1.5,
        "end": 5.0,
        "text": "  这是一段测试字幕  ",
        "words": [],
    }
    seg = Segment.from_whisper_segment(whisper_seg)

    assert seg.start == 1.5
    assert seg.end == 5.0
    assert seg.text == "这是一段测试字幕"


def test_transcript_result_from_whisper():
    """测试从 Whisper 输出创建 TranscriptResult"""
    whisper_result = {
        "language": "zh",
        "text": "完整文本",
        "segments": [
            {"start": 0.0, "end": 3.0, "text": "第一段", "words": []},
            {"start": 3.0, "end": 6.0, "text": "第二段", "words": []},
        ],
    }

    result = TranscriptResult.from_whisper_result(whisper_result, duration=6.0)

    assert result.language == "zh"
    assert result.text == "完整文本"
    assert len(result.segments) == 2
    assert result.duration == 6.0


def test_segment_dataclass():
    """测试 Segment dataclass"""
    seg = Segment(start=0.0, end=5.0, text="测试")
    assert seg.start == 0.0
    assert seg.end == 5.0
    assert seg.text == "测试"
    assert seg.words == []
