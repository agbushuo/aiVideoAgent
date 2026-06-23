"""批量处理模块

串行处理多个视频，通过重复调用 `process_video()` 实现批处理。

每个视频完全独立运行：各自创建和释放 Whisper/LLM/Clipper 实例。
适合视频数量不多、追求隔离性的场景。

用法:
    from src.batch import run_batch, discover_videos

    # 批量处理目录下的所有视频
    result = run_batch("D:/videos/", clip=True)
    print(f"成功: {result.success_count}, 失败: {result.fail_count}")
    print(f"汇总 CSV: {result.summary_csv_path}")
"""

from __future__ import annotations

import csv
import glob
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from src.pipeline import VideoProcessResult

logger = logging.getLogger(__name__)
console = Console()

# 支持的视频扩展名
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv"}


@dataclass
class BatchResult:
    """批量处理总结果"""
    items: list[VideoProcessResult] = field(default_factory=list)
    summary_csv_path: Path | None = None
    total_elapsed_seconds: float = 0.0

    @property
    def success_count(self) -> int:
        return sum(1 for i in self.items if i.status == "success")

    @property
    def fail_count(self) -> int:
        return sum(1 for i in self.items if i.status == "error")


def discover_videos(input_path: str | Path) -> list[Path]:
    """发现视频文件

    支持：
    - 单个文件路径
    - 目录路径（递归查找）
    - glob 模式（包含 * 或 ?）

    Args:
        input_path: 文件 / 目录 / glob 模式

    Returns:
        视频文件路径列表（按文件名排序）
    """
    input_str = str(input_path)

    # glob 模式
    if "*" in input_str or "?" in input_str:
        matches = sorted(Path(p) for p in glob.glob(input_str))
        return [p for p in matches if p.suffix.lower() in VIDEO_EXTENSIONS]

    target = Path(input_path)

    # 单个文件
    if target.is_file():
        if target.suffix.lower() in VIDEO_EXTENSIONS:
            return [target]
        raise ValueError(
            f"不是支持的视频格式: {target}"
            f"（支持: {', '.join(sorted(VIDEO_EXTENSIONS))}）"
        )

    # 目录递归
    if target.is_dir():
        videos = []
        for ext in VIDEO_EXTENSIONS:
            videos.extend(target.rglob(f"*{ext}"))
        videos.sort(key=lambda p: p.name)
        return videos

    raise FileNotFoundError(f"路径不存在: {target}")


