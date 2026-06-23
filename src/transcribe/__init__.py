"""Whisper 转录模块"""

from src.transcribe.models import Segment, TranscriptResult


def __getattr__(name):
    if name == "WhisperEngine":
        from src.transcribe.whisper_engine import WhisperEngine
        return WhisperEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["WhisperEngine", "TranscriptResult", "Segment"]
