/**
 * API client for VideoAgent backend
 * All requests go through Next.js rewrites to localhost:8501
 */

import {
  TaskCreateRequest,
  TaskListItem,
  TaskDetailResponse,
  StageResult,
} from "@/types/api";
import {
  Scene,
  SceneListResponse,
  SceneUpdateRequest,
  CandidateListResponse,
  BulkSelectRequest,
} from "@/types/scene";
import {
  Segment,
  TranscriptResponse,
  TranscriptUpdateRequest,
  SegmentUpdateRequest,
} from "@/types/transcript";
import { PipelineStageInfo } from "@/types/stage";
import {
  PresetInfo,
  PresetData,
  ClipModeInfo,
  ScoreDimensionInfo,
  DurationTemplate,
  ConfigResponse,
  PromptInfo,
} from "@/types/config";
import { SSEEvent } from "@/types/sse";

// =====================================================================
// Task Management
// =====================================================================

export async function listTasks(
  status?: string,
  limit = 50,
  offset = 0,
): Promise<TaskListItem[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (status) params.set("status", status);

  const res = await fetch(`/api/tasks?${params}`);
  if (!res.ok) throw new Error(`Failed to list tasks: ${res.statusText}`);
  return res.json();
}

export async function createTask(
  request: TaskCreateRequest,
): Promise<{ task_id: string; status: string; message: string }> {
  const res = await fetch("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error(`Failed to create task: ${res.statusText}`);
  return res.json();
}

export async function getTask(taskId: string): Promise<TaskDetailResponse> {
  const res = await fetch(`/api/tasks/${taskId}`);
  if (!res.ok) throw new Error(`Task not found: ${res.statusText}`);
  return res.json();
}

export async function deleteTask(taskId: string): Promise<{ status: string }> {
  const res = await fetch(`/api/tasks/${taskId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete task: ${res.statusText}`);
  return res.json();
}

export async function bulkDeleteTasks(
  taskIds: string[],
  deleteOutputs = false,
): Promise<{ deleted: number; output_dirs_removed: number; errors: Array<{ task_id: string; error: string }> }> {
  const params = new URLSearchParams({
    delete_outputs: String(deleteOutputs),
  });
  for (const id of taskIds) {
    params.append("task_ids", id);
  }
  const res = await fetch(`/api/tasks/bulk-delete?${params}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to bulk delete tasks: ${res.statusText}`);
  return res.json();
}

export async function resumeTask(taskId: string): Promise<{ status: string }> {
  const res = await fetch(`/api/tasks/${taskId}/resume`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to resume task: ${res.statusText}`);
  return res.json();
}

export async function cancelTask(taskId: string): Promise<{ status: string }> {
  const res = await fetch(`/api/tasks/${taskId}/cancel`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to cancel task: ${res.statusText}`);
  return res.json();
}

export async function rerunStage(
  taskId: string,
  stageId: string,
): Promise<StageResult> {
  const res = await fetch(
    `/api/tasks/${taskId}/rerun-stage?stage_id=${encodeURIComponent(stageId)}`,
    { method: "POST" },
  );
  if (!res.ok) throw new Error(`Failed to rerun stage: ${res.statusText}`);
  return res.json();
}

// =====================================================================
// Stage Execution
// =====================================================================

export async function listStages(taskId: string): Promise<StageResult[]> {
  const res = await fetch(`/api/tasks/${taskId}/stages`);
  if (!res.ok) throw new Error(`Failed to list stages: ${res.statusText}`);
  return res.json();
}

export async function getStage(
  taskId: string,
  stageId: string,
): Promise<StageResult> {
  const res = await fetch(`/api/tasks/${taskId}/stages/${stageId}`);
  if (!res.ok) throw new Error(`Stage not found: ${res.statusText}`);
  return res.json();
}

export async function runStage(
  taskId: string,
  stageId: string,
  params?: Record<string, unknown>,
): Promise<StageResult> {
  const res = await fetch(`/api/tasks/${taskId}/stages/${stageId}/run`, {
    method: "POST",
    headers: params ? { "Content-Type": "application/json" } : undefined,
    body: params ? JSON.stringify({ params }) : undefined,
  });
  if (!res.ok) throw new Error(`Failed to run stage: ${res.statusText}`);
  return res.json();
}

// =====================================================================
// Scene Data
// =====================================================================

export async function listScenes(
  taskId: string,
  options?: {
    tag?: string;
    min_score?: number;
    search?: string;
    sort?: "score" | "start";
    order?: "desc" | "asc";
  },
): Promise<SceneListResponse> {
  const params = new URLSearchParams();
  if (options?.tag) params.set("tag", options.tag);
  if (options?.min_score != null) params.set("min_score", String(options.min_score));
  if (options?.search) params.set("search", options.search);
  if (options?.sort) params.set("sort", options.sort);
  if (options?.order) params.set("order", options.order);

  const res = await fetch(`/api/tasks/${taskId}/scenes?${params}`);
  if (!res.ok) throw new Error(`Failed to list scenes: ${res.statusText}`);
  return res.json();
}

export async function getScene(taskId: string, sceneId: number): Promise<Scene> {
  const res = await fetch(`/api/tasks/${taskId}/scenes/${sceneId}`);
  if (!res.ok) throw new Error(`Scene not found: ${res.statusText}`);
  return res.json();
}

export async function updateScene(
  taskId: string,
  sceneId: number,
  data: SceneUpdateRequest,
): Promise<Scene> {
  const res = await fetch(`/api/tasks/${taskId}/scenes/${sceneId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to update scene: ${res.statusText}`);
  return res.json();
}

// =====================================================================
// ClipCandidate Data
// =====================================================================

export async function listCandidates(
  taskId: string,
  sort: "score" | "start" = "score",
  order: "desc" | "asc" = "desc",
): Promise<CandidateListResponse> {
  const params = new URLSearchParams({ sort, order });
  const res = await fetch(`/api/tasks/${taskId}/candidates?${params}`);
  if (!res.ok) throw new Error(`Failed to list candidates: ${res.statusText}`);
  return res.json();
}

export async function bulkSelectCandidates(
  taskId: string,
  data: BulkSelectRequest,
): Promise<{ updated: number; selected: boolean }> {
  const res = await fetch(`/api/tasks/${taskId}/candidates/bulk-select`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to bulk select: ${res.statusText}`);
  return res.json();
}

// =====================================================================
// Transcript
// =====================================================================

export async function getTranscript(taskId: string): Promise<TranscriptResponse> {
  const res = await fetch(`/api/tasks/${taskId}/transcript`);
  if (!res.ok) throw new Error(`Transcript not found: ${res.statusText}`);
  return res.json();
}

export async function updateTranscript(
  taskId: string,
  data: TranscriptUpdateRequest,
): Promise<{ status: string; segment_count: number }> {
  const res = await fetch(`/api/tasks/${taskId}/transcript`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to update transcript: ${res.statusText}`);
  return res.json();
}

export async function updateSegment(
  taskId: string,
  segIndex: number,
  data: SegmentUpdateRequest,
): Promise<{ status: string; text: string }> {
  const res = await fetch(`/api/tasks/${taskId}/transcript/segments/${segIndex}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to update segment: ${res.statusText}`);
  return res.json();
}

// =====================================================================
// Config Reference Data
// =====================================================================

export async function getPresets(): Promise<ConfigResponse<PresetInfo>> {
  const res = await fetch("/api/config/presets");
  if (!res.ok) throw new Error(`Failed to get presets: ${res.statusText}`);
  return res.json();
}

export async function getClipModes(): Promise<ConfigResponse<ClipModeInfo>> {
  const res = await fetch("/api/config/clip-modes");
  if (!res.ok) throw new Error(`Failed to get clip modes: ${res.statusText}`);
  return res.json();
}

export async function getSceneTypes(): Promise<ConfigResponse<string>> {
  const res = await fetch("/api/config/scene-types");
  if (!res.ok) throw new Error(`Failed to get scene types: ${res.statusText}`);
  return res.json();
}

export async function getScoreDimensions(): Promise<ConfigResponse<ScoreDimensionInfo>> {
  const res = await fetch("/api/config/score-dimensions");
  if (!res.ok) throw new Error(`Failed to get score dimensions: ${res.statusText}`);
  return res.json();
}

export async function getPipelineStages(): Promise<ConfigResponse<PipelineStageInfo>> {
  const res = await fetch("/api/config/pipeline-stages");
  if (!res.ok) throw new Error(`Failed to get pipeline stages: ${res.statusText}`);
  return res.json();
}

export async function getWeights(): Promise<Record<string, unknown>> {
  const res = await fetch("/api/config/weights");
  if (!res.ok) throw new Error(`Failed to get weights: ${res.statusText}`);
  return res.json();
}

export async function getDurationTemplates(): Promise<ConfigResponse<DurationTemplate>> {
  const res = await fetch("/api/config/duration-templates");
  if (!res.ok) throw new Error(`Failed to get duration templates: ${res.statusText}`);
  return res.json();
}

// =====================================================================
// Preset Management (CRUD)
// =====================================================================

export async function listPresets(): Promise<PresetData[]> {
  const res = await fetch("/api/presets");
  if (!res.ok) throw new Error(`Failed to list presets: ${res.statusText}`);
  const data = await res.json();
  return data.items;
}

export async function getPreset(name: string): Promise<PresetData> {
  const res = await fetch(`/api/presets/${name}`);
  if (!res.ok) throw new Error(`Preset not found: ${res.statusText}`);
  return res.json();
}

export async function savePreset(preset: PresetData): Promise<PresetData> {
  const res = await fetch(`/api/presets/${preset.name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(preset),
  });
  if (!res.ok) throw new Error(`Failed to save preset: ${res.statusText}`);
  return res.json();
}

export async function deletePreset(name: string): Promise<{ status: string }> {
  const res = await fetch(`/api/presets/${name}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete preset: ${res.statusText}`);
  return res.json();
}

export async function duplicatePreset(
  name: string,
  newName: string,
): Promise<PresetData> {
  const params = new URLSearchParams({ new_name: newName });
  const res = await fetch(`/api/presets/${name}/duplicate?${params}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to duplicate preset: ${res.statusText}`);
  return res.json();
}

// =====================================================================
// Prompt Management
// =====================================================================

export async function listPrompts(): Promise<PromptInfo[]> {
  const res = await fetch("/api/prompts");
  if (!res.ok) throw new Error(`Failed to list prompts: ${res.statusText}`);
  const data = await res.json();
  return data.items;
}

export async function getPrompt(name: string): Promise<string> {
  const res = await fetch(`/api/prompts/${name}`);
  if (!res.ok) throw new Error(`Prompt not found: ${res.statusText}`);
  const data = await res.json();
  return data.content;
}

export async function savePrompt(
  name: string,
  content: string,
): Promise<{ status: string; name: string }> {
  const res = await fetch(`/api/prompts/${name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(`Failed to save prompt: ${res.statusText}`);
  return res.json();
}

// =====================================================================
// SSE Connection
// =====================================================================

export function connectSSE(
  taskId?: string,
  onMessage?: (event: SSEEvent) => void,
): EventSource {
  const url = taskId
    ? `/api/tasks/${taskId}/events`
    : "/api/events";
  const es = new EventSource(url);

  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      const sseEvent: SSEEvent = {
        event_type: (event.type || "log") as SSEEvent["event_type"],
        data: data.data || data,
      };
      onMessage?.(sseEvent);
    } catch {
      // Skip malformed events
    }
  };

  // Handle different event types via named handlers
  const eventTypes: SSEEvent["event_type"][] = [
    "task_status",
    "stage_start",
    "stage_complete",
    "log",
    "progress",
    "error",
    "pause",
    "complete",
  ];
  for (const type of eventTypes) {
    es.addEventListener(type, (evt: MessageEvent) => {
      try {
        const data = JSON.parse(evt.data);
        onMessage?.({ event_type: type, data });
      } catch {
        // Skip
      }
    });
  }

  return es;
}

// =====================================================================
// File Operations
// =====================================================================

export function getThumbnailUrl(
  filePath: string,
  timestamp = 0,
  width = 320,
): string {
  return `/api/files/${encodeURIComponent(filePath)}/thumbnail?timestamp=${timestamp}&width=${width}`;
}

export function getFileDownloadUrl(filePath: string): string {
  return `/api/files/${encodeURIComponent(filePath)}`;
}

const SETTINGS_STORAGE_KEY = "videoagent_settings";

// --------------------------------------------------------------------- #
// User Settings — with localStorage fallback
// --------------------------------------------------------------------- #

export interface UserSettings {
  modelType: "local" | "online";
  localLlm: {
    url: string;
    model: string;
    temperature: number;
    maxTokens: number;
  };
  onlineLlm: {
    provider: string;
    apiKey: string;
    baseUrl: string;
    model: string;
    temperature: number;
    maxTokens: number;
  };
  theme?: "dark" | "light";
  accentColor?: string;
}

function getDefaultSettings(): UserSettings {
  return {
    modelType: "online",
    localLlm: { url: "http://localhost:11434", model: "", temperature: 0.7, maxTokens: 8192 },
    onlineLlm: {
      provider: "openai",
      apiKey: "",
      baseUrl: "https://api.openai.com/v1",
      model: "claude-sonnet-4-6",
      temperature: 0.7,
      maxTokens: 8192,
    },
    theme: "dark",
    accentColor: "#6366f1",
  };
}

function readLocalSettings(): UserSettings | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function writeLocalSettings(settings: UserSettings) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings));
  } catch {
    /* quota exceeded */
  }
}

