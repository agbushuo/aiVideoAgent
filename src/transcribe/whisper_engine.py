"""Whisper 转录引擎

封装 openai-whisper，提供模型加载、视频转录、字幕导出功能。
支持分段转录（Segment-aware），自动处理超长视频。

torch 和 whisper 使用延迟导入，避免在导入模块时就加载重型依赖。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from src.transcribe.models import TranscriptResult

console = Console()


class WhisperEngine:
    """Whisper 转录引擎（支持分段转录）"""

    def __init__(
        self,
        model_path: str | None = None,
        model_name: str = "large-v3",
        device: str = "auto",
        fp16: bool = True,
        # 分段转录配置
        chunk_duration: float = 900.0,        # chunk 时长（秒），默认 15 分钟
        overlap: float = 10.0,                # overlap 时长（秒），默认 10 秒
        segment_threshold_minutes: float = 30.0,  # 分段阈值（分钟），默认 30 分钟
        similarity_threshold: float = 0.8,    # 去重相似度阈值
        normalize_loudness: bool = False,     # 是否响度归一化
        # ffmpeg 路径
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
        # Whisper 参数优化（3.5）
        beam_size: int = 5,                  # beam search 大小
        temperature_fallback: bool = True,   # 是否使用 temperature fallback
    ):
        self.model_name = model_name
        self.device = self._resolve_device(device)
        self.fp16 = fp16 and self.device == "cuda"
        self.model_path = model_path
        self._model = None

        # 分段转录配置
        self.chunk_duration = chunk_duration
        self.overlap = overlap
        self.segment_threshold_minutes = segment_threshold_minutes
        self.similarity_threshold = similarity_threshold
        self.normalize_loudness = normalize_loudness

        # ffmpeg 路径
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path

        # Whisper 参数优化
        self.beam_size = beam_size
        self.temperature_fallback = temperature_fallback

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device == "auto":
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device

    def load_model(self):
        import whisper

        if self._model is not None:
            return self._model

        console.print(f"[dim]加载 Whisper 模型: {self.model_name}[/dim]")
        console.print(f"  设备: {self.device}")
        if self.model_path:
            console.print(f"  路径: {self.model_path}")

        start = time.time()

        if self.model_path:
            model = whisper.load_model(self.model_path, device=self.device)
        else:
            model = whisper.load_model(self.model_name, device=self.device)

        elapsed = time.time() - start
        console.print(f"[green]✓[/green] 模型加载完成 ({elapsed:.1f}秒)")

        self._model = model
        return model

    def transcribe(
        self,
        audio_path: str | Path,
        language: str | None = None,
        verbose: bool = False,
    ) -> "TranscriptResult":
        """
        转录音频/视频，自动判断是否使用分段策略。

        流程：
        1. 检测音频时长
        2. 如果超过阈值 → 分段转录（提取音频 → 切分 → 逐 chunk 转录 → 去重合并）
        3. 如果未超过阈值 → 直接转录（原有逻辑）

        Args:
            audio_path: 音频或视频文件路径
            language: 语言代码（None 则让 Whisper 自动检测）
            verbose: 是否打印详细日志

        Returns:
            TranscriptResult
        """
        from src.transcribe.models import TranscriptResult

        model = self.load_model()
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"文件不存在: {audio_path}")

        # 检测是否需要分段
        needs_segmented = self._check_needs_segmented(audio_path)

        if needs_segmented:
            console.print(f"\n[yellow]! 检测到长视频，启用分段转录策略[/yellow]")
            console.print(
                f"  chunk 大小: {self.chunk_duration / 60:.1f} 分钟, "
                f"overlap: {self.overlap} 秒"
            )
            return self._transcribe_segmented(
                audio_path, language=language, verbose=verbose
            )
        else:
            return self._transcribe_direct(
                model, audio_path, language=language, verbose=verbose
            )

    def _check_needs_segmented(self, input_path: Path) -> bool:
        """检查是否需要分段转录"""
        from src.utils.audio_preprocess import (
            get_audio_duration,
            should_segment_transcribe,
        )

        try:
            duration = get_audio_duration(input_path, self.ffprobe_path)
        except Exception:
            # 如果检测失败，回退到直接转录
            console.print("[dim]无法检测音频时长，使用直接转录[/dim]")
            return False

        needs = should_segment_transcribe(
            duration,
            segment_threshold_minutes=self.segment_threshold_minutes,
        )

        if needs:
            console.print(
                f"[dim]音频时长: {duration / 60:.1f} 分钟 "
                f"(阈值: {self.segment_threshold_minutes} 分钟) → 分段转录[/dim]"
            )
        else:
            console.print(
                f"[dim]音频时长: {duration / 60:.1f} 分钟 "
                f"(阈值: {self.segment_threshold_minutes} 分钟) → 直接转录[/dim]"
            )

        return needs

    def _transcribe_direct(
        self,
        model: Any,
        audio_path: Path,
        language: str | None = None,
        verbose: bool = False,
    ) -> "TranscriptResult":
        """直接转录（原有逻辑，适用于短视频）"""
        from src.transcribe.models import TranscriptResult

        console.print(f"\n[dim]开始转录: {audio_path.name}[/dim]")
        if language:
            console.print(f"[dim]  语言: {language}[/dim]")
        else:
            console.print("[dim]  语言: auto-detect[/dim]")
        start = time.time()

        result = model.transcribe(
            str(audio_path),
            language=language,
            fp16=self.fp16,
            verbose=verbose,
            beam_size=self.beam_size,
            temperature=[0] if not self.temperature_fallback else [0, 0.5],
        )

        elapsed = time.time() - start
        detected_lang = result.get("language", "unknown")

        segments = result.get("segments", [])
        duration = segments[-1]["end"] if segments else 0.0

        transcript = TranscriptResult.from_whisper_result(result, duration)

        console.print(f"[green]✓[/green] 转录完成 ({elapsed:.1f}秒)")
        console.print(f"  检测语言: {detected_lang}")
        console.print(f"  片段数: {len(transcript.segments)}")
        console.print(f"  时长: {duration:.1f}秒")

        return transcript

    def _transcribe_segmented(
        self,
        input_path: Path,
        language: str | None = None,
        verbose: bool = False,
    ) -> "TranscriptResult":
        """
        分段转录流程：

        1. 音频预处理：提取 16kHz mono WAV
        2. (可选) 响度归一化
        3. 音频切分为 chunks（带 overlap）
        4. 逐 chunk 转录
        5. 全局时间戳偏移 + segment 级去重合并
        6. 清理临时文件
        """
        from src.transcribe.merger import (
            ChunkTranscript,
            merge_chunk_transcripts,
        )
        from src.transcribe.models import TranscriptResult
        from src.utils.audio_preprocess import (
            chunk_audio,
            preprocess_audio_for_transcribe,
        )

        overall_start = time.time()

        # Step 1: 音频预处理
        console.print("[dim]Step 1: 音频预处理...[/dim]")
        preprocess_result = preprocess_audio_for_transcribe(
            input_path,
            ffmpeg_path=self.ffmpeg_path,
            ffprobe_path=self.ffprobe_path,
            normalize_loudness=self.normalize_loudness,
            segment_threshold_minutes=self.segment_threshold_minutes,
        )
        console.print(
            f"[dim]  音频: {preprocess_result.audio_path.name}, "
            f"时长: {preprocess_result.duration / 60:.1f} 分钟[/dim]"
        )

        # Step 2: 音频切分
        console.print("[dim]Step 2: 音频切分...[/dim]")
        chunks = chunk_audio(
            preprocess_result.audio_path,
            chunk_duration=self.chunk_duration,
            overlap=self.overlap,
            ffmpeg_path=self.ffmpeg_path,
            ffprobe_path=self.ffprobe_path,
        )
        console.print(f"[dim]  切分为 {len(chunks)} 个 chunk[/dim]")

        # Step 3: 逐 chunk 转录
        model = self._model  # 已加载
        chunk_transcripts: list[ChunkTranscript] = []
        detected_language: str | None = None

        for i, chunk in enumerate(chunks):
            chunk_start = time.time()
            # 第一个 chunk 用用户指定的语言（可为 auto），后续 chunk 统一用第一个检测到的语言
            # 避免方言场景下各 chunk 语言检测结果不一致
            chunk_language = detected_language if detected_language is not None else language

            console.print(
                f"[dim]Step 3: 转录 chunk {i + 1}/{len(chunks)} "
                f"({chunk.start_time:.0f}s - {chunk.end_time:.0f}s)"
                f"[language={chunk_language or 'auto'}][/dim]"
            )

            whisper_result = model.transcribe(
                str(chunk.path),
                language=chunk_language,
                fp16=self.fp16,
                verbose=verbose,
                beam_size=self.beam_size,
                temperature=[0] if not self.temperature_fallback else [0, 0.5],
            )

            # 从第一个 chunk 获取检测到的语言
            if detected_language is None:
                detected_language = whisper_result.get("language")

            segments = []
            for seg in whisper_result.get("segments", []):
                from src.transcribe.models import Segment
                segments.append(Segment.from_whisper_segment(seg))

            chunk_elapsed = time.time() - chunk_start
            console.print(
                f"[dim]  chunk {i + 1} 转录完成 "
                f"({len(segments)} segments, {chunk_elapsed:.1f}秒)[/dim]"
            )

            chunk_transcripts.append(ChunkTranscript(
                segments=segments,
                chunk_start_time=chunk.start_time,
                chunk_index=i,
            ))

        # Step 4: 合并去重
        console.print("[dim]Step 4: 合并去重...[/dim]")
        transcript, stats = merge_chunk_transcripts(
            chunk_transcripts,
            language=detected_language or language,
            total_duration=preprocess_result.duration,
            similarity_threshold=self.similarity_threshold,
        )

        overall_elapsed = time.time() - overall_start

        console.print(f"[green]✓[/green] 分段转录完成 ({overall_elapsed:.1f}秒)")
        console.print(f"  检测语言: {transcript.language}")
        console.print(f"  总片段数: {len(transcript.segments)}")
        console.print(f"  总时长: {transcript.duration:.1f}秒")
        console.print(
            f"  合并统计: {stats.total_segments_before} → {stats.total_segments_after} "
            f"(移除 {stats.duplicates_removed} 个重复)"
        )

        return transcript

    def unload(self):
        import torch

        if self._model is not None:
            del self._model
            self._model = None
            if self.device == "cuda":
                torch.cuda.empty_cache()
            console.print("[dim]模型已释放[/dim]")
