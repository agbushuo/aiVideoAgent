import { create } from "zustand";
import {
  TaskListItem,
  TaskDetailResponse,
  TaskStatus,
  TaskCreateRequest,
  LogEntry,
} from "@/types/api";
import { SSEEvent } from "@/types/sse";
import { useWorkflowStore } from "@/stores/workflowStore";
import { StageId } from "@/types/stage";
import * as api from "@/lib/api";

interface TaskState {
  tasks: TaskListItem[];
  currentTask: TaskDetailResponse | null;
  isLoading: boolean;
  sseConnected: boolean;

  // Selected tasks for bulk operations
  selectedTaskIds: string[];

  // Run Console log entries (in-memory, keyed by taskId)
  consoleLogs: Record<string, LogEntry[]>;

  // Actions
  fetchTasks: () => Promise<void>;
  createTask: (request: TaskCreateRequest) => Promise<string>;
  fetchTask: (taskId: string) => Promise<void>;
  deleteTask: (taskId: string) => Promise<void>;
  bulkDeleteTasks: (taskIds: string[], deleteOutputs: boolean) => Promise<void>;
  cancelTask: (taskId: string) => Promise<void>;
  resumeTask: (taskId: string) => Promise<void>;
  runStage: (taskId: string, stageId: string) => Promise<void>;
  rerunStage: (taskId: string, stageId: string) => Promise<void>;

  // Selection
  toggleSelectTask: (taskId: string) => void;
  selectAllTasks: () => void;
  clearSelection: () => void;

  // Run Console
  getLogs: (taskId: string) => LogEntry[];
  appendLog: (taskId: string, entry: LogEntry) => void;
  loadConsoleLogs: (taskId: string) => Promise<void>;
  clearConsoleLogs: (taskId: string) => void;

  handleSSEEvent: (event: SSEEvent) => void;
  connectSSE: (taskId?: string) => EventSource | null;
  disconnectSSE: () => void;
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  currentTask: null,
  isLoading: false,
  sseConnected: false,
  selectedTaskIds: [],
  consoleLogs: {},

  fetchTasks: async () => {
    set({ isLoading: true });
    try {
      const tasks = await api.listTasks();
      set({ tasks });
    } catch {
      // Silently fail — backend may not be running
    } finally {
      set({ isLoading: false });
    }
  },

  createTask: async (request) => {
    const result = await api.createTask(request);
    await get().fetchTasks();
    return result.task_id;
  },

  fetchTask: async (taskId) => {
    try {
      const task = await api.getTask(taskId);
      set({ currentTask: task });
    } catch {
      // Task not found
    }
  },

  deleteTask: async (taskId) => {
    await api.deleteTask(taskId);
    set({ tasks: get().tasks.filter((t) => t.task_id !== taskId) });
    if (get().currentTask?.task_id === taskId) {
      set({ currentTask: null });
    }
  },

  bulkDeleteTasks: async (taskIds, deleteOutputs) => {
    await api.bulkDeleteTasks(taskIds, deleteOutputs);
    const current = get().tasks;
    set({
      tasks: current.filter((t) => !taskIds.includes(t.task_id)),
      selectedTaskIds: [],
    });
    // Clear current task if it was deleted
    if (get().currentTask && taskIds.includes(get().currentTask.task_id)) {
      set({ currentTask: null });
    }
  },

  toggleSelectTask: (taskId) => {
    const selected = [...get().selectedTaskIds];
    const idx = selected.indexOf(taskId);
    if (idx >= 0) {
      selected.splice(idx, 1);
    } else {
      selected.push(taskId);
    }
    set({ selectedTaskIds: selected });
  },

  selectAllTasks: () => {
    set({ selectedTaskIds: get().tasks.map((t) => t.task_id) });
  },

  clearSelection: () => {
    set({ selectedTaskIds: [] });
  },

  cancelTask: async (taskId) => {
    await api.cancelTask(taskId);
    await get().fetchTasks();
  },

  resumeTask: async (taskId) => {
    await api.resumeTask(taskId);
    await get().fetchTasks();
  },

  runStage: async (taskId, stageId) => {
    await api.runStage(taskId, stageId);
    await get().fetchTask(taskId);
  },

  rerunStage: async (taskId, stageId) => {
    await api.rerunStage(taskId, stageId);
    await get().fetchTask(taskId);
  },

  // ── Run Console ──

