// Workflow Builder form field types and stage schema mappings

import { StageId } from "@/types/stage";

export interface StageFieldConfig {
  key: string;
  label: string;
  type: "select" | "number" | "slider" | "textarea" | "checkbox" | "text";
  options?: { label: string; value: string | number }[];
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  description?: string;
}

// Node layout positions for the DAG (hierarchical arrangement)
export const NODE_LAYOUT: Record<string, { x: number; y: number }> = {
  transcribe: { x: 400, y: 0 },
  scene_detection: { x: 400, y: 180 },
  llm_annotation: { x: 400, y: 360 },
  scoring: { x: 400, y: 540 },
  filtering: { x: 400, y: 720 },
  duration_planning: { x: 200, y: 900 },
  final_review: { x: 600, y: 900 },
  clipping: { x: 400, y: 1080 },
};

// Base form schemas per stage (without dynamic options)
export const BASE_STAGE_SCHEMAS: Record<StageId, Omit<StageFieldConfig, "options">[]> = {
  transcribe: [
    { key: "language", label: "语言", type: "select", placeholder: "zh" },
    { key: "model_name", label: "模型", type: "text", placeholder: "whisper-large-v3" },
    { key: "device", label: "设备", type: "select" },
  ],
  scene_detection: [
    { key: "gap_threshold", label: "间隙阈值 (s)", type: "slider", min: 0, max: 30, step: 0.5 },
    { key: "min_scene_duration", label: "最小时长 (s)", type: "number", min: 1, max: 60 },
    { key: "max_scene_duration", label: "最长时间 (s)", type: "number", min: 10, max: 600 },
  ],
  llm_annotation: [
    { key: "user_prompt", label: "自定义提示", type: "textarea", placeholder: "可选的自定义指令..." },
  ],
  scoring: [
    { key: "preset", label: "平台预设", type: "select" },
    { key: "clip_mode", label: "剪辑模式", type: "select" },
  ],
  filtering: [
    { key: "max_clips", label: "最大片段数", type: "number", min: 0, description: "0 = 无限制" },
    { key: "min_gap", label: "最小间隔 (s)", type: "slider", min: 0, max: 600, step: 5 },
    { key: "target_duration", label: "目标时长 (s)", type: "number", min: 0, description: "0 = 不限制" },
  ],
  duration_planning: [
    { key: "target_duration", label: "目标时长 (s)", type: "number", min: 0 },
  ],
  final_review: [
    { key: "num_to_select", label: "精选数量", type: "number", min: 1, description: "null = 跳过" },
  ],
  clipping: [
    { key: "merge", label: "合并片段", type: "checkbox", description: "将片段合并为一个视频" },
    { key: "transition", label: "转场时长 (s)", type: "slider", min: 0, max: 3, step: 0.1 },
  ],
};

// Static select options
export const LANGUAGE_OPTIONS = [
  { label: "中文", value: "zh" },
  { label: "English", value: "en" },
  { label: "日本語", value: "ja" },
  { label: "한국어", value: "ko" },
];

export const DEVICE_OPTIONS = [
  { label: "CUDA (GPU)", value: "cuda" },
  { label: "CPU", value: "cpu" },
  { label: "MPS (Mac)", value: "mps" },
];

// Stage description text
export const STAGE_DESCRIPTIONS: Record<StageId, string> = {
  transcribe: "使用 Whisper 提取视频字幕并转录为文本",
  scene_detection: "基于字幕间隙检测场景边界",
  llm_annotation: "调用 LLM 对每个场景进行类型标注和摘要",
  scoring: "根据预设权重对场景进行多维度评分",
  filtering: "按评分、多样性、时长约束筛选候选片段",
  duration_planning: "按目标时长规划片段组合",
  final_review: "LLM 对候选片段进行最终精选",
  clipping: "使用 FFmpeg 剪辑视频并合并输出",
};

// ── English translations (for locale-aware rendering) ──

export const EN_BASE_STAGE_SCHEMAS: Record<StageId, Omit<StageFieldConfig, "options">[]> = {
  transcribe: [
    { key: "language", label: "Language", type: "select", placeholder: "zh" },
    { key: "model_name", label: "Model", type: "text", placeholder: "whisper-large-v3" },
    { key: "device", label: "Device", type: "select" },
  ],
  scene_detection: [
    { key: "gap_threshold", label: "Gap Threshold (s)", type: "slider", min: 0, max: 30, step: 0.5 },
    { key: "min_scene_duration", label: "Min Duration (s)", type: "number", min: 1, max: 60 },
    { key: "max_scene_duration", label: "Max Duration (s)", type: "number", min: 10, max: 600 },
  ],
  llm_annotation: [
    { key: "user_prompt", label: "Custom Prompt", type: "textarea", placeholder: "Optional custom instructions..." },
  ],
  scoring: [
    { key: "preset", label: "Preset", type: "select" },
    { key: "clip_mode", label: "Clip Mode", type: "select" },
  ],
  filtering: [
    { key: "max_clips", label: "Max Clips", type: "number", min: 0, description: "0 = unlimited" },
    { key: "min_gap", label: "Min Gap (s)", type: "slider", min: 0, max: 600, step: 5 },
    { key: "target_duration", label: "Target Duration (s)", type: "number", min: 0, description: "0 = no limit" },
  ],
  duration_planning: [
    { key: "target_duration", label: "Target Duration (s)", type: "number", min: 0 },
  ],
  final_review: [
    { key: "num_to_select", label: "Num to Select", type: "number", min: 1, description: "null = skip" },
  ],
  clipping: [
    { key: "merge", label: "Merge Clips", type: "checkbox", description: "Merge clips into a single video" },
    { key: "transition", label: "Transition (s)", type: "slider", min: 0, max: 3, step: 0.1 },
  ],
};

export const EN_STAGE_DESCRIPTIONS: Record<StageId, string> = {
  transcribe: "Extract video subtitles using Whisper",
  scene_detection: "Detect scene boundaries based on subtitle gaps",
  llm_annotation: "Annotate each scene with type, tags, and summary via LLM",
  scoring: "Multi-dimensional scoring based on preset weights",
  filtering: "Filter candidates by score, diversity, and duration",
  duration_planning: "Plan clip combinations by target duration",
  final_review: "LLM final selection and ranking of candidates",
  clipping: "Clip video segments and merge output with FFmpeg",
};

/**
 * Get stage schemas for a given locale.
 * NOTE: ConfigPanel should call this with the current locale to render localized labels.
 */
export function getStageSchemas(locale = "zh"): Record<StageId, Omit<StageFieldConfig, "options">[]> {
  return locale === "en" ? EN_BASE_STAGE_SCHEMAS : BASE_STAGE_SCHEMAS;
}

/**
 * Get stage descriptions for a given locale.
 */
export function getStageDescriptions(locale = "zh"): Record<StageId, string> {
  return locale === "en" ? EN_STAGE_DESCRIPTIONS : STAGE_DESCRIPTIONS;
}
