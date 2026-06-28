// Scene & ClipCandidate types

export interface Scene {
  scene_id: number;
  start: number;
  end: number;
  duration: number;
  segment_ids: number[];
  text: string;
  scene_type: string;
  tags: string[];
  summary: string;
  multi_score: Record<string, number>;
}

export interface SceneListResponse {
  total: number;
  scenes: Scene[];
}

export interface SceneUpdateRequest {
  scene_type?: string;
  tags?: string[];
  summary?: string;
  multi_score?: Record<string, number>;
}

export interface ClipCandidate {
  scene: Scene;
  composite_score: number;
  rank: number;
  selected: boolean;
}

export interface CandidateListResponse {
  total: number;
  candidates: ClipCandidate[];
}

export interface BulkSelectRequest {
  scene_ids: number[];
  selected: boolean;
}

// Scene types from the engine
export const SCENE_TYPES = [
  "Dialogue", "Comedy", "Fight", "Emotion", "Knowledge",
  "Suspense", "Climax", "Hook", "Other",
];

export const MULTI_SCORE_DIMENSIONS = [
  "hook", "emotion", "comedy", "action",
  "information", "suspense", "climax", "viral",
];