  getLogs: (taskId) => get().consoleLogs[taskId] || [],

  appendLog: (taskId, entry) => {
    set({
      consoleLogs: {
        ...get().consoleLogs,
        [taskId]: [...(get().consoleLogs[taskId] || []), entry],
      },
    });
  },

  loadConsoleLogs: async (taskId) => {
    try {
      const task = await api.getTask(taskId);
      const logs = task.logs || [];
      set({
        consoleLogs: { ...get().consoleLogs, [taskId]: logs },
      });
    } catch {
      // Task may not exist yet
    }
  },

  clearConsoleLogs: (taskId) => {
    set({
      consoleLogs: { ...get().consoleLogs, [taskId]: [] },
    });
  },

  handleSSEEvent: (event) => {
    const { currentTask, tasks } = get();
    const taskId = event.data.task_id as string;

    if (event.event_type === "progress") {
      // Update current task progress
      if (currentTask && currentTask.task_id === taskId) {
        set({
          currentTask: {
            ...currentTask,
            progress: {
              ...currentTask.progress,
              step: (event.data.step as string) || currentTask.progress.step,
              percent: (event.data.percent as number) ?? currentTask.progress.percent,
              step_detail: (event.data.step_detail as string) || currentTask.progress.step_detail,
            },
          },
        });
      }
      // Update task list item
      set({
        tasks: tasks.map((t) =>
          t.task_id === taskId
            ? {
                ...t,
                progress: {
                  ...t.progress,
                  step: (event.data.step as string) || t.progress.step,
                  percent: (event.data.percent as number) ?? t.progress.percent,
                },
              }
            : t,
        ),
      });
    }

    if (event.event_type === "task_status") {
      const status = event.data.status as TaskStatus;
      if (currentTask && currentTask.task_id === taskId) {
        set({ currentTask: { ...currentTask, status } });
      }
      set({
        tasks: tasks.map((t) =>
          t.task_id === taskId ? { ...t, status } : t,
        ),
      });
    }

    if (event.event_type === "log") {
      // Append log entry to console
      const level = (event.data.level as LogEntry["level"]) || "info";
      const message = (event.data.message as string) || "";
      const step = (event.data.stage as string) || "";
      const timestamp = (event.data.timestamp as number) || Date.now() / 1000;
      get().appendLog(taskId, { timestamp, level, message, step });
    }

    if (event.event_type === "stage_start") {
      // Update workflow node status
      const stageId = event.data.stage_id as StageId;
      const workflow = useWorkflowStore.getState();
      workflow.updateStageStatus(stageId, "running");

      // Append a system log entry
      const stageName = (event.data.stage_name as string) || stageId;
      get().appendLog(taskId, {
        timestamp: Date.now() / 1000,
        level: "info",
        message: `Stage started: ${stageName}`,
        step: stageId,
      });
    }

    if (event.event_type === "stage_complete") {
      const stageId = event.data.stage_id as StageId;
      const duration = (event.data.duration as number) || undefined;
      const workflow = useWorkflowStore.getState();
      workflow.updateStageStatus(stageId, "completed", duration);

      const stageName = (event.data.stage_name as string) || stageId;
      get().appendLog(taskId, {
        timestamp: Date.now() / 1000,
        level: "success",
        message: `Stage completed: ${stageName}${duration ? ` (${duration.toFixed(1)}s)` : ""}`,
        step: stageId,
      });
    }

    if (event.event_type === "complete" || event.event_type === "error") {
      if (event.event_type === "error") {
        const stageId = (event.data.stage_id as StageId) || "";
        const errorMsg = (event.data.error as string) || "Unknown error";
        const workflow = useWorkflowStore.getState();
        if (stageId) {
          workflow.updateStageStatus(stageId, "failed");
        }
        get().appendLog(taskId, {
          timestamp: Date.now() / 1000,
          level: "error",
          message: `Error${stageId ? ` in ${stageId}` : ""}: ${errorMsg}`,
          step: stageId,
        });
      }
      get().fetchTask(taskId);
      get().fetchTasks();
    }
  },

  connectSSE: (taskId) => {
    try {
      const es = api.connectSSE(taskId, get().handleSSEEvent);
      set({ sseConnected: true });
      return es;
    } catch {
      set({ sseConnected: false });
      return null;
    }
  },

  disconnectSSE: () => {
    set({ sseConnected: false });
  },
}));
