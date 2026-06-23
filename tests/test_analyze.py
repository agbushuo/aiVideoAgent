"""LLMAnalyzer 测试"""

import json
from unittest.mock import patch
import pytest

from src.analyze.llm_analyzer import (
    LLMAnalyzer,
    AnalysisReport,
    Highlight,
)
from src.transcribe.models import TranscriptResult, Segment


def test_highlight_creation():
    """测试 Highlight 创建"""
    h = Highlight(
        segment_id=5,
        start=10.0,
        end=30.0,
        title="测试亮点",
        reason="这是一个测试",
        score=0.85,
    )
    assert h.segment_id == 5
    assert h.score == 0.85


def test_analysis_report():
    """测试 AnalysisReport 创建"""
    report = AnalysisReport(
        summary="测试总结",
        highlights=[
            Highlight(0, 0.0, 10.0, "亮点1", "原因1", 0.9),
            Highlight(1, 10.0, 20.0, "亮点2", "原因2", 0.7),
        ],
        language="zh",
        duration=120.0,
        model="test-model",
        analyzed_at="2026-06-22T10:00:00",
    )

    assert len(report.highlights) == 2
    assert report.highlights[0].score > report.highlights[1].score


def test_build_transcript_text():
    """测试构建字幕文本"""
    transcript = TranscriptResult(
        language="zh",
        segments=[
            Segment(0.0, 5.0, "第一段字幕"),
            Segment(5.0, 10.0, "第二段字幕"),
        ],
        text="完整文本",
    )

    analyzer = LLMAnalyzer()
    text = analyzer._build_transcript_text(transcript)

    assert "#0:" in text
    assert "#1:" in text
    assert "第一段字幕" in text
    assert "[0.0s-5.0s]" in text


def test_parse_llm_response_clean():
    """测试解析干净的 JSON 响应"""
    analyzer = LLMAnalyzer()
    response = json.dumps({
        "summary": "测试总结",
        "highlights": [
            {
                "segment_id": 0,
                "start": 0.0,
                "end": 10.0,
                "title": "测试",
                "reason": "测试原因",
                "score": 0.9,
            }
        ],
    })

    data = analyzer._parse_llm_response(response)
    assert data["summary"] == "测试总结"
    assert len(data["highlights"]) == 1


def test_parse_llm_response_with_markdown():
    """测试解析带 markdown 代码块的响应"""
    analyzer = LLMAnalyzer()
    response = (
        "```json\n"
        "{\n"
        '  "summary": "测试总结",\n'
        '  "highlights": []\n'
        "}\n"
        "```"
    )

    data = analyzer._parse_llm_response(response)
    assert data["summary"] == "测试总结"


def test_estimate_tokens():
    """测试 token 估算"""
    chinese = "这是一个测试字符串"
    tokens = LLMAnalyzer._estimate_tokens(chinese)
    assert 10 <= tokens <= 30

    english = "hello world test"
    tokens = LLMAnalyzer._estimate_tokens(english)
    assert 2 <= tokens <= 10


def test_check_response_truncated():
    """测试截断检测"""
    analyzer = LLMAnalyzer()

    assert not analyzer._check_response_truncated('{"a": 1}')
    assert not analyzer._check_response_truncated('{"a": [1, 2]}')

    assert analyzer._check_response_truncated('{"a": {')
    assert analyzer._check_response_truncated('{"a": [')


def test_parse_truncated_response():
    """测试解析被截断的响应"""
    analyzer = LLMAnalyzer()
    response = (
        '{"summary": "测试总结", "highlights": ['
        '{"segment_id": 0, "start": 0.0, "end": 10.0, '
        '"title": "测试", "reason": "原因", "score": 0.9}'
    )

    data = analyzer._parse_llm_response(response)
    assert data.get("summary") == "测试总结"
    assert len(data.get("highlights", [])) >= 1


