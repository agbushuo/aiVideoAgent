"""视频元信息提取工具

使用 ffprobe 提取视频的时长、分辨率、编码等信息。
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoInfo:
    """视频元信息"""
    path: str
    duration: float
    width: int
    height: int
    video_codec: str
    audio_codec: str
    fps: float
    bitrate: int

    @classmethod
    def from_file(cls, video_path: str | Path, probe_path: str = "ffprobe") -> "VideoInfo":
        """
        从视频文件提取元信息

        Args:
            video_path: 视频文件路径
            probe_path: ffprobe 可执行文件路径

        Returns:
            VideoInfo
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"文件不存在: {video_path}")

        cmd = [
            probe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        # 提取视频流信息
        video_stream = None
        audio_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and audio_stream is None:
                audio_stream = stream

        format_info = data.get("format", {})

        return cls(
            path=str(video_path),
            duration=float(format_info.get("duration", 0)),
            width=int(video_stream.get("width", 0)) if video_stream else 0,
            height=int(video_stream.get("height", 0)) if video_stream else 0,
            video_codec=video_stream.get("codec_name", "unknown") if video_stream else "unknown",
            audio_codec=audio_stream.get("codec_name", "unknown") if audio_stream else "unknown",
            fps=float(video_stream.get("r_frame_rate", 0)) if video_stream else 0,
            bitrate=int(format_info.get("bit_rate", 0)),
        )
