"""Smart Clip Engine v2.0 - Intelligent clip selection engine

Four-layer architecture:
    AI content understanding (LLM annotation) -> Rule engine (Score) -> Strategy engine (Filter/Planner) -> Final optimization (LLM Review)

Modules:
    models - Scene, ClipCandidate, ClipResult data models
    scene_detector - Whisper segment grouping + OpenCV interface
    scorer - Multi-dimensional scoring + preset weight calculation (JSON config)
    filter - Diversity dedup, count/duration constraints
    planner - Duration Planner (target duration clip combination)
    reviewer - LLM Final Review (two-stage filtering)
    weights.json - Preset weight config file

Note: Avoid importing submodules directly in __init__.py to prevent circular imports.
      Use explicit imports: from src.clip_engine.scorer import ScoreEngine
"""

# Export model classes only (no circular dependencies)
from src.clip_engine.models import (
    ClipCandidate,
    ClipResult,
    MULTI_SCORE_DIMENSIONS,
    SCENE_TYPES,
    Scene,
)

__all__ = [
    # Models
    "Scene",
    "ClipCandidate",
    "ClipResult",
    "MULTI_SCORE_DIMENSIONS",
    "SCENE_TYPES",
]