def run_batch(
    input_path: str | Path,
    *,
    output_dir: str | Path = "outputs",
    language: str = "zh",
    clip: bool = False,
    min_score: float | None = None,
    merge_clips: bool = True,
    transition_duration: float = 0.5,
    # Whisper 配置覆盖
    whisper_model_path: str | None = None,
    whisper_model_name: str | None = None,
    whisper_device: str | None = None,
    whisper_fp16: bool | None = None,
    # LLM 配置覆盖
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_endpoint: str | None = None,
    llm_api_key: str | None = None,
    llm_temperature: float | None = None,
    llm_max_tokens: int | None = None,
    llm_timeout: int | None = None,
    llm_context_size: int | None = None,
    # ffmpeg 配置覆盖
    ffmpeg_path: str | None = None,
    ffprobe_path: str | None = None,
) -> BatchResult:
    """批量处理视频

    串行调用 process_video()，每个视频完全独立运行。

    Args:
        input_path: 文件 / 目录 / glob 模式
        output_dir: 总输出目录
        language: 字幕语言
        clip: 是否剪辑
        min_score: 最低剪辑评分
        merge_clips: 是否拼接精华视频
        transition_duration: 转场时长
        whisper_* / llm_* / ffmpeg_*: 配置覆盖参数（传给 process_video）

    Returns:
        BatchResult: 包含所有视频的处理结果和 CSV 汇总路径

    Example:
        >>> result = run_batch("D:/videos/*.mp4", clip=True, min_score=0.7)
        >>> print(f"成功: {result.success_count}/{len(result.items)}")
    """
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    # 发现视频
    videos = discover_videos(input_path)
    if not videos:
        console.print(f"[yellow]未找到视频文件: {input_path}[/yellow]")
        return BatchResult()

    console.print(f"\n[dim]找到 {len(videos)} 个视频，开始串行处理...[/dim]\n")

    total_start = time.time()
    batch = BatchResult()

    for idx, video in enumerate(videos, 1):
        console.print(
            f"[bold]━━━ [{idx}/{len(videos)}] {video.name} ━━━[/bold]"
        )

        try:
            from src.pipeline import process_video

            item = process_video(
                video,
                output_dir=output_root,
                language=language,
                clip=clip,
                min_score=min_score,
                merge_clips=merge_clips,
                transition_duration=transition_duration,
                whisper_model_path=whisper_model_path,
                whisper_model_name=whisper_model_name,
                whisper_device=whisper_device,
                whisper_fp16=whisper_fp16,
                llm_provider=llm_provider,
                llm_model=llm_model,
                llm_endpoint=llm_endpoint,
                llm_api_key=llm_api_key,
                llm_temperature=llm_temperature,
                llm_max_tokens=llm_max_tokens,
                llm_timeout=llm_timeout,
                llm_context_size=llm_context_size,
                ffmpeg_path=ffmpeg_path,
                ffprobe_path=ffprobe_path,
            )

            batch.items.append(item)

        except Exception as e:
            # 即使 process_video 内部已经捕获了异常，这里也做兜底
            console.print(f"[red]✗[/red] {video.name} 处理异常: {str(e)[:200]}\n")
            from src.pipeline import VideoProcessResult

            item = VideoProcessResult(
                video_path=video,
                status="error",
                error=f"未知异常: {str(e)[:200]}",
            )
            batch.items.append(item)

        console.print("")  # 空行分隔

    batch.total_elapsed_seconds = time.time() - total_start

    # 生成 CSV 汇总
    summary_csv = output_root / "batch_summary.csv"
    _write_summary_csv(batch, summary_csv)
    batch.summary_csv_path = summary_csv

    # 打印汇总
    _print_summary(batch)

    return batch


def _write_summary_csv(batch: BatchResult, csv_path: Path) -> None:
    """写入 CSV 汇总报告"""
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "序号", "状态", "文件名", "视频时长(秒)", "转录片段数",
            "亮点数", "剪辑片段数", "精华视频路径", "耗时(秒)", "错误信息",
            "字幕JSON路径", "报告JSON路径", "报告Markdown路径",
        ])
        for i, item in enumerate(batch.items, 1):
            writer.writerow([
                i,
                item.status,
                item.video_path.name,
                f"{item.duration:.1f}",
                item.segment_count,
                item.highlight_count,
                item.clip_count,
                item.merged_clip_path,
                f"{item.elapsed_seconds:.1f}",
                item.error,
                item.transcript_path or "",
                item.report_json_path or "",
                item.report_md_path or "",
            ])


def _print_summary(batch: BatchResult) -> None:
    """在终端打印汇总信息"""
    console.print("\n[bold]═══════════════════════════════════════[/bold]")
    console.print("[bold]  批量处理汇总[/bold]")
    console.print("[bold]═══════════════════════════════════════[/bold]")

    total = len(batch.items)
    success = batch.success_count
    failed = batch.fail_count

    console.print(
        f"  总数: {total}  |  "
        f"[green]成功: {success}[/green]  |  "
        f"[red]失败: {failed}[/red]"
    )

    total_duration = sum(i.duration for i in batch.items)
    total_highlights = sum(i.highlight_count for i in batch.items)
    console.print(f"  总视频时长: {total_duration:.1f} 秒")
    console.print(f"  总亮点数: {total_highlights}")
    console.print(f"  总耗时: {batch.total_elapsed_seconds:.1f} 秒")

    if failed > 0:
        console.print(f"\n  [yellow]失败列表:[/yellow]")
        for item in batch.items:
            if item.status == "error":
                console.print(
                    f"    [red]✗[/red] {item.video_path.name} — {item.error}"
                )

    if batch.summary_csv_path:
        console.print(
            f"\n  汇总 CSV: [green]{batch.summary_csv_path}[/green]"
        )

    console.print("[bold]═══════════════════════════════════════[/bold]\n")
