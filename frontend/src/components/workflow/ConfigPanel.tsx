"use client";

import { useWorkflowStore } from "@/stores/workflowStore";
import { useConfigStore } from "@/stores/configStore";
import {
  BASE_STAGE_SCHEMAS,
  LANGUAGE_OPTIONS,
  DEVICE_OPTIONS,
  STAGE_DESCRIPTIONS,
} from "@/types/workflow";
import type { StageFieldConfig } from "@/types/workflow";
import type { StageId } from "@/types/stage";
import StageFormField from "./StageFormField";
import { Mic, Scissors, Brain, Star, Filter, Clock, Check, Film } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";

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

export default function ConfigPanel() {
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId);
  const selectedNode = useWorkflowStore((s) =>
    s.nodes.find((n) => n.id === s.selectedNodeId),
  );
  const updateStageParams = useWorkflowStore((s) => s.updateStageParams);
  const toggleStage = useWorkflowStore((s) => s.toggleStage);
  const selectNode = useWorkflowStore((s) => s.selectNode);
  const presets = useConfigStore((s) => s.presets);
  const clipModes = useConfigStore((s) => s.clipModes);
  const t = useTranslations("workflow");

  if (!selectedNodeId || !selectedNode) {
    return (
      <div className="shrink-0 border-t border-border bg-surface flex items-center justify-center">
        <p className="text-xs text-zinc-600 py-2">点击画布中的节点以编辑参数</p>
      </div>
    );
  }

  const stageId = selectedNodeId as StageId;
  const IconComponent = ICON_MAP[selectedNode.data.icon] || Film;
  const baseSchema = BASE_STAGE_SCHEMAS[stageId] || [];

  // Merge dynamic options from configStore
  const schema: StageFieldConfig[] = baseSchema.map((field) => {
    if (field.key === "language" && field.type === "select") {
      return { ...field, options: LANGUAGE_OPTIONS };
    }
    if (field.key === "device" && field.type === "select") {
      return { ...field, options: DEVICE_OPTIONS };
    }
    if (field.key === "preset" && field.type === "select") {
      return {
        ...field,
        options: presets.map((p) => ({ label: t(`presetLabels.${p.name}`, { defaultValue: p.name }), value: p.name })),
      };
    }
    if (field.key === "clip_mode" && field.type === "select") {
      return {
        ...field,
        options: clipModes.map((m) => ({ label: t(`clipModes.${m.name}`, { defaultValue: m.name }), value: m.name })),
      };
    }
    return field as StageFieldConfig;
  });

  const description = STAGE_DESCRIPTIONS[stageId] || "";

  return (
    <div className="shrink-0 border-t border-border bg-surface-elevated flex flex-col">
      {/* Header: icon, label, toggle, close */}
      <div className="flex items-center gap-3 px-5 py-2.5 border-b border-border">
        <IconComponent className="w-5 h-5 text-zinc-400" />
        <h3 className="text-sm font-semibold text-zinc-200">
          {selectedNode.data.label}
        </h3>
        {description && (
          <span className="text-xs text-zinc-500">{description}</span>
        )}

        <div className="flex items-center gap-3 ml-auto">
          {selectedNode.data.duration !== null && (
            <span className="text-xs text-zinc-500">
              上次执行: {selectedNode.data.duration.toFixed(1)}s
            </span>
          )}
          <button
            onClick={() => toggleStage(selectedNodeId)}
            className={`relative w-10 h-6 rounded-full transition-colors ${
              selectedNode.data.enabled ? "bg-brand-600" : "bg-zinc-700"
            }`}
          >
            <div
              className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                selectedNode.data.enabled ? "translate-x-4" : "translate-x-0.5"
              }`}
            />
          </button>
          <button
            onClick={() => selectNode(null)}
            className="text-zinc-400 hover:text-zinc-200 transition-colors"
            title="关闭面板"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Form fields laid out horizontally */}
      {schema.length > 0 ? (
        <div className="flex items-start gap-8 px-5 py-3 overflow-x-auto">
          {schema.map((field) => (
            <div key={field.key} className="shrink-0 pt-1">
              <StageFormField
                config={field}
                value={selectedNode.data.params[field.key]}
                onChange={(value) =>
                  updateStageParams(selectedNodeId, { [field.key]: value })
                }
              />
            </div>
          ))}
        </div>
      ) : (
        <div className="px-5 py-3">
          <p className="text-xs text-zinc-500">此阶段没有可配置参数</p>
        </div>
      )}
    </div>
  );
}
