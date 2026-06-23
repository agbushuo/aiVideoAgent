"""视频剪辑器 (基于 ffmpeg)

从分析报告 JSON 中提取亮点片段，支持：
- 单个片段裁剪
- 批量提取独立片段文件
- 拼接所有片段为精华视频（带淡入淡出转场）
- 从报告 JSON 一键提取
"""

from __future__ import annotations

import json
import logging
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.analyze.llm_analyzer import AnalysisReport, Highlight

logger = logging.getLogger(__name__)


@dataclass
class ClipResult:
    """单个剪辑结果"""
    clip_path: Path          # 输出文件路径
    title: str               # 片段标题
    start: float             # 开始时间
    end: float               # 结束时间
    duration: float          # 实际时长
    success: bool            # 是否成功
    error: str = ""          # 错误信息


@dataclass
class ClipBatchResult:
    """批量剪辑结果"""
    clips: list[ClipResult] = field(default_factory=list)
    merged_path: Path | None = None       # 拼接后的精华视频路径
    total_duration: float = 0.0           # 所有片段总时长
    success_count: int = 0
    fail_count: int = 0
    errors: list[str] = field(default_factory=list)


class Clipper:
    """视频剪辑器 — 基于 ffmpeg 实现片段裁剪和拼接"""

    # 默认转场时长（秒）
    DEFAULT_TRANSITION_DURATION = 0.5

    def __init__(
        self,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
        output_format: str = "mp4",
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        video_bitrate: str = "2M",
        audio_bitrate: str = "128k",
        crf: int = 23,
    ):
        """
        Args:
            ffmpeg_path: ffmpeg 可执行文件路径
            ffprobe_path: ffprobe 可执行文件路径
            output_format: 输出格式 (mp4 / mkv)
            video_codec: 视频编码器
            audio_codec: 音频编码器
            video_bitrate: 视频码率 (仅非 CRF 模式)
            audio_bitrate: 音频码率
            crf: 恒定质量参数 (0-51, 越低质量越高, 默认 23)
        """
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.output_format = output_format
        self.video_codec = video_codec
        self.audio_codec = audio_codec
        self.video_bitrate = video_bitrate
        self.audio_bitrate = audio_bitrate
        self.crf = crf

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def clips_from_report(
        self,
        report_path: str | Path,
        video_path: str | Path | None = None,
        output_dir: str | Path | None = None,
        merge: bool = True,
        merge_transition: float | None = None,
        filter_by_score: float | None = None,
    ) -> ClipBatchResult:
        """
        从分析报告 JSON 中提取亮点片段 — **主入口接口**

        Args:
            report_path: 分析报告 JSON 路径 (如 outputs/reports/video.json)
            video_path: 源视频路径 (可选，优先从报告中读取)
            output_dir: 输出目录 (默认 reports 同级 clips/ 目录)
            merge: 是否拼接精华视频 (默认 True)
            merge_transition: 转场时长秒数 (默认 0.5s)
            filter_by_score: 最低评分阈值，低于此值的亮点将被跳过 (None=全部)

        Returns:
            ClipBatchResult: 包含所有剪辑结果和拼接视频路径

        Example:
            >>> clipper = Clipper()
            >>> result = clipper.clips_from_report(
            ...     "outputs/reports/testvideo.json",
            ...     video_path="input.mp4",
            ...     merge=True,
            ...     filter_by_score=0.8,
            ... )
            >>> print(f"成功: {result.success_count}, 失败: {result.fail_count}")
            >>> print(f"精华视频: {result.merged_path}")
        """
        report_path = Path(report_path)
        report = self._load_report_json(report_path)

        # 确定源视频路径
        if video_path is None:
            video_path = report.video_path
        if not video_path:
            raise ValueError(
                "未找到源视频路径：报告中未记录 video_path，"
                "请通过 video_path 参数传入"
            )

        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"源视频文件不存在: {video_path}")

        # 确定输出目录
        if output_dir is None:
            output_dir = report_path.parent.parent / "clips"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 过滤 highlights
        highlights = report.highlights
        if filter_by_score is not None:
            highlights = [h for h in highlights if h.score >= filter_by_score]

        if not highlights:
            logger.warning("没有符合条件的亮点片段")
            return ClipBatchResult()

        # 批量裁剪
        batch = ClipBatchResult()
        for i, h in enumerate(highlights):
            clip_filename = self._sanitize_filename(
                f"clip_{i+1:02d}_{h.title}"
            )
            clip_path = output_dir / f"{clip_filename}.{self.output_format}"
            result = self.extract_segment(video_path, h.start, h.end, clip_path)
            batch.clips.append(result)
            if result.success:
                batch.success_count += 1
                batch.total_duration += result.duration
            else:
                batch.fail_count += 1
                batch.errors.append(f"{h.title}: {result.error}")

        # 拼接精华视频
        if merge and batch.success_count > 0:
            successful_clips = [c for c in batch.clips if c.success]
            transition = merge_transition if merge_transition is not None else self.DEFAULT_TRANSITION_DURATION
            merged_path = output_dir / f"highlights_merged.{self.output_format}"
            merge_result = self.merge_clips(
                [c.clip_path for c in successful_clips],
                merged_path,
                transition_duration=transition,
            )
            if merge_result:
                batch.merged_path = merged_path
            else:
                batch.errors.append("拼接精华视频失败")

        return batch

    def extract_segment(
        self,
        video_path: str | Path,
        start: float,
        end: float,
        output_path: str | Path,
    ) -> ClipResult:
        """
        提取单个视频片段

        Args:
            video_path: 源视频路径
            start: 开始时间 (秒)
            end: 结束时间 (秒)
            output_path: 输出文件路径

        Returns:
            ClipResult: 裁剪结果
        """
        video_path = Path(video_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        duration = end - start
        title = output_path.stem

        try:
            cmd = self._build_extract_cmd(video_path, start, end, output_path)
            logger.info(
                "裁剪片段: %.1fs - %.1fs (%.1fs) -> %s",
                start, end, duration, output_path,
            )
            self._run_ffmpeg(cmd)

            # 验证输出文件
            actual_duration = self._get_duration(output_path)
            return ClipResult(
                clip_path=output_path,
                title=title,
                start=start,
                end=end,
                duration=actual_duration,
                success=True,
            )

        except Exception as e:
            # 清理失败文件
            if output_path.exists():
                output_path.unlink()
            return ClipResult(
                clip_path=output_path,
                title=title,
                start=start,
                end=end,
                duration=0,
                success=False,
                error=str(e),
            )

    def clip_highlights(
        self,
        video_path: str | Path,
        highlights: list[Highlight],
        output_dir: str | Path,
    ) -> list[ClipResult]:
        """
        批量裁剪所有亮点片段为独立文件

        Args:
            video_path: 源视频路径
            highlights: 亮点片段列表
            output_dir: 输出目录

        Returns:
            剪辑结果列表
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for i, h in enumerate(highlights):
            clip_filename = self._sanitize_filename(
                f"clip_{i+1:02d}_{h.title}"
            )
            clip_path = output_dir / f"{clip_filename}.{self.output_format}"
            result = self.extract_segment(video_path, h.start, h.end, clip_path)
            results.append(result)

        return results

    def merge_clips(
        self,
        clip_paths: list[str | Path],
        output_path: str | Path,
        transition_duration: float = 0.5,
    ) -> Path | None:
        """
        拼接多个片段为一个视频（带淡入淡出转场）

        Args:
            clip_paths: 片段文件路径列表（按顺序）
            output_path: 输出文件路径
            transition_duration: 转场时长 (秒)，0 表示直接拼接

        Returns:
            成功返回输出路径，失败返回 None
        """
        clip_paths = [Path(p) for p in clip_paths]
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not clip_paths:
            logger.warning("没有可拼接的片段")
            return None

        if len(clip_paths) == 1:
            # 只有一个片段，直接复制（重编码）
            try:
                cmd = self._build_extract_cmd(
                    clip_paths[0], 0, self._get_duration(clip_paths[0]), output_path
                )
                self._run_ffmpeg(cmd)
                return output_path
            except Exception as e:
                logger.error("拼接失败: %s", e)
                return None

        try:
            if transition_duration > 0:
                return self._merge_with_fade(
                    clip_paths, output_path, transition_duration
                )
            else:
                return self._merge_concat(clip_paths, output_path)

        except Exception as e:
            logger.error("拼接失败: %s", e)
            if output_path.exists():
                output_path.unlink()
            return None

    # ------------------------------------------------------------------ #
    #  FFmpeg 命令构建
    # ------------------------------------------------------------------ #

    def _build_extract_cmd(
        self,
        input_path: Path,
        start: float,
        end: float,
        output_path: Path,
    ) -> list[str]:
        """构建片段裁剪的 ffmpeg 命令"""
        duration = end - start

        cmd = [
            self.ffmpeg_path,
            "-y",  # 覆盖输出文件
            "-ss", str(start),  # 起始时间（输入前，快速定位）
            "-i", str(input_path),
            "-t", str(duration),  # 持续时间
            "-c:v", self.video_codec,
            "-crf", str(self.crf),
            "-c:a", self.audio_codec,
            "-b:a", self.audio_bitrate,
            # 确保音频同步
            "-async", "1",
            # 输出格式
            "-f", self.output_format,
            str(output_path),
        ]
        return cmd

    def _merge_concat(
        self, clip_paths: list[Path], output_path: Path
    ) -> Path:
        """使用 concat demuxer 拼接（无转场，速度快）"""
        # 生成 concat 列表文件
        list_content = "\n".join(
            f"file '{os.path.abspath(p)}'" for p in clip_paths
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(list_content)
            list_file = f.name

        try:
            # 先用 concat demuxer 合并（不重编码，极速）
            temp_merged = tempfile.NamedTemporaryFile(
                suffix=f".{self.output_format}", delete=False
            ).name

            cmd = [
                self.ffmpeg_path,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                temp_merged,
            ]
            self._run_ffmpeg(cmd)

            # 再重编码为 H.264
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-i", temp_merged,
                "-c:v", self.video_codec,
                "-pix_fmt", "yuv420p",
                "-crf", str(self.crf),
                "-c:a", self.audio_codec,
                "-b:a", self.audio_bitrate,
                "-f", self.output_format,
                str(output_path),
            ]
            self._run_ffmpeg(cmd)

            Path(temp_merged).unlink()
            return output_path

        finally:
            if Path(list_file).exists():
                Path(list_file).unlink()

    def _merge_with_fade(
        self,
        clip_paths: list[Path],
        output_path: Path,
        transition: float,
    ) -> Path:
        """使用 complex filter 拼接（带交叉淡入淡出转场）"""
        num_clips = len(clip_paths)

        # 获取每个片段的时长
        durations = []
        for p in clip_paths:
            dur = self._get_duration(p)
            if dur <= 0:
                raise ValueError(f"片段时长无效: {p}")
            durations.append(dur)

        # 构建 complex filter
        filter_parts = []
        inputs = []

        # 输入参数
        for i, p in enumerate(clip_paths):
            inputs.extend(["-i", str(p)])

        # 对所有片段重置时间戳，确保格式兼容
        for i in range(num_clips):
            filter_parts.append(
                f"[{i}:v]setpts=PTS-STARTPTS,format=yuv420p[v{i}]"
            )
            filter_parts.append(
                f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]"
            )

        # 交叉淡入淡出
        if num_clips == 2:
            # 两个片段：一个 crossfade
            dur0 = durations[0]
            filter_parts.append(
                f"[v0][v1]xfade=transition=fade:"
                f"duration={transition}:"
                f"offset={dur0 - transition}[vout]"
            )
            filter_parts.append(
                f"[a0][a1]acrossfade=d={transition}[aout]"
            )
        else:
            # 多个片段：链式 crossfade
            first_dur = durations[0]
            # 第一个 crossfade
            filter_parts.append(
                f"[v0][v1]xfade=transition=fade:"
                f"duration={transition}:"
                f"offset={first_dur - transition}[tmp0]"
            )
            filter_parts.append(
                f"[a0][a1]acrossfade=d={transition}[atmp0]"
            )

            # 后续 crossfade
            accumulated = first_dur + durations[1] - transition
            for i in range(2, num_clips):
                prev_label = f"tmp{i-2}"
                # Last iteration outputs to [vout]/[aout] directly
                if i == num_clips - 1:
                    out_label = "vout"
                    audio_out = "aout"
                else:
                    out_label = f"tmp{i-1}"
                    audio_out = f"atmp{i-1}"
                offset = accumulated - transition
                filter_parts.append(
                    f"[{prev_label}][v{i}]xfade=transition=fade:"
                    f"duration={transition}:"
                    f"offset={offset}[{out_label}]"
                )
                filter_parts.append(
                    f"[atmp{i-2}][a{i}]acrossfade=d={transition}[{audio_out}]"
                )
                accumulated += durations[i] - transition

        filter_complex = ";".join(filter_parts)

        cmd = [
            self.ffmpeg_path,
            "-y",
        ] + inputs + [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", self.video_codec,
            "-pix_fmt", "yuv420p",
            "-crf", str(self.crf),
            "-c:a", self.audio_codec,
            "-b:a", self.audio_bitrate,
            "-f", self.output_format,
            str(output_path),
        ]

        self._run_ffmpeg(cmd)
        return output_path

    # ------------------------------------------------------------------ #
    #  工具方法
    # ------------------------------------------------------------------ #

    def _run_ffmpeg(self, cmd: list[str]) -> subprocess.CompletedProcess:
        """执行 ffmpeg 命令"""
        logger.debug("ffmpeg 命令: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            logger.error("ffmpeg 错误: %s", result.stderr[-500:] if result.stderr else "未知错误")
            raise RuntimeError(
                f"ffmpeg 执行失败 (rc={result.returncode}): "
                f"{result.stderr[-200:] if result.stderr else '未知错误'}"
            )
        return result

    def _get_duration(self, video_path: Path) -> float:
        """使用 ffprobe 获取视频时长"""
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", check=True)
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0))

    @staticmethod
    def _sanitize_filename(name: str, max_len: int = 80) -> str:
        """清理文件名中的非法字符"""
        # 移除或替换非法字符
        sanitized = name.replace(" ", "_")
        illegal = '<>:"|?*'
        for ch in illegal:
            sanitized = sanitized.replace(ch, "")
        # 限制长度
        if len(sanitized) > max_len:
            sanitized = sanitized[:max_len]
        return sanitized.strip("_-")

    @staticmethod
    def _load_report_json(report_path: Path) -> AnalysisReport:
        """从 JSON 文件加载分析报告"""
        from src.utils.io import load_analysis_json
        return load_analysis_json(report_path)
