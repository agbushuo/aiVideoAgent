// Pipeline stage definition

export interface PipelineStageInfo {
  stage_id: string;
  label: string;
  description: string;
  icon: string;
  default_params: Record<string, unknown>;
  dependencies: string[];
}

export const STAGE_IDS = [
  "transcribe",
  "scene_detection",
  "llm_annotation",
  "scoring",
  "filtering",
  "duration_planning",
  "final_review",
  "clipping",
] as const;

export type StageId = (typeof STAGE_IDS)[number];