def test_analyze_full_flow_with_mock():
    """测试完整的 analyze 流程 (mock LLM 调用)"""
    transcript = TranscriptResult(
        language="zh",
        segments=[
            Segment(0.0, 5.0, "开场白"),
            Segment(5.0, 15.0, "核心观点阐述"),
            Segment(15.0, 25.0, "案例演示"),
            Segment(25.0, 30.0, "总结"),
        ],
        text="完整文本",
        duration=30.0,
    )

    analyzer = LLMAnalyzer()

    mock_response = json.dumps({
        "summary": "这是一个测试视频",
        "highlights": [
            {
                "segment_id": 1,
                "start": 5.0,
                "end": 15.0,
                "title": "核心观点",
                "reason": "最重要的内容",
                "score": 0.95,
            },
            {
                "segment_id": 2,
                "start": 15.0,
                "end": 25.0,
                "title": "案例演示",
                "reason": "很直观的演示",
                "score": 0.8,
            },
        ],
    })

    with patch.object(analyzer, "_call_llm") as mock_call:
        mock_call.return_value = mock_response
        report = analyzer.analyze(transcript)

    assert report.summary == "这是一个测试视频"
    assert len(report.highlights) == 2
    assert report.highlights[0].score == 0.95
    assert report.highlights[1].score == 0.8
    assert report.language == "zh"
    assert report.duration == 30.0


def test_analyze_with_empty_llm_response():
    """测试 LLM 返回空响应时的行为"""
    transcript = TranscriptResult(
        language="zh",
        segments=[Segment(0.0, 5.0, "测试")],
        text="测试",
        duration=5.0,
    )

    analyzer = LLMAnalyzer()

    with patch.object(analyzer, "_call_llm") as mock_call:
        mock_call.return_value = '{"summary": "", "highlights": []}'
        report = analyzer.analyze(transcript)

    assert report.summary == ""
    assert len(report.highlights) == 0


def test_analyze_skips_invalid_segment_id():
    """测试跳过超出范围的 segment_id"""
    transcript = TranscriptResult(
        language="zh",
        segments=[
            Segment(0.0, 5.0, "第一段"),
            Segment(5.0, 10.0, "第二段"),
        ],
        text="测试",
        duration=10.0,
    )

    analyzer = LLMAnalyzer()

    with patch.object(analyzer, "_call_llm") as mock_call:
        mock_call.return_value = json.dumps({
            "summary": "测试总结",
            "highlights": [
                {
                    "segment_id": 0,
                    "start": 0.0,
                    "end": 5.0,
                    "title": "有效的亮点",
                    "reason": "原因",
                    "score": 0.9,
                },
                {
                    "segment_id": 99,
                    "start": 0.0,
                    "end": 5.0,
                    "title": "无效的亮点",
                    "reason": "segment_id 超出范围",
                    "score": 0.8,
                },
            ],
        })
        report = analyzer.analyze(transcript)

    assert len(report.highlights) == 1
    assert report.highlights[0].segment_id == 0


def test_analyze_clamps_times_to_max():
    """测试时间被限制在视频最大时长内"""
    transcript = TranscriptResult(
        language="zh",
        segments=[Segment(0.0, 10.0, "测试")],
        text="测试",
        duration=10.0,
    )

    analyzer = LLMAnalyzer()

    with patch.object(analyzer, "_call_llm") as mock_call:
        mock_call.return_value = json.dumps({
            "summary": "测试总结",
            "highlights": [
                {
                    "segment_id": 0,
                    "start": 0.0,
                    "end": 999.0,
                    "title": "测试",
                    "reason": "原因",
                    "score": 0.9,
                }
            ],
        })
        report = analyzer.analyze(transcript)

    assert report.highlights[0].end == 10.0


def test_build_transcript_text_compact():
    """测试截断版字幕文本构建"""
    segments = [
        Segment(i * 2.0, (i + 1) * 2.0, f"第{i}段")
        for i in range(100)
    ]
    transcript = TranscriptResult(
        language="zh",
        segments=segments,
        text="",
    )

    analyzer = LLMAnalyzer()
    compact = analyzer._build_transcript_text_compact(
        transcript, max_segments=40
    )

    assert "省略了" in compact
    assert "#0:" in compact
    assert "#99:" in compact


def test_analyze_long_transcript_triggers_compact():
    """测试超长字幕自动触发截断"""
    segments = [
        Segment(
            i * 2.0, (i + 1) * 2.0,
            "这是一段比较长的字幕内容用于测试"
        )
        for i in range(500)
    ]
    transcript = TranscriptResult(
        language="zh",
        segments=segments,
        text="",
        duration=1000.0,
    )

    analyzer = LLMAnalyzer(context_size=4096, max_tokens=2048)

    with patch.object(analyzer, "_call_llm") as mock_call:
        mock_call.return_value = json.dumps({
            "summary": "测试总结",
            "highlights": [],
        })
        report = analyzer.analyze(transcript)

    assert report.summary == "测试总结"
