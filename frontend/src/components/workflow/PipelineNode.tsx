"use client";

import { Handle, Position } from "@xyflow/react";
import { Mic, Scissors, Brain, Star, Filter, Clock, Check, Film } from "lucide-react";
import { useTranslations } from "next-intl";
import { useWorkflowStore } from "@/stores/workflowStore";
import type { PipelineNode } from "@/stores/workflowStore";
import type { StageId } from "@/types/stage";
import type { LucideIcon } from "lucide-react";

const ICON_MAP: Record<string, LucideIcon> = {
  mic: Mic,
  scissors: Scissors,
  brain: Brain,
  star: Star,
  filter: Filter,
  clock: Clock,
  check: Check,
  film: Film,
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-zinc-600",
  running: "bg-blue-500 animate-pulse",
  completed: "bg-green-500",
  failed: "bg-red-500",
  skipped: "bg-zinc-700",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "等待",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  skipped: "已跳过",
};

interface PipelineNodeProps {
  data: PipelineNode["data"] & { id: string };
}

export default function PipelineNode({ data }: PipelineNodeProps) {
  const t = useTranslations("workflow");
  const toggleStage = useWorkflowStore((s) => s.toggleStage);

  const IconComponent = ICON_MAP[data.icon] || Film;
  const statusColor = STATUS_COLORS[data.status] || STATUS_COLORS.pending;

  const statusLabel = STATUS_LABELS[data.status] || data.status;
  const enableLabel = t("enable", { label: data.label });
  const disableLabel = t("disable", { label: data.label });
  const isDisabled = !data.enabled;

  return (
    <div
      className={`relative px-6 py-4 rounded-lg border transition-all ${
        isDisabled
          ? "opacity-40 border-dashed border-zinc-600 bg-zinc-900/50"
          : "border-border bg-surface-elevated"
      }`}
      style={{ minWidth: 220, maxWidth: 280 }}
    >
      {/* Connection handles */}
      <Handle type="target" position={Position.Top} />
      <Handle type="source" position={Position.Bottom} />

      {/* Header: icon + label */}
      <div className="flex items-center gap-2.5 mb-3">
        <IconComponent className="w-5 h-5 text-zinc-400 shrink-0" />
        <span className="text-base font-medium text-zinc-200">{data.label}</span>
      </div>

      {/* Toggle + status */}
      <div className="flex items-center justify-between">
        <button
          onClick={(e) => {
            e.stopPropagation();
            toggleStage(data.id as StageId);
          }}
          className={`relative w-10 h-6 rounded-full transition-colors ${
            data.enabled ? "bg-brand-600" : "bg-zinc-700"
          }`}
          title={data.enabled ? disableLabel : enableLabel}
        >
          <div
            className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
              data.enabled ? "translate-x-4" : "translate-x-0.5"
            }`}
          />
        </button>

        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${statusColor}`} />
          <span className="text-xs text-zinc-500">{statusLabel}</span>
        </div>
      </div>

      {/* Duration */}
      {data.duration !== null && (
        <div className="mt-2 text-xs text-zinc-500">
          {data.duration.toFixed(1)}s
        </div>
      )}
    </div>
  );
}
