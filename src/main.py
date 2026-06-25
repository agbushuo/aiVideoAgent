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
#  Helper functions
# ====================================================================== #


def _parse_duration(duration_str: str) -> float:
    """解析时长字符串为秒数

    支持的格式: 60s, 3m, 1h, 1h30m, 90s, 5m30s

    Args:
        duration_str: 时长字符串

    Returns:
        秒数

    Raises:
        ValueError: 格式不识别时
    """
    import re

    duration_str = duration_str.strip().lower()
    total = 0.0

    # 匹配 h/m/s
    hours = re.search(r'(\d+(?:\.\d+)?)h', duration_str)
    minutes = re.search(r'(\d+(?:\.\d+)?)m(?:[^i\s]|$)', duration_str)
    seconds = re.search(r'(\d+(?:\.\d+)?)s(?:\s|$)', duration_str)

    if hours:
        total += float(hours.group(1)) * 3600
    if minutes:
        total += float(minutes.group(1)) * 60
    if seconds:
        total += float(seconds.group(1))

    if total == 0:
        # 尝试纯数字（默认为秒）
        try:
            total = float(duration_str)
        except ValueError:
            pass

    if total == 0:
        raise ValueError(
            f"无法解析时长 '{duration_str}'。"
            "支持的格式: 60s, 3m, 1h, 1h30m, 90s"
        )

    return total


def _get_video_path_from_report(report_path: str) -> str:
    """从报告 JSON 中读取视频路径"""
    import json

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    video_path = data.get("video_path", "")
    if not video_path:
        raise ValueError(
            f"报告 {report_path} 中未找到 video_path，"
            "请使用 --video 参数指定源视频路径"
        )
    return video_path


