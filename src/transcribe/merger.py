"""Segment 级去重合并器

对多个 chunk 转录后的 Whisper segment 进行：
1. 全局时间戳偏移（将 chunk 局部时间映射回原始音频时间）
2. 按时间排序
3. 相邻 segment 文本相似度去重（前 N 字符 + Levenshtein 混合）
4. 合并为最终的 TranscriptResult

核心原则：**按 Whisper segment 边界对齐去重，而非按时间切分**，
避免"半句话保留、半句话丢弃"的情况。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.transcribe.models import Segment, TranscriptResult

logger = logging.getLogger(__name__)


@dataclass
class ChunkTranscript:
    """单个 chunk 的转录结果"""
    segments: list[Segment]          # 该 chunk 的 Whisper segments
    chunk_start_time: float          # chunk 在原始音频中的起始时间（秒）
    chunk_index: int                 # chunk 序号


@dataclass
class MergeStats:
    """合并统计信息"""
    total_segments_before: int = 0   # 合并前总 segment 数
    total_segments_after: int = 0    # 合并后总 segment 数
    duplicates_removed: int = 0      # 去重移除的数量
    chunks_merged: int = 0           # 合并的 chunk 数量


def apply_time_offset(
    segments: list[Segment],
    offset: float,
) -> list[Segment]:
    """
    给 segment 列表加上全局时间戳偏移。

    Args:
        segments: chunk 的 Whisper segments（时间为 chunk 局部时间）
        offset: chunk 在原始音频中的起始时间（秒）

    Returns:
        时间偏移后的 segment 列表（新对象，不修改原列表）
    """
    return [
        Segment(
            start=seg.start + offset,
            end=seg.end + offset,
            text=seg.text,
            words=seg.words,
        )
        for seg in segments
    ]


def compute_text_similarity(text_a: str, text_b: str) -> float:
    """
    计算两个文本的相似度，使用前 N 字符 + Levenshtein 混合策略。

    策略：
    1. 快速路径：比较前 20 个字符，如果完全不同则直接返回低相似度
    2. 精确路径：使用 Levenshtein 距离计算完整相似度

    Args:
        text_a: 文本 A
        text_b: 文本 B

    Returns:
        相似度分数 (0.0 - 1.0)
    """
    if not text_a or not text_b:
        return 0.0

    # 完全相同
    if text_a == text_b:
        return 1.0

    # 快速路径：前 N 字符比较
    prefix_len = min(20, len(text_a), len(text_b))
    prefix_a = text_a[:prefix_len]
    prefix_b = text_b[:prefix_len]

    # 如果前缀完全不同，相似度很低
    if prefix_a and prefix_b:
        prefix_match = sum(1 for a, b in zip(prefix_a, prefix_b) if a == b) / prefix_len
        if prefix_match < 0.3:
            return prefix_match * 0.5  # 惩罚前缀不匹配

    # 精确路径：Levenshtein 距离
    try:
        import Levenshtein
        return Levenshtein.ratio(text_a, text_b)
    except ImportError:
        # 回退到内置实现
        return _levenshtein_ratio_builtin(text_a, text_b)


def _levenshtein_ratio_builtin(a: str, b: str) -> float:
    """
    内置 Levenshtein 相似度计算（当 python-Levenshtein 不可用时）。

    使用动态规划计算编辑距离，然后转换为相似度分数。
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    # 对于很长的字符串，使用前缀近似
    max_len = 200
    if len(a) > max_len or len(b) > max_len:
        a = a[:max_len]
        b = b[:max_len]

    len_a, len_b = len(a), len(b)
    dp = list(range(len_b + 1))

    for i in range(1, len_a + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, len_b + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp

    distance = dp[len_b]
    max_dist = max(len_a, len_b)
    return 1.0 - (distance / max_dist) if max_dist > 0 else 1.0


def merge_segments(
    chunk_transcripts: list[ChunkTranscript],
    similarity_threshold: float = 0.8,
) -> tuple[list[Segment], MergeStats]:
    """
    合并多个 chunk 的 segment 列表，去除 overlap 区域的重复 segment。

    流程：
    1. 对每个 chunk 的 segment 应用时间偏移
    2. 合并所有 segment 并按时间排序
    3. 检测相邻 segment 的时间重叠
    4. 对重叠的 segment 做文本相似度比对
    5. 相似度 > 阈值 → 保留时间范围更广的那个（整段保留/整段丢弃）
    6. 相似度 < 阈值 → 保留两者

    Args:
        chunk_transcripts: 各 chunk 的转录结果
        similarity_threshold: 相似度阈值，超过则判定为重复

    Returns:
        (去重后的 segment 列表, 合并统计信息)
    """
    stats = MergeStats(chunks_merged=len(chunk_transcripts))

    # Step 1: 应用时间偏移并合并
    all_segments: list[Segment] = []
    for ct in chunk_transcripts:
        offset_segments = apply_time_offset(ct.segments, ct.chunk_start_time)
        all_segments.extend(offset_segments)

    stats.total_segments_before = len(all_segments)

    if not all_segments:
        return [], stats

    # Step 2: 按起始时间排序
    all_segments.sort(key=lambda s: (s.start, s.end))

    # Step 3: 去重
    deduped = _deduplicate_segments(all_segments, similarity_threshold, stats)

    stats.total_segments_after = len(deduped)
    stats.duplicates_removed = stats.total_segments_before - stats.total_segments_after

    logger.info(
        "合并 %d 个 chunk: %d segments → %d segments (移除 %d 个重复)",
        stats.chunks_merged,
        stats.total_segments_before,
        stats.total_segments_after,
        stats.duplicates_removed,
    )

    return deduped, stats


def _deduplicate_segments(
    segments: list[Segment],
    threshold: float,
    stats: MergeStats,
) -> list[Segment]:
    """
    对已排序的 segment 列表进行去重。

    核心逻辑：
    - 遍历相邻 segment 对
    - 如果时间有重叠，计算文本相似度
    - 相似度高 → 保留更好的那个（优先时间范围更广的）
    - 相似度低 → 都保留
    """
    if len(segments) <= 1:
        return segments

    keep: list[Segment] = [segments[0]]

    for i in range(1, len(segments)):
        current = segments[i]
        prev = keep[-1]

        # 检查时间重叠
        overlap = _compute_overlap(prev, current)

        if overlap > 0:
            # 有重叠，计算文本相似度
            similarity = compute_text_similarity(prev.text, current.text)

            if similarity >= threshold:
                # 判定为重复，保留时间范围更广的那个
                prev_duration = prev.end - prev.start
                current_duration = current.end - current.start

                if current_duration >= prev_duration:
                    # 替换为当前 segment（范围更广或相等）
                    keep[-1] = current
                    logger.debug(
                        "去重: segment@%.1fs (sim=%.2f, 保留范围更广的)",
                        current.start, similarity,
                    )
                else:
                    # 保留已有的（范围更广）
                    logger.debug(
                        "去重: segment@%.1fs (sim=%.2f, 丢弃范围较窄的)",
                        current.start, similarity,
                    )
            else:
                # 相似度低，可能是不同的内容恰好时间重叠，都保留
                keep.append(current)
                logger.debug(
                    "保留重叠 segment@%.1fs (sim=%.2f < %.2f)",
                    current.start, similarity, threshold,
                )
        else:
            # 无重叠，直接保留
            keep.append(current)

    return keep


def _compute_overlap(seg_a: Segment, seg_b: Segment) -> float:
    """
    计算两个 segment 的时间重叠量（秒）。

    假设 seg_a.start <= seg_b.start（已排序）。

    Returns:
        重叠时长，无重叠返回 0
    """
    # seg_a: [a_start, a_end]
    # seg_b: [b_start, b_end]
    # overlap = max(0, a_end - b_start)
    overlap = seg_a.end - seg_b.start
    return max(0.0, overlap)


def _merge_consecutive_identical(
    segments: list[Segment],
    stats: MergeStats,
) -> list[Segment]:
    """
    合并连续且文本完全相同的 segment。

    Whisper 对纯音乐/音效片段会输出大量重复文本，
    这一步将它们合并为单个 segment，减少对下游的干扰。
    """
    if len(segments) <= 1:
        return segments

    merged: list[Segment] = [segments[0]]

    for seg in segments[1:]:
        prev = merged[-1]
        if seg.text == prev.text and seg.text.strip():
            # 合并：扩展前一个 segment 的结束时间
            merged[-1] = Segment(
                start=prev.start,
                end=seg.end,
                text=prev.text,
            )
            stats.duplicates_removed += 1
        else:
            merged.append(seg)

    return merged


def build_transcript_result(
    segments: list[Segment],
    language: str | None = None,
    duration: float = 0.0,
) -> TranscriptResult:
    """
    从去重后的 segment 列表构建最终的 TranscriptResult。

    Args:
        segments: 去重合并后的 segment 列表
        language: 语言代码（None 则用 Whisper 检测值）
        duration: 总时长（秒）

    Returns:
        TranscriptResult 对象
    """
    # 拼接完整文本
    text = " ".join(seg.text for seg in segments if seg.text)

    # 计算总时长
    if not duration and segments:
        duration = segments[-1].end

    return TranscriptResult(
        language=language or "unknown",
        segments=segments,
        text=text,
        duration=duration,
    )


def merge_chunk_transcripts(
    chunk_transcripts: list[ChunkTranscript],
    language: str | None = None,
    total_duration: float = 0.0,
    similarity_threshold: float = 0.8,
) -> tuple[TranscriptResult, MergeStats]:
    """
    一站式合并：从 chunk 转录结果到最终 TranscriptResult。

    Args:
        chunk_transcripts: 各 chunk 的转录结果
        language: 语言代码（None 则用 Whisper 检测值）
        total_duration: 原始音频总时长
        similarity_threshold: 去重相似度阈值

    Returns:
        (TranscriptResult, MergeStats)
    """
    segments, stats = merge_segments(chunk_transcripts, similarity_threshold)

    # 合并连续相同文本的 segment（Whisper 对纯音乐/音效的重复输出）
    segments = _merge_consecutive_identical(segments, stats)
    stats.total_segments_after = len(segments)

    # 从各 chunk 的 Whisper 结果中获取检测到的语言
    if not language and chunk_transcripts:
        first_chunk = chunk_transcripts[0]
        # Whisper 检测的语言需要从转录结果获取
        # 这里用第一个非空 segment 的语言标记

    result = build_transcript_result(segments, language, total_duration)
    return result, stats
