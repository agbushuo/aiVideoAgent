"""VideoAgent CLI 入口"""

from pathlib import Path

import typer
import yaml
from rich.console import Console

app = typer.Typer(
    name="videoagent",
    help="视频自动化处理 Agent: 视频 -> 字幕 -> 总结 -> 亮点分析",
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


@app.command(name="transcribe")
def transcribe(
    video_path: str = typer.Argument(..., help="视频文件路径"),
    language: str = typer.Option("zh", "--language", "-l", help="字幕语言代码"),
    output_dir: str | None = typer.Option(None, "--output-dir", "-o", help="输出目录"),
):
    """使用 Whisper 转录视频生成字幕"""
    from src.transcribe.whisper_engine import WhisperEngine

    config = load_config()
    whisper_config = config.get("whisper", {})

    console.print(f"[bold blue]VideoAgent[/bold blue] - 转录视频")
    console.print(f"  视频: {video_path}")
    console.print(f"  语言: {language}")
    console.print(f"  模型: {whisper_config.get('model_name', 'large-v3')}")

    engine = WhisperEngine(
        model_path=whisper_config.get("model_path"),
        model_name=whisper_config.get("model_name", "large-v3"),
        device=whisper_config.get("device", "auto"),
        fp16=whisper_config.get("fp16", True),
    )

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

    from src.utils.io import export_analysis_json, export_markdown_report

    json_path = reports_dir / f"{base_name}.json"
    md_path = reports_dir / f"{base_name}.md"

    export_analysis_json(report, json_path)
    export_markdown_report(report, md_path)

    console.print(f"\n[green]✓[/green] 分析完成")
    console.print(f"  JSON: {json_path}")
    console.print(f"  Markdown: {md_path}")
    console.print(f"  亮点数: {len(report.highlights)}")


@app.command(name="pipeline")
def pipeline(
    video_path: str = typer.Argument(..., help="视频文件路径"),
    language: str = typer.Option("zh", "--language", "-l", help="字幕语言代码"),
    output_dir: str | None = typer.Option(None, "--output-dir", "-o", help="输出目录"),
):
    """一键全流程: 转录 -> 分析 -> 输出报告"""
    config = load_config()

    console.print("[bold blue]VideoAgent[/bold blue] - 全流程处理")
    console.print(f"  视频: {video_path}")
    console.print(f"  语言: {language}")
    console.rule()

    output_dir = get_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1: 转录
    console.print("[bold]Stage 1/2[/bold]: Whisper 转录...")
    from src.transcribe.whisper_engine import WhisperEngine

    whisper_config = config.get("whisper", {})
    engine = WhisperEngine(
        model_path=whisper_config.get("model_path"),
        model_name=whisper_config.get("model_name", "large-v3"),
        device=whisper_config.get("device", "auto"),
        fp16=whisper_config.get("fp16", True),
    )

    transcript = engine.transcribe(video_path, language=language)

    from src.utils.io import export_srt, export_transcript_json

    base_name = Path(video_path).stem
    subtitles_dir = output_dir / "subtitles"
    subtitles_dir.mkdir(parents=True, exist_ok=True)

    srt_path = subtitles_dir / f"{base_name}.srt"
    json_path = subtitles_dir / f"{base_name}.json"

    export_srt(transcript, srt_path)
    export_transcript_json(transcript, json_path)

    console.print(f"[green]✓[/green] 转录完成 ({len(transcript.segments)} 个片段)")
    console.rule()

    # Stage 2: 分析
    console.print("[bold]Stage 2/2[/bold]: LLM 分析...")
    llm_config = config.get("llm", {})
    analyzer = _build_analyzer(llm_config)

    report = analyzer.analyze(transcript)

    from src.utils.io import export_analysis_json, export_markdown_report

    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_json_path = reports_dir / f"{base_name}.json"
    report_md_path = reports_dir / f"{base_name}.md"

    export_analysis_json(report, report_json_path)
    export_markdown_report(report, report_md_path)

    console.print(f"[green]✓[/green] 分析完成 ({len(report.highlights)} 个亮点)")
    console.rule()

    console.print("[bold green]✓ 全流程完成![/bold green]")
    console.print(f"  字幕 SRT:  {srt_path}")
    console.print(f"  字幕 JSON: {json_path}")
    console.print(f"  报告 JSON: {report_json_path}")
    console.print(f"  报告 Markdown: {report_md_path}")


@app.command(name="version")
def version():
    """显示版本信息"""
    from src import __version__

    console.print(f"VideoAgent v{__version__}")


if __name__ == "__main__":
    app()
