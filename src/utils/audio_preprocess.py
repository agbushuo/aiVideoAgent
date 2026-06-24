"""音频预处理工具

使用 FFmpeg 将视频转换为 Whisper 最优格式的音频：
- 16kHz 采样率
- 单声道 (mono)
- WAV 格式（无损，适合 Whisper）
- 可选响度归一化（提升噪声视频质量）

同时提供音频时长检测、chunk 切分等功能。
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AudioChunk:
    """音频 chunk 信息"""
    path: Path                    # chunk WAV 文件路径
    start_time: float             # 在原音频中的起始时间（秒）
    end_time: float               # 在原音频中的结束时间（秒）
    duration: float               # chunk 实际时长（秒）
    chunk_index: int              # chunk 序号（从 0 开始）


@dataclass
class AudioPreprocessResult:
    """音频预处理结果"""
    audio_path: Path              # 预处理后的 WAV 文件路径
    duration: float               # 音频总时长（秒）
    sample_rate: int              # 采样率 (Hz)
    channels: int                 # 声道数
    needs_chunking: bool          # 是否需要分段处理
    estimated_chunks: int         # 预估 chunk 数量（0 表示不分段）
    temp_files: list[Path]        # 所有临时文件（用于清理）


def extract_audio(
    input_path: str | Path,
    output_path: str | Path | None = None,
    sample_rate: int = 16000,
    channels: int = 1,
    ffmpeg_path: str = "ffmpeg",
) -> Path:
    """
    从视频文件提取音频，转换为 Whisper 最优格式。

    Args:
        input_path: 输入视频/音频文件路径
        output_path: 输出 WAV 路径（None 则自动生成临时文件）
        sample_rate: 采样率（Whisper 需要 16kHz）
        channels: 声道数（1=mono, 2=stereo）
        ffmpeg_path: ffmpeg 可执行文件路径

    Returns:
        输出的 WAV 文件路径

    Raises:
        RuntimeError: ffmpeg 执行失败
        FileNotFoundError: 输入文件不存在
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    if output_path is None:
        suffix = f"_{sample_rate}kHz_{channels}ch.wav"
        output_path = input_path.with_suffix(suffix)
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg_path,
        "-y",
        "-i", str(input_path),
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-f", "wav",
        str(output_path),
    ]

    logger.info("提取音频: %s -> %s", input_path, output_path)
    _run_ffmpeg(cmd)

    return output_path


def loudness_normalize(
    input_path: str | Path,
    output_path: str | Path | None = None,
    target_loudness: float = -24.0,
    ffmpeg_path: str = "ffmpeg",
) -> Path:
    """
    对音频进行响度归一化（EBU R128 标准）。

    使用两遍编码：第一遍分析响度，第二遍应用归一化。
    适合噪声较大或音量不一致的视频。

    Args:
        input_path: 输入音频文件路径
        output_path: 输出路径（None 则在原文件旁生成 normalized_*.wav）
        target_loudness: 目标响度（dB LUFS，默认 -24，广播标准）
        ffmpeg_path: ffmpeg 可执行文件路径

    Returns:
        输出的 WAV 文件路径
    """
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.parent / f"normalized_{input_path.name}"
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 第一遍：测量响度
    measure_cmd = [
        ffmpeg_path,
        "-i", str(input_path),
        "-af", f"loudnorm=I={target_loudness}:print_format=json",
        "-f", "null",
        "-",
    ]

    result = subprocess.run(
        measure_cmd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )

    # 从 stderr 末尾提取 JSON
    stderr_text = result.stderr if result.stderr else ""
    json_start = stderr_text.rfind("{")
    json_end = stderr_text.rfind("}") + 1
    if json_start < 0 or json_end <= json_start:
        logger.warning("响度测量未返回 JSON，跳过归一化")
        # 直接复制
        copy_cmd = [
            ffmpeg_path, "-y", "-i", str(input_path),
            "-f", "wav", str(output_path),
        ]
        _run_ffmpeg(copy_cmd)
        return output_path

    json_str = stderr_text[json_start:json_end]
    try:
        import json
        data = json.loads(json_str)
        input_i = data.get("input_i", target_loudness)
        input_tp = data.get("input_tp", "0")
        input_lra = data.get("input_lra", "0")
        target_offset = data.get("target_offset", "0")

        # 第二遍：应用归一化
        normalize_cmd = [
            ffmpeg_path,
            "-y",
            "-i", str(input_path),
            "-af", (
                f"loudnorm=I={target_loudness}:"
                f"T={target_offset}:"
                f"measured_I={input_i}:"
                f"measured_TP={input_tp}:"
                f"measured_LRA={input_lra}:"
                f"linear=true"
            ),
            "-f", "wav",
            str(output_path),
        ]
        _run_ffmpeg(normalize_cmd)
        logger.info("响度归一化完成: %.1f -> %.1f dB LUFS", input_i, target_loudness)

    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("响度归一化解析失败 (%s)，直接复制", e)
        copy_cmd = [
            ffmpeg_path, "-y", "-i", str(input_path),
            "-f", "wav", str(output_path),
        ]
        _run_ffmpeg(copy_cmd)

    return output_path