/** Deep-merge local into remote (local overrides remote) */
function mergeSettings(base: UserSettings, override: Partial<UserSettings>): UserSettings {
  return {
    ...base,
    ...override,
    localLlm: { ...base.localLlm, ...(override.localLlm || {}) },
    onlineLlm: { ...base.onlineLlm, ...(override.onlineLlm || {}) },
  };
}

export async function getUserSettings(): Promise<UserSettings> {
  const res = await fetch("/api/settings");
  if (!res.ok) throw new Error(`Failed to get settings: ${res.status}`);
  const api: UserSettings = await res.json();
  // Cache to localStorage
  writeLocalSettings(api);
  return api;
}

export async function saveUserSettings(
  settings: Partial<UserSettings> & {
    localLlm?: Partial<UserSettings["localLlm"]>;
    onlineLlm?: Partial<UserSettings["onlineLlm"]>;
  },
): Promise<UserSettings> {
  const res = await fetch("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error(`Failed to save settings: ${res.status}`);
  const data = await res.json();
  const merged: UserSettings = data.settings;
  // Sync to localStorage
  writeLocalSettings(merged);
  return merged;
}

/** Get settings — try API first, fall back to localStorage, then defaults */
export async function getUserSettingsWithFallback(): Promise<UserSettings> {
  try {
    return await getUserSettings();
  } catch {
    return readLocalSettings() || getDefaultSettings();
  }
}

/** Save settings — write to API, but also persist locally if API fails */
export async function saveUserSettingsWithFallback(
  settings: Partial<UserSettings> & {
    localLlm?: Partial<UserSettings["localLlm"]>;
    onlineLlm?: Partial<UserSettings["onlineLlm"]>;
  },
): Promise<boolean> {
  try {
    await saveUserSettings(settings);
    return true;
  } catch {
    // API failed — persist to localStorage as fallback
    const local = readLocalSettings() || getDefaultSettings();
    const merged = mergeSettings(local, settings as Partial<UserSettings>);
    writeLocalSettings(merged);
    return false;
  }
}