def _run_smart_clip(
    *,
    transcript_path: str,
    video_path: str,
    output_dir: str | None = None,
    mode: str | None = None,
    preset: str | None = None,
    num_clips: int = 0,
    target_duration: float = 0.0,
    user_prompt: str | None = None,
    min_gap: float = 120.0,
    merge: bool = True,
    transition: float = 0.5,
    ffmpeg_config: dict,
    llm_config: dict,
    use_duration_planner: bool = False,
    use_final_review: bool = False,
    final_review_count: int | None = None,
) -> "ClipBatchResult":
    """运行 Smart Clip Engine v2.0 完整流程

    流程:
    1. 加载字幕 → Scene Detection → 生成 Scene 列表
    2. LLM 标注 → 多维评分 + 标签
    3. Score Engine → 计算综合分
    4. Filter Engine → Diversity 去重 + 数量/时长约束
    5. Duration Planner → 按目标时长组合片段（可选）
    6. LLM Final Review → 最终精选和排序（可选）
    7. Clipper → ffmpeg 裁剪 + 拼接

    Returns:
        ClipBatchResult: 剪辑结果
    """
    from src.transcribe.models import TranscriptResult
    from src.clip_engine.scene_detector import WhisperSegmentDetector
    from src.clip_engine.scorer import ScoreEngine
    from src.clip_engine.filter import ClipFilter
    from src.clip_engine.planner import DurationPlanner
    from src.clip_engine.reviewer import FinalReviewer
    from src.edit.clipper import Clipper
    from src.analyze.llm_analyzer import LLMAnalyzer

    console.print("[bold]Step 1/7[/bold]: Scene Detection...")

    # 加载字幕
    transcript = TranscriptResult.from_json(transcript_path)
    console.print(
        f"[dim]加载 {len(transcript.segments)} 个 segments[/dim]"
    )

    # Scene 检测
    detector = WhisperSegmentDetector()
    scenes = detector.detect_scenes(transcript.segments)
    console.print(
        f"[green]✓[/green] 检测到 {len(scenes)} 个场景"
    )
    console.rule()

    console.print("[bold]Step 2/7[/bold]: LLM Scene 标注...")

    # LLM 标注
    analyzer = LLMAnalyzer(
        provider=llm_config.get("provider", "llama_cpp"),
        model=llm_config.get("model", "Qwen3.6-27B-Q4_K_M.gguf"),
        endpoint=llm_config.get("endpoint", "http://localhost:8080/v1"),
        api_key=llm_config.get("api_key", ""),
        temperature=llm_config.get("temperature", 0.3),
        max_tokens=llm_config.get("max_tokens", 16384),
        timeout=llm_config.get("timeout", 600),
        context_size=llm_config.get("context_size", 131072),
    )
    scenes = analyzer.analyze_scenes(
        scenes,
        user_prompt=user_prompt,
    )
    console.rule()

    console.print("[bold]Step 3/7[/bold]: Score Engine...")

    # 评分
    clip_mode = mode or "viral"
    preset_name = preset or "viral"
    scorer = ScoreEngine(preset=preset_name, clip_mode=clip_mode)
    candidates = scorer.compute(scenes)
    console.print(
        f"[green]✓[/green] 生成 {len(candidates)} 个候选, "
        f"最高分: {candidates[0].composite_score if candidates else 0:.2f}"
    )
    console.rule()

    console.print("[bold]Step 4/7[/bold]: Filter Engine...")

    # 筛选（Filter Engine 阶段不设置 target_duration，留给 Duration Planner）
    filter_target_duration = 0.0 if use_duration_planner else target_duration
    clip_filter = ClipFilter(
        min_gap=min_gap,
        max_clips=num_clips,
        target_duration=filter_target_duration,
    )
    selected = clip_filter.filter(candidates)

    total_dur = sum(c.duration for c in selected)
    console.print(
        f"[green]✓[/green] 选中 {len(selected)} 个片段, "
        f"总时长: {total_dur:.1f} 秒"
    )
    console.rule()

    # ─── Step 5: Duration Planner（可选）────
    if use_duration_planner and target_duration > 0 and selected:
        console.print("[bold]Step 5/7[/bold]: Duration Planner...")

        planner = DurationPlanner(
            target_duration=target_duration,
            min_gap=min_gap,
        )
        plan_result = planner.plan(selected)

        selected = plan_result.selected
        total_dur = plan_result.total_duration

        console.print(
            f"[green]✓[/green] 时长规划完成: {len(selected)} 个片段, "
            f"总时长 {total_dur:.1f}s / 目标 {target_duration:.0f}s "
            f"(得分 {plan_result.score:.1f})"
        )

        # 显示槽位信息
        for slot_info in plan_result.slots_filled:
            c = slot_info.get("candidate")
            if c:
                console.print(
                    f"  [dim]  {slot_info['role']:>10s} | "
                    f"场景 #{c.scene_id} | "
                    f"{c.duration:.1f}s | "
                    f"分 {c.composite_score:.2f}[/dim]"
                )
        console.rule()
    else:
        # 跳过 Step 5，调整后续步骤编号
        _step_offset = 0

    # ─── Step 6: LLM Final Review（可选）────
    if use_final_review and selected:
        console.print("[bold]Step 6/7[/bold]: LLM Final Review...")

        review_num = final_review_count or (
            num_clips if num_clips > 0 else None
        )
        reviewer = FinalReviewer(
            llm_analyzer=analyzer,
            num_to_select=review_num,
            platform=preset_name,
            target_duration=target_duration,
            user_prompt=user_prompt,
        )
        review_result = reviewer.review(selected)
        selected = review_result.candidates

        total_dur = sum(c.duration for c in selected)
        if review_result.overall_comment:
            console.print(
                f"  [dim]评审: {review_result.overall_comment}[/dim]"
            )
        console.print(
            f"[green]✓[/green] Final Review 完成: "
            f"{len(selected)} 个片段, 总时长 {total_dur:.1f} 秒"
        )
        console.rule()

    # ─── Step 7: ffmpeg 剪辑 ───
    console.print("[bold]Step 7/7[/bold]: ffmpeg 剪辑...")

    # 剪辑
    clipper = Clipper(
        ffmpeg_path=ffmpeg_config.get("path", "ffmpeg"),
        ffprobe_path=ffmpeg_config.get("probe_path", "ffprobe"),
    )

    # 构建剪辑时间列表
    clip_times = [(c.start, c.end) for c in selected]

    # 确定输出目录
    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = Path(video_path).parent / "clips"

    out_dir.mkdir(parents=True, exist_ok=True)

    # 执行剪辑
    from src.edit.clipper import ClipBatchResult

    result = ClipBatchResult()

    # 裁剪独立片段
    base_name = Path(video_path).stem
    for i, (start, end) in enumerate(clip_times):
        try:
            clip_file = out_dir / f"{base_name}_clip_{i+1:02d}.mp4"
            clip_result = clipper.extract_segment(
                video_path=video_path,
                start=start,
                end=end,
                output_path=clip_file,
            )
            result.clips.append(clip_result)
        except Exception as e:
            result.errors.append(f"片段 {i+1} 裁剪失败: {str(e)[:100]}")

    # 拼接精华视频
    if merge and len(clip_times) > 1:
        try:
            merged_file = out_dir / f"{base_name}_highlight.mp4"
            clip_paths = [c.clip_path for c in result.clips if c.success]
            merge_result = clipper.merge_clips(
                clip_paths=clip_paths,
                output_path=merged_file,
                transition=transition if transition > 0 else None,
            )
            result.merged_path = merge_result
        except Exception as e:
            result.errors.append(f"拼接失败: {str(e)[:100]}")

    return result


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
    # ─── Smart Clip Engine v2.0 参数 ───
    mode: str | None = typer.Option(
        None, "--mode",
        help="剪辑模式: comedy/action/emotion/dialogue/knowledge/hook/viral/all",
    ),
    preset: str | None = typer.Option(
        None, "--preset",
        help="平台预设权重: douyin/youtube/bilibili/viral/all",
    ),
    num_clips: int = typer.Option(
        0, "--clips",
        help="输出片段数量（0 表示不限制）",
    ),
    duration: str | None = typer.Option(
        None, "--duration",
        help="目标成片时长（如 60s, 3m, 180s）",
    ),
    prompt: str | None = typer.Option(
        None, "--prompt",
        help="自定义 prompt，注入到 LLM 标注中（如 '切情侣吵架片段'）",
    ),
    min_gap: float = typer.Option(
        120.0, "--min-gap",
        help="Diversity 去重最小间隔（秒），默认 120 秒",
    ),
    use_smart_clip: bool = typer.Option(
        False, "--smart-clip",
        help="启用 Smart Clip Engine v2.0（需要字幕 JSON + 视频）",
    ),
    transcript_path: str | None = typer.Option(
        None, "--transcript",
        help="字幕 JSON 路径（--smart-clip 时需要）",
    ),
    use_duration_planner: bool = typer.Option(
        False, "--duration-planner",
        help="启用 Duration Planner（按目标时长智能组合片段）",
    ),
    final_review: bool = typer.Option(
        False, "--final-review",
        help="启用 LLM Final Review（二阶段筛选，对候选做最终精选和排序）",
    ),
    final_review_count: int | None = typer.Option(
        None, "--final-review-count",
        help="Final Review 精选的片段数量（不指定则使用 --clips 的值）",
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

      # Smart Clip Engine v2.0: 按模式筛选
      videoagent clip report.json -v input.mp4 --smart-clip \\
          --transcript subtitles.json --mode comedy --clips 5 --preset douyin

      # 按目标时长筛选
      videoagent clip report.json -v input.mp4 --smart-clip \\
          --transcript subtitles.json --duration 60s --mode viral

      # 启用 Duration Planner（智能时长组合）
      videoagent clip report.json -v input.mp4 --smart-clip \\
          --transcript subtitles.json --duration 180s --duration-planner

      # 启用 LLM Final Review（二阶段筛选）
      videoagent clip report.json -v input.mp4 --smart-clip \\
          --transcript subtitles.json --final-review --clips 5

      # 组合使用：时长规划 + Final Review
      videoagent clip report.json -v input.mp4 --smart-clip \\
          --transcript subtitles.json --duration 60s \\
          --duration-planner --final-review --clips 3
    """
    config = load_config()
    ffmpeg_config = config.get("ffmpeg", {})

    console.print(f"[bold blue]VideoAgent[/bold blue] - 提取亮点片段")
    console.print(f"  报告: {report_path}")
    console.print(f"  ffmpeg: {ffmpeg_config.get('path', 'ffmpeg')}")

    # 解析 duration 参数
    target_duration = _parse_duration(duration) if duration else 0.0

    # ─── Smart Clip Engine v2.0 模式 ───
    if use_smart_clip:
        if not transcript_path:
            console.print(
                "[red]✗[/red] --smart-clip 模式需要 --transcript 参数指定字幕 JSON 路径"
            )
            raise typer.Exit(1)

        console.print("[bold]Smart Clip Engine v2.0[/bold]")
        console.print(f"  模式: {mode or 'viral'}")
        console.print(f"  预设: {preset or 'viral'}")
        if num_clips > 0:
            console.print(f"  片段数: {num_clips}")
        if target_duration > 0:
            console.print(f"  目标时长: {target_duration:.0f} 秒")
            console.print(f"  Duration Planner: {'启用' if use_duration_planner else '禁用'}")
        if prompt:
            console.print(f"  自定义指令: {prompt}")
        console.print(f"  Diversity 间隔: {min_gap:.0f} 秒")
        console.print(f"  LLM Final Review: {'启用' if final_review else '禁用'}")
        console.rule()

        clip_result = _run_smart_clip(
            transcript_path=transcript_path,
            video_path=video_path or _get_video_path_from_report(report_path),
            output_dir=output_dir,
            mode=mode,
            preset=preset,
            num_clips=num_clips,
            target_duration=target_duration,
            user_prompt=prompt,
            min_gap=min_gap,
            merge=merge,
            transition=transition,
            ffmpeg_config=ffmpeg_config,
            llm_config=config.get("llm", {}),
            use_duration_planner=use_duration_planner,
            use_final_review=final_review,
            final_review_count=final_review_count,
        )

    else:
        # ─── 传统模式（兼容现有行为） ───
        clipper = _build_clipper(ffmpeg_config)

        if output_dir:
            output_dir = Path(output_dir)

        clip_result = clipper.clips_from_report(
            report_path=report_path,
            video_path=video_path,
            output_dir=output_dir,
            merge=merge,
            merge_transition=transition if merge else None,
            filter_by_score=min_score,
        )

    console.print(f"\n[green]✓[/green] 剪辑完成")
    console.print(f"  成功: {clip_result.success_count} 个片段")
    console.print(f"  总时长: {clip_result.total_duration:.1f} 秒")

    if clip_result.clips:
        console.print(f"\n  独立片段:")
        for c in clip_result.clips:
            status = "[green]✓[/green]" if c.success else "[red]✗[/red]"
            console.print(
                f"    {status} {c.clip_path.name} "
                f"({c.start:.1f}s - {c.end:.1f}s, {c.duration:.1f}s)"
            )

    if clip_result.merged_path:
        console.print(f"\n  精华视频: [green]{clip_result.merged_path}[/green]")

    if clip_result.errors:
        console.print(f"\n  错误:")
        for err in clip_result.errors:
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
    # ─── Smart Clip Engine v2.0 参数 ───
    smart_clip: bool = typer.Option(
        False, "--smart-clip",
        help="启用 Smart Clip Engine v2.0 剪辑（覆盖 --clip）",
    ),
    mode: str | None = typer.Option(
        None, "--mode",
        help="剪辑模式: comedy/action/emotion/dialogue/knowledge/hook/viral/all",
    ),
    preset: str | None = typer.Option(
        None, "--preset",
        help="平台预设权重: douyin/youtube/bilibili/viral/all",
    ),
    num_clips: int = typer.Option(
        0, "--clips",
        help="输出片段数量（0 表示不限制）",
    ),
    duration: str | None = typer.Option(
        None, "--duration",
        help="目标成片时长（如 60s, 3m, 180s）",
    ),
    prompt: str | None = typer.Option(
        None, "--prompt",
        help="自定义 prompt，注入到 LLM 标注中",
    ),
    use_duration_planner: bool = typer.Option(
        False, "--duration-planner",
        help="启用 Duration Planner（按目标时长智能组合片段）",
    ),
    final_review: bool = typer.Option(
        False, "--final-review",
        help="启用 LLM Final Review（二阶段筛选）",
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

      # Smart Clip Engine v2.0 全流程
      videoagent pipeline input.mp4 --smart-clip --mode comedy --clips 5 --preset douyin
    """
    config = load_config()

    console.print("[bold blue]VideoAgent[/bold blue] - 全流程处理")
    console.print(f"  视频: {video_path}")
    console.print(f"  语言: {language or 'auto'}")
    console.print(f"  剪辑: {'Smart Clip v2.0' if smart_clip else ('传统' if clip else '否')}")
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
    # Stage 3: clip (optional)
    if clip or smart_clip:
        console.print("[bold]Stage 3/3[/bold]: clipping...")

        if smart_clip:
            # Smart Clip Engine v2.0
            target_duration = _parse_duration(duration) if duration else 0.0

            clip_result = _run_smart_clip(
                transcript_path=str(subtitle_json_path),
                video_path=video_path,
                output_dir=str(output_dir / "clips"),
                mode=mode,
                preset=preset,
                num_clips=num_clips,
                target_duration=target_duration,
                user_prompt=prompt,
                merge=True,
                transition=0.5,
                ffmpeg_config=config.get("ffmpeg", {}),
                llm_config=llm_config,
                use_duration_planner=use_duration_planner,
                use_final_review=final_review,
                final_review_count=num_clips if num_clips > 0 else None,
            )
        else:
            # Traditional clip
            ffmpeg_config = config.get("ffmpeg", {})
            clipper = _build_clipper(ffmpeg_config)

            clip_result = clipper.clips_from_report(
                report_path=report_json_path,
                video_path=video_path,
                filter_by_score=min_score,
            )

        console.print(f"[green]Done[/green] clipping")
        console.print(f"  Success: {clip_result.success_count} clips")

        for c in clip_result.clips:
            status = "[green]OK[/green]" if c.success else "[red]FAIL[/red]"
            console.print(
                f"    {status} {c.clip_path.name} "
                f"({c.start:.1f}s - {c.end:.1f}s)"
            )

        if clip_result.merged_path:
            console.print(f"  Highlight video: [green]{clip_result.merged_path}[/green]")

        if clip_result.errors:
            for err in clip_result.errors:
                console.print(f"    [red]FAIL[/red] {err}")

        console.rule()

    console.print("[bold green]Pipeline complete![/bold green]")
    console.print(f"  SRT:  {srt_path}")
    console.print(f"  JSON: {subtitle_json_path}")
    console.print(f"  Report JSON: {report_json_path}")
    console.print(f"  Report MD: {report_md_path}")


@app.command(name="batch")
def batch(
    input_path: str = typer.Argument(..., help="Video file/dir/glob pattern"),
    language: str | None = typer.Option(None, "--language", "-l"),
    output_dir: str | None = typer.Option(None, "--output-dir", "-o"),
    clip: bool = typer.Option(False, "--clip"),
    min_score: float | None = typer.Option(None, "--min-score"),
    merge_clips: bool = typer.Option(True, "--merge/--no-merge"),
    transition: float = typer.Option(0.5, "--transition"),
):
    """Batch process multiple videos"""
    from src.batch import run_batch

    output_dir = get_output_dir(output_dir)

    console.print(f"[bold blue]VideoAgent[/bold blue] - Batch")
    console.print(f"  Input: {input_path}")
    console.print(f"  Output: {output_dir}")
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

    console.print(f"\n[bold green]Batch complete![/bold green]")
    console.print(f"  Success: {result.success_count}/{len(result.items)}")
    if result.summary_csv_path:
        console.print(f"  CSV: {result.summary_csv_path}")


@app.command(name="version")
def version():
    """Show version"""
    from src import __version__
    console.print(f"VideoAgent v{__version__}")


if __name__ == "__main__":
    app()
