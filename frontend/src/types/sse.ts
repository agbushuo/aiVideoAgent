// SSE event types

export type SSEEventType =
  | "task_status"
  | "stage_start"
  | "stage_complete"
  | "log"
  | "progress"
  | "error"
  | "pause"
  | "complete";

export interface SSEEvent {
  event_type: SSEEventType;
  data: Record<string, unknown>;
}

export interface SSELogData {
  task_id: string;
  level: string;
  message: string;
  stage?: string;
}

export interface SSEProgressData {
  task_id: string;
  step: string;
  step_detail?: string;
  percent: number;
}

export interface SSEStageData {
  task_id: string;
  stage_id: string;
  stage_name?: string;
  artifacts?: Record<string, string>;
  duration?: number;
}

export interface SSEErrorData {
  task_id: string;
  stage_id?: string;
  error: string;
  traceback?: string;
}
