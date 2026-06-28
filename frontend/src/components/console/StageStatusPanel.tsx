"use client";

import { useTranslations } from "next-intl";
import { useTaskStore } from "@/stores/taskStore";
import { useWorkflowStore } from "@/stores/workflowStore";
import { STAGE_IDS } from "@/types/stage";
import { STAGE_DESCRIPTIONS } from "@/types/workflow";
import {
  CheckCircle,
  XCircle,
  SkipForward,
  Loader2,
  Clock,
  RotateCw,
  AlertCircle,
} from "lucide-react";

const statusConfig = {
  pending: { color: "text-zinc-500", bg: "bg-zinc-800", icon: Clock },
  running: { color: "text-blue-400", bg: "bg-blue-900/40", icon: Loader2 },
  completed: { color: "text-green-400", bg: "bg-green-900/40", icon: CheckCircle },
  failed: { color: "text-red-400", bg: "bg-red-900/40", icon: XCircle },
  skipped: { color: "text-zinc-500", bg: "bg-zinc-800/50", icon: SkipForward },
};

export default function StageStatusPanel({ taskId }: { taskId: string }) {
  const t = useTranslations("console");
  const st = useTranslations("stageDefs");
  const s = useTranslations("status");

  const currentTask = useTaskStore((s) => s.currentTask);
  const rerunStage = useTaskStore((s) => s.rerunStage);

  const stages = Object.entries(currentTask?.stage_results || {});

  if (stages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
        {t("noResults")}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-surface">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <span className="text-sm font-semibold text-zinc-200">{t("title")}</span>
        <span className="text-xs text-zinc-500">
          {stages.filter(([, s]) => s.status === "completed").length}/{stages.length} {t("completed")}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {STAGE_IDS.map((id) => {
          const stage = currentTask?.stage_results[id];
          if (!stage) return null;

          const status = stage.status;
          const cfg = statusConfig[status] || statusConfig.pending;
          const StatusIcon = cfg.icon;

          const duration = stage.duration_seconds
            ? `${stage.duration_seconds.toFixed(1)}s`
            : null;
          const error = stage.error || null;

          // Build stage label from stageDefs: st("transcribe.label") etc.
          const stageLabel = st(`${id}.label`);

          return (
            <div
              key={id}
              className={`flex items-start gap-3 p-3 rounded-lg border transition-colors ${
                status === "failed"
                  ? "border-red-900/50 bg-red-950/20"
                  : status === "running"
                    ? "border-blue-900/50 bg-blue-950/20"
                    : status === "completed"
                      ? "border-green-900/30 bg-green-950/10"
                      : "border-border bg-surface-elevated"
              }`}
            >
              {/* Status indicator */}
              <div className={`mt-0.5 ${cfg.color}`}>
                <StatusIcon className={`w-4 h-4 ${status === "running" ? "animate-spin" : ""}`} />
              </div>

              {/* Stage info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-zinc-200">
                    {stageLabel || id}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${cfg.bg} ${cfg.color}`}>
                    {s(status)}
                  </span>
                </div>

                <p className="text-xs text-zinc-500 mt-0.5">
                  {st(`${id}.description`) || STAGE_DESCRIPTIONS[id] || ""}
                </p>

                {duration && (
                  <span className="text-xs text-zinc-600 mt-1 inline-block">{duration}</span>
                )}

                {error && (
                  <p className="text-xs text-red-400 mt-1 truncate">{error}</p>
                )}
              </div>

              {/* Retry button */}
              {status === "failed" && (
                <button
                  onClick={() => rerunStage(taskId, id)}
                  className="shrink-0 flex items-center gap-1 text-xs px-2 py-1 rounded bg-red-900/40 text-red-400 hover:bg-red-900/60 transition-colors"
                  title={`${t("rerun")} ${stageLabel || id}`}
                >
                  <RotateCw className="w-3 h-3" />
                  {t("retry")}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
