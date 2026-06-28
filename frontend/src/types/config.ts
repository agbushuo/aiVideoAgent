// Config reference data types

export interface PresetInfo {
  name: string;
  weights: Record<string, number>;
}

export interface PresetData {
  name: string;
  displayName: string;
  description: string;
  stageParams: Record<string, Record<string, unknown>>;
  weights: Record<string, number>;
  prompts: Record<string, string>;
}

export interface ClipModeInfo {
  name: string;
  weights: Record<string, number>;
}

export interface ScoreDimensionInfo {
  name: string;
  description: string;
}

export interface DurationTemplate {
  name: string;
  duration_seconds: number;
  num_clips: number;
}

export interface PromptInfo {
  name: string;
  hasContent: boolean;
}

export interface ConfigResponse<T> {
  items: T[];
}
