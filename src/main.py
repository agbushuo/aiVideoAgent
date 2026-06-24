"""VideoAgent CLI 入口"""

from pathlib import Path

import typer
import yaml
from rich.console import Console

app = typer.Typer(
    name="videoagent",
    help="视频自动化处理 Agent: 视频 -> 字幕 -> 总结 -> 亮点分析 -> 自动剪辑",
    add_completion=False,
)

console = Console()


def load_config() -> dict:
    """加载配置文件"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def get_output_dir(output_dir: str | None) -> Path:
    """获取输出目录"""
    config = load_config()
    if output_dir:
        return Path(output_dir)
    default = config.get("output", {}).get("default_dir", "./outputs")
    return Path(default)


def _build_analyzer(llm_config: dict) -> "LLMAnalyzer":
    """从配置构建 LLMAnalyzer"""
    from src.analyze.llm_analyzer import LLMAnalyzer

    return LLMAnalyzer(
        provider=llm_config.get("provider", "llama_cpp"),
        model=llm_config.get("model", "Qwen3.6-27B-Q4_K_M.gguf"),
        endpoint=llm_config.get("endpoint", "http://localhost:8080/v1"),
        api_key=llm_config.get("api_key", ""),
        temperature=llm_config.get("temperature", 0.3),
        max_tokens=llm_config.get("max_tokens", 16384),
        timeout=llm_config.get("timeout", 600),
        context_size=llm_config.get("context_size", 131072),
    )


def _build_whisper_engine(whisper_config: dict) -> "WhisperEngine":
    """从配置构建 WhisperEngine"""
    from src.transcribe.whisper_engine import WhisperEngine

    seg_cfg = whisper_config.get("segment_transcribe", {})
    ffmpeg_cfg = load_config().get("ffmpeg", {})

    return WhisperEngine(
        model_path=whisper_config.get("model_path"),
        model_name=whisper_config.get("model_name", "large-v3"),
        device=whisper_config.get("device", "auto"),
        fp16=whisper_config.get("fp16", True),
        # 分段转录配置
        chunk_duration=seg_cfg.get("chunk_duration", 900.0),
        overlap=seg_cfg.get("overlap", 10.0),
        segment_threshold_minutes=seg_cfg.get("threshold_minutes", 30.0),
        similarity_threshold=seg_cfg.get("similarity_threshold", 0.8),
        normalize_loudness=seg_cfg.get("normalize_loudness", False),
        # ffmpeg 路径
        ffmpeg_path=ffmpeg_cfg.get("path", "ffmpeg"),
        ffprobe_path=ffmpeg_cfg.get("probe_path", "ffprobe"),
        # Whisper 参数优化
        beam_size=seg_cfg.get("beam_size", 5),
        temperature_fallback=seg_cfg.get("temperature_fallback", True),
    )


def _build_clipper(ffmpeg_config: dict) -> "Clipper":
    """从配置构建 Clipper"""
    from src.edit.clipper import Clipper

    return Clipper(
        ffmpeg_path=ffmpeg_config.get("path", "ffmpeg"),
        ffprobe_path=ffmpeg_config.get("probe_path", "ffprobe"),
    )


# ====================================================================== #
#  Commands
# ====================================================================== #


@app.command(name="transcribe")
def transcribe(
    video_path: str = typer.Argument(..., help="视频文件路径"),
    language: str | None = typer.Option(None, "--language", "-l", help="字幕语言代码（None 则自动检测）"),
    output_dir: str | None = typer.Option(None, "--output-dir", "-o", help="输出目录"),
):
    """使用 Whisper 转录视频生成字幕"""
    config = load_config()
    whisper_config = config.get("whisper", {})

    console.print(f"[bold blue]VideoAgent[/bold blue] - 转录视频")
    console.print(f"  视频: {video_path}")
    console.print(f"  语言: {language or 'auto'}")
    console.print(f"  模型: {whisper_config.get('model_name', 'large-v3')}")

    engine = _build_whisper_engine(whisper_config)

    output_dir = get_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = engine.transcribe(video_path, language=language)

    from src.utils.io import export_srt, export_transcript_json

    base_name = Path(video_path).stem
    srt_path = output_dir / "subtitles" / f"{base_name}.srt"
    json_path = output_dir / "subtitles" / f"{base_name}.json"

    srt_path.parent.mkdir(parents=True, exist_ok=True)
    export_srt(result, srt_path)
    export_transcript_json(result, json_path)

    console.print(f"\n[green]✓[/green] 转录完成")
    console.print(f"  SRT: {srt_path}")
    console.print(f"  JSON: {json_path}")
    console.print(f"  片段数: {len(result.segments)}")
    console.print(
        f"  时长: {result.segments[-1].end if result.segments else 0:.1f}秒"
    )


@app.command(name="analyze")
def analyze(
    transcript_path: str = typer.Argument(..., help="字幕 JSON 文件路径"),
    video_path: str | None = typer.Option(
        None, "--video", "-v",
        help="源视频路径（记录到报告中，供剪辑使用）",
    ),
    output_dir: str | None = typer.Option(None, "--output-dir", "-o", help="输出目录"),
):
    """使用 LLM 分析字幕，生成亮点报告"""
    from src.utils.io import load_transcript_json

    config = load_config()
    llm_config = config.get("llm", {})

    console.print(f"[bold blue]VideoAgent[/bold blue] - 分析字幕")
    console.print(f"  字幕: {transcript_path}")
    console.print(f"  LLM: {llm_config.get('provider', 'llama_cpp')}")

    transcript = load_transcript_json(transcript_path)

    analyzer = _build_analyzer(llm_config)

    output_dir = get_output_dir(output_dir)
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    base_name = Path(transcript_path).stem
    report = analyzer.analyze(transcript)

    # 记录源视频路径到报告中
    if video_path:
        report.video_path = video_path
    elif not report.video_path:
        # 尝试从字幕文件名推断
        report.video_path = f"{base_name}.mkv"

    from src.utils.io import export_analysis_json, export_markdown_report

    json_path = reports_dir / f"{base_name}.json"
    md_path = reports_dir / f"{base_name}.md"

    export_analysis_json(report, json_path)
    export_markdown_report(report, md_path)

    console.print(f"\n[green]✓[/green] 分析完成")
    console.print(f"  JSON: {json_path}")
    console.print(f"  Markdown: {md_path}")
    console.print(f"  亮点数: {len(report.highlights)}")
    if report.video_path:
        console.print(f"  源视频: {report.video_path}")


@app.command(name="clip")
def clip(
    report_path: str = typer.Argument(..., help="分析报告 JSON 路径"),
    video_path: str | None = typer.Option(
        None, "--video", "-v",
        help="源视频路径（可选，优先从报告中读取）",
    ),
    output_dir: str | None = typer.Option(
        None, "--output-dir", "-o",
        help="输出目录（默认 reports 同级 clips/ 目录）",
    ),
    merge: bool = typer.Option(
        True, "--merge/--no-merge",
        help="是否拼接精华视频",
    ),
    transition: float = typer.Option(
        0.5, "--transition",
        help="转场时长（秒），0 表示直接拼接",
    ),
    min_score: float | None = typer.Option(
        None, "--min-score",
        help="最低评分阈值，低于此值的亮点将被跳过",
    ),
):
    """从分析报告提取亮点片段（基于 ffmpeg）

    读取分析报告中的 highlights，自动裁剪对应片段并可选拼接精华视频。

    示例:
      # 从报告提取所有亮点（视频路径从报告中读取）
      videoagent clip outputs/reports/testvideo.json

      # 指定源视频路径
      videoagent clip outputs/reports/testvideo.json -v input.mp4

      # 只提取评分 >= 0.8 的亮点，不拼接
      videoagent clip outputs/reports/testvideo.json -v input.mp4 --no-merge --min-score 0.8
    """
    config = load_config()
    ffmpeg_config = config.get("ffmpeg", {})

    console.print(f"[bold blue]VideoAgent[/bold blue] - 提取亮点片段")
    console.print(f"  报告: {report_path}")
    console.print(f"  ffmpeg: {ffmpeg_config.get('path', 'ffmpeg')}")

    clipper = _build_clipper(ffmpeg_config)

    if output_dir:
        output_dir = Path(output_dir)

    result = clipper.clips_from_report(
        report_path=report_path,
        video_path=video_path,
        output_dir=output_dir,
        merge=merge,
        merge_transition=transition if merge else None,
        filter_by_score=min_score,
    )

    console.print(f"\n[green]✓[/green] 剪辑完成")
    console.print(f"  成功: {result.success_count} 个片段")
    console.print(f"  总时长: {result.total_duration:.1f} 秒")

    if result.clips:
        console.print(f"\n  独立片段:")
        for c in result.clips:
            status = "[green]✓[/green]" if c.success else "[red]✗[/red]"
            console.print(
                f"    {status} {c.clip_path.name} "
                f"({c.start:.1f}s - {c.end:.1f}s, {c.duration:.1f}s)"
            )

    if result.merged_path:
        console.print(f"\n  精华视频: [green]{result.merged_path}[/green]")

    if result.errors:
        console.print(f"\n  错误:")
        for err in result.errors:
            console.print(f"    [red]✗[/red] {err}")


@app.command(name="pipeline")
def pipeline(
    video_path: str = typer.Argument(..., help="视频文件路径"),
    language: str | None = typer.Option(None, "--language", "-l", help="字幕语言代码（None 则自动检测）"),
    output_dir: str | None = typer.Option(None, "--output-dir", "-o", help="输出目录"),
    clip: bool = typer.Option(
        False, "--clip",
        help="分析完成后自动提取亮点片段",
    ),
    min_score: float | None = typer.Option(
        None, "--min-score",
        help="剪辑时最低评分阈值（仅 --clip 时生效）",
    ),
):
    """一键全流程: 转录 -> 分析 -> (可选) 剪辑

    示例:
      # 转录 + 分析
      videoagent pipeline input.mp4

      # 转录 + 分析 + 自动剪辑
      videoagent pipeline input.mp4 --clip

      # 只剪辑评分 >= 0.8 的亮点
      videoagent pipeline input.mp4 --clip --min-score 0.8
    """
    config = load_config()

    console.print("[bold blue]VideoAgent[/bold blue] - 全流程处理")
    console.print(f"  视频: {video_path}")
    console.print(f"  语言: {language or 'auto'}")
    console.rule()

    output_dir = get_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1: 转录
    console.print("[bold]Stage 1/3[/bold]: Whisper 转录...")

    whisper_config = config.get("whisper", {})
    engine = _build_whisper_engine(whisper_config)

    transcript = engine.transcribe(video_path, language=language)

    from src.utils.io import export_srt, export_transcript_json

    base_name = Path(video_path).stem
    subtitles_dir = output_dir / "subtitles"
    subtitles_dir.mkdir(parents=True, exist_ok=True)

    srt_path = subtitles_dir / f"{base_name}.srt"
    subtitle_json_path = subtitles_dir / f"{base_name}.json"

    export_srt(transcript, srt_path)
    export_transcript_json(transcript, subtitle_json_path)

    console.print(f"[green]✓[/green] 转录完成 ({len(transcript.segments)} 个片段)")
    console.rule()

    # Stage 2: 分析
    console.print("[bold]Stage 2/3[/bold]: LLM 分析...")
    llm_config = config.get("llm", {})
    analyzer = _build_analyzer(llm_config)

    report = analyzer.analyze(transcript)

    # 记录源视频路径
    report.video_path = video_path

    from src.utils.io import export_analysis_json, export_markdown_report

    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_json_path = reports_dir / f"{base_name}.json"
    report_md_path = reports_dir / f"{base_name}.md"

    export_analysis_json(report, report_json_path)
    export_markdown_report(report, report_md_path)

    console.print(f"[green]✓[/green] 分析完成 ({len(report.highlights)} 个亮点)")
    console.rule()

    # Stage 3: 剪辑 (可选)
    if clip:
        console.print("[bold]Stage 3/3[/bold]: ffmpeg 剪辑...")
        ffmpeg_config = config.get("ffmpeg", {})
        clipper = _build_clipper(ffmpeg_config)

        clip_result = clipper.clips_from_report(
            report_path=report_json_path,
            video_path=video_path,
            filter_by_score=min_score,
        )

        console.print(f"[green]✓[/green] 剪辑完成")
        console.print(f"  成功: {clip_result.success_count} 个片段")

        for c in clip_result.clips:
            status = "[green]✓[/green]" if c.success else "[red]✗[/red]"
            console.print(
                f"    {status} {c.clip_path.name} "
                f"({c.start:.1f}s - {c.end:.1f}s)"
            )

        if clip_result.merged_path:
            console.print(f"  精华视频: [green]{clip_result.merged_path}[/green]")

        if clip_result.errors:
            for err in clip_result.errors:
                console.print(f"    [red]✗[/red] {err}")

        console.rule()

    console.print("[bold green]✓ 全流程完成![/bold green]")
    console.print(f"  字幕 SRT:  {srt_path}")
    console.print(f"  字幕 JSON: {subtitle_json_path}")
    console.print(f"  报告 JSON: {report_json_path}")
    console.print(f"  报告 Markdown: {report_md_path}")


@app.command(name="batch")
def batch(
    input_path: str = typer.Argument(..., help="视频文件/目录/glob 模式"),
    language: str | None = typer.Option(None, "--language", "-l", help="字幕语言代码（None 则自动检测）"),
    output_dir: str | None = typer.Option(None, "--output-dir", "-o", help="输出目录"),
    clip: bool = typer.Option(
        False, "--clip",
        help="分析完成后自动提取亮点片段",
    ),
    min_score: float | None = typer.Option(
        None, "--min-score",
        help="剪辑时最低评分阈值（仅 --clip 时生效）",
    ),
    merge_clips: bool = typer.Option(
        True, "--merge/--no-merge",
        help="是否拼接精华视频（仅 --clip 时生效）",
    ),
    transition: float = typer.Option(
        0.5, "--transition",
        help="转场时长（秒），0 表示直接拼接",
    ),
):
    """批量处理多个视频（串行，每个视频独立运行）

    支持：
    - 单个文件: videoagent batch input.mp4
    - 目录递归: videoagent batch D:/videos/
    - glob 模式: videoagent batch "D:/videos/*.mp4"

    示例:
      # 批量处理目录下所有视频（转录 + 分析）
      videoagent batch "D:/videos/"

      # 转录 + 分析 + 自动剪辑
      videoagent batch "D:/videos/" --clip

      # 只剪辑评分 >= 0.7 的亮点
      videoagent batch "D:/videos/*.mp4" --clip --min-score 0.7
    """
    from src.batch import run_batch

    output_dir = get_output_dir(output_dir)

    console.print(f"[bold blue]VideoAgent[/bold blue] - 批量处理")
    console.print(f"  输入: {input_path}")
    console.print(f"  输出: {output_dir}")
    console.print(f"  语言: {language or 'auto'}")
    console.print(f"  剪辑: {'是' if clip else '否'}")
    console.rule()

    result = run_batch(
        input_path,
        output_dir=output_dir,
        language=language,
        clip=clip,
        min_score=min_score,
        merge_clips=merge_clips,
        transition_duration=transition,
    )

    console.print(f"\n[bold green]✓ 批量处理完成![/bold green]")
    console.print(f"  成功: {result.success_count}/{len(result.items)}")
    if result.summary_csv_path:
        console.print(f"  汇总 CSV: {result.summary_csv_path}")


@app.command(name="version")
def version():
    """显示版本信息"""
    from src import __version__

    console.print(f"VideoAgent v{__version__}")


if __name__ == "__main__":
    app()
