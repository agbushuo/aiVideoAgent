// Task-related types matching src/web/api_schemas.py & task_manager.py

export type TaskStatus =
  | "pending"
  | "transcribing"
  | "review_subtitles"
  | "analyzing"
  | "scoring"
  | "filtering"
  | "clipping"
  | "completed"
  | "cancelled"
  | "error";

export interface TaskProgress {
  step: string;
  step_detail: string;
  percent: number;
}

export interface LogEntry {
  timestamp: number;
  level: "info" | "warning" | "error" | "success";
  message: string;
  step: string;
}

export interface PipelineStageConfig {
  stage_id: string;
  enabled: boolean;
  params: Record<string, unknown>;
}

export interface PipelineConfig {
  stages: PipelineStageConfig[];
}

export interface TaskCreateRequest {
  video_path: string;
  language?: string;
  review_enabled?: boolean;
  output_dir?: string;
  pipeline_config?: PipelineConfig | null;
  skip_existing_transcript?: boolean;
  smart_clip?: boolean;
  clip_mode?: string;
  preset?: string;
  num_clips?: number;
  target_duration?: number;
  user_prompt?: string | null;
  use_duration_planner?: boolean;
  use_final_review?: boolean;
  min_score?: number | null;
  merge_clips?: boolean;
  transition_duration?: number;
}

export interface TaskResponse {
  task_id: string;
  status: TaskStatus;
  video_path: string;
  output_dir: string;
  progress: TaskProgress;
  stage_results: Record<string, StageResult>;
}

export interface TaskDetailResponse extends TaskResponse {
  logs: LogEntry[];
  output_files: Record<string, string>;
  pipeline_config?: PipelineConfig | null;
}

// Simplified task list item
export interface TaskListItem {
  task_id: string;
  status: TaskStatus;
  video_path: string;
  progress: {
    step: string;
    percent: number;
  };
}

export interface StageResult {
  stage_id: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  started_at: number | null;
  completed_at: number | null;
  duration_seconds: number | null;
  output_artifacts: Record<string, string>;
  error: string | null;
}
