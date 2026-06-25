"""Score Engine - Multi-dimensional scoring + preset weight calculation

Calculates composite scores for ClipCandidates based on preset weights.

Weight system:
- Preset weights: douyin, youtube, bilibili, viral, all
- Clip Mode weights: comedy, action, emotion, dialogue, knowledge, hook, viral, all
- Custom weights: via dict or JSON file
- External config: loads from weights.json, supports ~/.videoagent/weights.json override

Data flow:
    Scene[].multi_score -> ScoreEngine.compute() -> ClipCandidate[].composite_score
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.clip_engine.models import ClipCandidate, MULTI_SCORE_DIMENSIONS, Scene


# ===================================================================== #
# Weight loading
# ===================================================================== #

_DEFAULT_WEIGHTS_PATH = Path(__file__).parent / "weights.json"
_USER_WEIGHTS_PATH = Path.home() / ".videoagent" / "weights.json"


def _load_weights_file(path: Path) -> dict[str, Any]:
    """Load weight config from JSON file"""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _merge_weights(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge two weight configs (user overrides default)"""
    if not override:
        return base
    merged = {
        "preset": dict(base.get("preset", {})),
        "clip_mode": dict(base.get("clip_mode", {})),
    }
    user_presets = override.get("preset", {})
    if user_presets:
        merged["preset"].update(user_presets)
    user_modes = override.get("clip_mode", {})
    if user_modes:
        merged["clip_mode"].update(user_modes)
    return merged


def _get_all_weights() -> dict[str, Any]:
    """Load and merge all weight configs"""
    base = _load_weights_file(_DEFAULT_WEIGHTS_PATH)
    user = _load_weights_file(_USER_WEIGHTS_PATH)
    return _merge_weights(base, user)


# Module-level cache
_WEIGHTS_CACHE: dict[str, Any] | None = None


def _get_weights() -> dict[str, Any]:
    """Get weight config (cached)"""
    global _WEIGHTS_CACHE
    if _WEIGHTS_CACHE is None:
        _WEIGHTS_CACHE = _get_all_weights()
    return _WEIGHTS_CACHE


def reload_weights() -> None:
    """Reload weight config (clear cache)"""
    global _WEIGHTS_CACHE
    _WEIGHTS_CACHE = None


def _get_preset_table() -> dict[str, dict[str, float]]:
    return _get_weights().get("preset", {})


def _get_clip_mode_table() -> dict[str, dict[str, float]]:
    return _get_weights().get("clip_mode", {})


# ===================================================================== #
# PresetWeights
# ===================================================================== #

@dataclass(frozen=True)
class PresetWeights:
    """Platform preset weight config"""

    name: str
    weights: dict[str, float]

    @classmethod
    def get(cls, name: str) -> "PresetWeights":
        """Get preset weights by name"""
        table = _get_preset_table()
        if name not in table:
            available = ", ".join(table.keys())
            raise ValueError(f"Unknown preset: '{name}'. Available: {available}")
        return cls(name=name, weights=dict(table[name]))

    @classmethod
    def from_dict(cls, name: str, weights: dict[str, float]) -> "PresetWeights":
        """Create from custom weight dict"""
        normalized = _normalize_weights(weights)
        return cls(name=name, weights=normalized)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "PresetWeights":
        """Load custom weights from JSON file"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Weight file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Weight file root must be a JSON object")
        weights = {k: float(v) for k, v in data.items() if isinstance(v, (int, float))}
        if not weights:
            raise ValueError("No valid weight values found in file")
        return cls(name=path.stem, weights=weights)

    def compute_score(self, multi_score: dict[str, float]) -> float:
        """Compute composite score from multi-dimensional scores"""
        if not multi_score:
            return 0.0
        total_weighted = 0.0
        total_weight = 0.0
        for dim, weight in self.weights.items():
            score = multi_score.get(dim, 0.0)
            total_weighted += score * weight
            total_weight += weight
        if total_weight == 0:
            return 0.0
        return total_weighted / total_weight

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "weights": dict(self.weights)}


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize weights to sum to 1.0"""
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Weight sum must be > 0")
    return {k: v / total for k, v in weights.items()}


# ===================================================================== #
# ClipMode
# ===================================================================== #

@dataclass(frozen=True)
class ClipMode:
    """Clip mode - user-selected clip type via --mode"""

    name: str
    weights: dict[str, float]

    @classmethod
    def get(cls, name: str) -> "ClipMode":
        """Get clip mode by name"""
        table = _get_clip_mode_table()
        if name not in table:
            available = ", ".join(table.keys())
            raise ValueError(f"Unknown clip mode: '{name}'. Available: {available}")
        return cls(name=name, weights=dict(table[name]))

    @classmethod
    def list_available(cls) -> list[str]:
        """List all available clip mode names"""
        return list(_get_clip_mode_table().keys())


# ===================================================================== #
# Score Engine
# ===================================================================== #

class ScoreEngine:
    """Scoring engine

    Computes composite scores for Scenes using preset or clip mode weights.

    Usage:
        engine = ScoreEngine(preset="douyin")
        candidates = engine.compute(scenes)
    """

    def __init__(
        self,
        preset: str = "viral",
        clip_mode: str | None = None,
        custom_weights: dict[str, float] | None = None,
        weight_file: str | Path | None = None,
    ):
        """
        Args:
            preset: Preset weight name (douyin/youtube/bilibili/viral/all)
            clip_mode: Clip mode (overrides preset if set)
            custom_weights: Custom weight dict (highest priority)
            weight_file: JSON file path for custom weights
        """
        if custom_weights:
            self.weights = PresetWeights.from_dict("custom", custom_weights)
        elif weight_file:
            self.weights = PresetWeights.from_json_file(weight_file)
        elif clip_mode:
            mode = ClipMode.get(clip_mode)
            self.weights = PresetWeights(
                name=f"mode:{mode.name}", weights=mode.weights
            )
        else:
            self.weights = PresetWeights.get(preset)

    def compute(self, scenes: list[Scene]) -> list[ClipCandidate]:
        """Compute composite scores for all scenes"""
        candidates = []
        for scene in scenes:
            score = self.weights.compute_score(scene.multi_score)
            candidate = ClipCandidate(
                scene=scene,
                composite_score=round(score, 2),
            )
            candidates.append(candidate)

        candidates.sort(key=lambda c: c.composite_score, reverse=True)
        for rank, candidate in enumerate(candidates, start=1):
            candidate.rank = rank

        return candidates

    def compute_with_threshold(
        self, scenes: list[Scene], min_score: float = 0.0
    ) -> list[ClipCandidate]:
        """Compute scores and filter by minimum threshold"""
        return [c for c in self.compute(scenes) if c.composite_score >= min_score]


# ===================================================================== #
# Helper functions
# ===================================================================== #

def list_presets() -> list[str]:
    """List all available preset weight names"""
    return list(_get_preset_table().keys())


def show_preset(name: str) -> dict[str, float] | None:
    """Show weight details for a preset"""
    return _get_preset_table().get(name)
