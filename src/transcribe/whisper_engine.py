"""Whisper 转录引擎

封装 openai-whisper，提供模型加载、视频转录、字幕导出功能。
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
    """Whisper 转录引擎"""

    def __init__(
        self,
        model_path: str | None = None,
        model_name: str = "large-v3",
        device: str = "auto",
        fp16: bool = True,
    ):
        self.model_name = model_name
        self.device = self._resolve_device(device)
        self.fp16 = fp16 and self.device == "cuda"
        self.model_path = model_path
        self._model = None

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
        language: str = "zh",
        verbose: bool = False,
    ) -> "TranscriptResult":
        from src.transcribe.models import TranscriptResult

        model = self.load_model()
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"文件不存在: {audio_path}")

        console.print(f"\n[dim]开始转录: {audio_path.name}[/dim]")
        start = time.time()

        result = model.transcribe(
            str(audio_path),
            language=language,
            fp16=self.fp16,
            verbose=verbose,
        )

        elapsed = time.time() - start
        detected_lang = result.get("language", language)

        segments = result.get("segments", [])
        duration = segments[-1]["end"] if segments else 0.0

        transcript = TranscriptResult.from_whisper_result(result, duration)

        console.print(f"[green]✓[/green] 转录完成 ({elapsed:.1f}秒)")
        console.print(f"  检测语言: {detected_lang}")
        console.print(f"  片段数: {len(transcript.segments)}")
        console.print(f"  时长: {duration:.1f}秒")

        return transcript

    def unload(self):
        import torch

        if self._model is not None:
            del self._model
            self._model = None
            if self.device == "cuda":
                torch.cuda.empty_cache()
            console.print("[dim]模型已释放[/dim]")
