"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { useTaskStore } from "@/stores/taskStore";
import StageStatusPanel from "./StageStatusPanel";
import LogPanel from "./LogPanel";
import { Loader2 } from "lucide-react";

export default function RunConsole({ taskId }: { taskId: string }) {
  const t = useTranslations("console");
  const currentTask = useTaskStore((s) => s.currentTask);
  const sseConnected = useTaskStore((s) => s.sseConnected);
  const loadConsoleLogs = useTaskStore((s) => s.loadConsoleLogs);

  const isRunning = currentTask && !["completed", "cancelled", "error"].includes(currentTask.status);
  const isTerminal = currentTask && ["completed", "cancelled", "error"].includes(currentTask.status);

  // Load historical logs on mount
  // SSE is handled globally by Layout — no need to connect here
  useEffect(() => {
    loadConsoleLogs(taskId);
  }, [taskId]);

  return (
    <div className="flex h-full min-w-0">
      {/* Left: Stage Status Panel — fixed width */}
      <div className="w-80 border-r border-border flex flex-col shrink-0">
        <StageStatusPanel taskId={taskId} />
      </div>

      {/* Right: Log Panel — fills remaining space */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Status bar */}
        <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-surface-elevated shrink-0">
          {isRunning && (
            <span className="flex items-center gap-1.5 text-xs text-blue-400">
              <Loader2 className="w-3 h-3 animate-spin" />
              {t("running")}
            </span>
          )}
          {isTerminal && (
            <span
              className={`text-xs ${
                currentTask?.status === "completed"
                  ? "text-green-400"
                  : currentTask?.status === "error"
                    ? "text-red-400"
                    : "text-zinc-500"
              }`}
            >
              {currentTask?.status === "completed"
                ? t("completed")
                : currentTask?.status === "error"
                  ? t("failed")
                  : t("cancelled")}
            </span>
          )}

          <span className="text-xs text-zinc-600">
            {t("sse")}: {sseConnected ? t("connected") : t("disconnected")}
          </span>

          {currentTask?.progress && (
            <span className="text-xs text-zinc-500 ml-auto">
              {Math.round(currentTask.progress.percent)}%
              {currentTask.progress.step ? ` — ${currentTask.progress.step}` : ""}
            </span>
          )}
        </div>

        {/* Log panel fills remaining height */}
        <div className="flex-1 min-h-0">
          <LogPanel taskId={taskId} />
        </div>
      </div>
    </div>
  );
}