def get_audio_duration(
    input_path: str | Path,
    ffprobe_path: str = "ffprobe",
) -> float:
    """
    使用 ffprobe 获取音频时长。

    Args:
        input_path: 音频/视频文件路径
        ffprobe_path: ffprobe 可执行文件路径

    Returns:
        音频时长（秒）
    """
    import json

    input_path = Path(input_path)
    cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(input_path),
    ]
    result = subprocess.run(
        cmd, capture_output=True, encoding="utf-8", errors="replace", check=True
    )
    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 0))


def chunk_audio(
    input_path: str | Path,
    chunk_duration: float = 900.0,
    overlap: float = 10.0,
    temp_dir: str | Path | None = None,
    ffmpeg_path: str = "ffmpeg",
    ffprobe_path: str = "ffprobe",
) -> list[AudioChunk]:
    """
    将音频按固定时长切分为多个 chunk，相邻 chunk 之间有 overlap。

    Args:
        input_path: 输入 WAV 文件路径
        chunk_duration: 每个 chunk 的时长（秒），默认 15 分钟
        overlap: 相邻 chunk 之间的重叠时长（秒），默认 10 秒
        temp_dir: 临时目录（None 则使用系统临时目录）
        ffmpeg_path: ffmpeg 可执行文件路径
        ffprobe_path: ffprobe 可执行文件路径

    Returns:
        AudioChunk 列表，按时间顺序排列
    """
    input_path = Path(input_path)
    total_duration = get_audio_duration(input_path, ffprobe_path)

    # 计算 chunk 边界
    boundaries = _compute_chunk_boundaries(
        total_duration, chunk_duration, overlap
    )

    if not boundaries:
        return []

    # 创建临时目录
    if temp_dir is None:
        temp_dir_obj = Path(tempfile.mkdtemp(prefix="va_chunk_"))
        owned_temp_dir = True
    else:
        temp_dir_obj = Path(temp_dir)
        owned_temp_dir = False
    temp_dir_obj.mkdir(parents=True, exist_ok=True)

    chunks = []
    for i, (start, end) in enumerate(boundaries):
        chunk_path = temp_dir_obj / f"chunk_{i:04d}.wav"
        duration = end - start

        cmd = [
            ffmpeg_path,
            "-y",
            "-ss", str(start),
            "-i", str(input_path),
            "-t", str(duration),
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            str(chunk_path),
        ]
        _run_ffmpeg(cmd)

        chunks.append(AudioChunk(
            path=chunk_path,
            start_time=start,
            end_time=end,
            duration=duration,
            chunk_index=i,
        ))

    logger.info(
        "音频切分为 %d 个 chunk (每段 %.1fs, overlap %.1fs)",
        len(chunks), chunk_duration, overlap,
    )

    return chunks


def should_segment_transcribe(
    audio_duration: float,
    gpu_memory_gb: float | None = None,
    segment_threshold_minutes: float = 30.0,
) -> bool:
    """
    根据 GPU 显存和视频时长判断是否需要分段转录。

    判断逻辑：
    1. 如果 GPU 显存 < 8GB，阈值降至 20 分钟
    2. 如果 GPU 显存 8-16GB，阈值升至 60 分钟
    3. 如果无法检测 GPU 显存，使用默认阈值（30 分钟）
    4. 短视频（< 5 分钟）永远不分段

    Args:
        audio_duration: 音频时长（秒）
        gpu_memory_gb: GPU 显存大小（GB），None 则自动检测
        segment_threshold_minutes: 分段阈值（分钟），默认 30 分钟

    Returns:
        True 表示需要分段转录
    """
    # 极短视频永远不分段
    if audio_duration < 300:  # 5 分钟
        return False

    # 尝试检测 GPU 显存
    if gpu_memory_gb is None:
        gpu_memory_gb = _detect_gpu_memory()

    # 根据显存调整阈值
    if gpu_memory_gb is not None and gpu_memory_gb < 8:
        # 显存较小，降低阈值到 20 分钟
        threshold_seconds = 20.0 * 60
    elif gpu_memory_gb is not None and gpu_memory_gb < 16:
        # 中等显存，升高阈值到 60 分钟
        threshold_seconds = 60.0 * 60
    else:
        # 默认阈值或大显存
        threshold_seconds = segment_threshold_minutes * 60

    return audio_duration > threshold_seconds


def preprocess_audio_for_transcribe(
    input_path: str | Path,
    *,
    ffmpeg_path: str = "ffmpeg",
    ffprobe_path: str = "ffprobe",
    normalize_loudness: bool = False,
    chunk_duration: float = 900.0,
    overlap: float = 10.0,
    segment_threshold_minutes: float = 30.0,
    gpu_memory_gb: float | None = None,
    output_dir: str | Path | None = None,
) -> AudioPreprocessResult:
    """
    完整的音频预处理流水线，为分段转录做准备。

    流程：
    1. 提取音频 → 16kHz mono WAV
    2. (可选) 响度归一化
    3. 检测时长，判断是否需要分段
    4. 如果需要，切分为 chunks

    Args:
        input_path: 输入视频/音频文件
        ffmpeg_path: ffmpeg 路径
        ffprobe_path: ffprobe 路径
        normalize_loudness: 是否进行响度归一化
        chunk_duration: chunk 时长（秒）
        overlap: overlap 时长（秒）
        segment_threshold_minutes: 分段阈值（分钟）
        gpu_memory_gb: GPU 显存（GB），None 则自动检测
        output_dir: 输出目录（None 则在输入文件旁创建）

    Returns:
        AudioPreprocessResult: 包含处理后的音频路径和 chunk 信息
    """
    input_path = Path(input_path)
    temp_files: list[Path] = []

    # 确定输出目录
    if output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: 提取音频
    audio_name = f"{input_path.stem}_audio.wav"
    audio_path = output_dir / audio_name
    extract_audio(input_path, audio_path, ffmpeg_path=ffmpeg_path)
    temp_files.append(audio_path)

    # Step 2: 响度归一化（可选）
    if normalize_loudness:
        normalized_path = output_dir / f"{input_path.stem}_normalized.wav"
        loudness_normalize(audio_path, normalized_path, ffmpeg_path=ffmpeg_path)
        temp_files.append(normalized_path)
        audio_path = normalized_path

    # Step 3: 获取时长
    duration = get_audio_duration(audio_path, ffprobe_path)

    # Step 4: 判断是否需要分段
    needs_chunking = should_segment_transcribe(
        duration, gpu_memory_gb, segment_threshold_minutes
    )

    # 估算 chunk 数量
    if needs_chunking:
        effective_chunk = max(chunk_duration - overlap, 60.0)
        estimated = max(1, int(duration / effective_chunk) + 1)
    else:
        estimated = 0

    return AudioPreprocessResult(
        audio_path=audio_path,
        duration=duration,
        sample_rate=16000,
        channels=1,
        needs_chunking=needs_chunking,
        estimated_chunks=estimated,
        temp_files=temp_files,
    )


# ------------------------------------------------------------------ #
#  内部工具函数
# ------------------------------------------------------------------ #

def _compute_chunk_boundaries(
    total_duration: float,
    chunk_duration: float,
    overlap: float,
) -> list[tuple[float, float]]:
    """
    计算音频 chunk 的时间边界。

    示例：60 分钟音频，15 分钟/chunk，10 秒 overlap
    → [0, 900], [890, 1800], [1780, 2700], [2670, 3600]

    Args:
        total_duration: 总时长（秒）
        chunk_duration: chunk 时长（秒）
        overlap: 重叠时长（秒）

    Returns:
        (start, end) 元组列表
    """
    if total_duration <= chunk_duration:
        return [(0.0, total_duration)]

    boundaries: list[tuple[float, float]] = []
    step = chunk_duration - overlap
    current_start = 0.0

    while current_start < total_duration:
        current_end = min(current_start + chunk_duration, total_duration)
        boundaries.append((current_start, current_end))

        # 如果已经覆盖到末尾，停止
        if current_end >= total_duration:
            break

        current_start += step

        # 防止浮点误差导致无限循环
        if current_start >= total_duration - 0.01:
            break

    return boundaries


def _detect_gpu_memory() -> float | None:
    """
    检测 GPU 显存大小（GB）。

    使用 torch.cuda 检测，如果不可用则返回 None。
    """
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        device = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(device)
        return props.total_memory / (1024 ** 3)  # bytes → GB
    except Exception:
        return None


def _run_ffmpeg(cmd: list[str]) -> subprocess.CompletedProcess:
    """执行 ffmpeg 命令"""
    result = subprocess.run(
        cmd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        stderr_tail = result.stderr[-500:] if result.stderr else "未知错误"
        logger.error("ffmpeg 执行失败 (rc=%d): %s", result.returncode, stderr_tail)
        raise RuntimeError(
            f"ffmpeg 执行失败 (rc={result.returncode}): "
            f"{stderr_tail.strip()}"
        )
    return result
