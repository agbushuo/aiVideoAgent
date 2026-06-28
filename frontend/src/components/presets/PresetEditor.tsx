"use client";

import { useState, useEffect } from "react";
import type { PresetData } from "@/types/config";
import { useTranslations } from "next-intl";
import {
  getStageSchemas,
  LANGUAGE_OPTIONS,
  DEVICE_OPTIONS,
} from "@/types/workflow";
import type { StageFieldConfig, StageId } from "@/types/workflow";
import StageFormField from "@/components/workflow/StageFormField";
import PromptEditor from "./PromptEditor";
import { Save, Trash2, Copy, Loader2, AlertTriangle } from "lucide-react";

const SCORE_DIMS = [
  "hook",
  "emotion",
  "comedy",
  "action",
  "information",
  "suspense",
  "climax",
  "viral",
];

const STAGE_ORDER: Array<{ key: string; stageId: StageId; labelKey: string }> = [
  { key: "transcribe", stageId: "transcribe", labelKey: "stageTranscribe" },
  { key: "scene_detection", stageId: "scene_detection", labelKey: "stageSceneDetection" },
  { key: "scoring", stageId: "scoring", labelKey: "stageScoring" },
  { key: "filtering", stageId: "filtering", labelKey: "stageFiltering" },
  { key: "duration_planning", stageId: "duration_planning", labelKey: "stageDurationPlanning" },
  { key: "final_review", stageId: "final_review", labelKey: "stageFinalReview" },
  { key: "clipping", stageId: "clipping", labelKey: "stageClipping" },
];

const PROMPT_TEMPLATES = ["scene_analysis", "final_review"];

type Tab = "params" | "weights" | "prompts";

interface PresetEditorProps {
  preset: PresetData;
  onSave: (preset: PresetData) => void;
  onDelete: () => void;
  onDuplicate: () => void;
  configPresets?: { name: string }[];
  configClipModes?: { name: string }[];
}

export default function PresetEditor({
  preset,
  onSave,
  onDelete,
  onDuplicate,
  configPresets = [],
  configClipModes = [],
}: PresetEditorProps) {
  const t = useTranslations("presets");
  const tW = useTranslations("workflow");
  const tCommon = useTranslations("common");
  const [activeTab, setActiveTab] = useState<Tab>("params");
  const [editing, setEditing] = useState<PresetData>({ ...preset });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [activePrompt, setActivePrompt] = useState(PROMPT_TEMPLATES[0]);

  // Sync when preset changes
  useEffect(() => {
    setEditing({ ...preset });
    setSaved(false);
  }, [preset]);

  // Build stage schemas with dynamic options
  const schemas = getStageSchemas("zh");

  const getFieldsForStage = (stageId: StageId): StageFieldConfig[] => {
    const base = schemas[stageId] || [];
    return base.map((field) => {
      if (field.key === "language" && field.type === "select") {
        return { ...field, options: LANGUAGE_OPTIONS };
      }
      if (field.key === "device" && field.type === "select") {
        return { ...field, options: DEVICE_OPTIONS };
      }
      if (field.key === "preset" && field.type === "select") {
        return {
          ...field,
          options: configPresets.map((p) => ({ label: tW(`presetLabels.${p.name}`, { defaultValue: p.name }), value: p.name })),
        };
      }
      if (field.key === "clip_mode" && field.type === "select") {
        return {
          ...field,
          options: configClipModes.map((m) => ({ label: tW(`clipModes.${m.name}`, { defaultValue: m.name }), value: m.name })),
        };
      }
      return field as StageFieldConfig;
    });
  };

  const updateStageParam = (stageId: string, key: string, value: unknown) => {
    setEditing((prev) => {
      const stageParams = { ...(prev.stageParams || {}) };
      const stage = { ...(stageParams[stageId] || {}) };
      stage[key] = value;
      stageParams[stageId] = stage;
      return { ...prev, stageParams };
    });
    setSaved(false);
  };

  const updateWeight = (dim: string, value: number) => {
    setEditing((prev) => {
      const weights = { ...(prev.weights || {}) };
      weights[dim] = value;
      return { ...prev, weights };
    });
    setSaved(false);
  };

  const updatePromptOverride = (promptName: string, content: string) => {
    setEditing((prev) => {
      const prompts = { ...(prev.prompts || {}) };
      prompts[promptName] = content;
      return { ...prev, prompts };
    });
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(editing);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error("Failed to save preset:", e);
    } finally {
      setSaving(false);
    }
  };

  const tabs: Array<{ key: Tab; label: string }> = [
    { key: "params", label: t("tabParams") },
    { key: "weights", label: t("tabWeights") },
    { key: "prompts", label: t("tabPrompts") },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border">
        <div className="flex items-center gap-3">
          <input
            type="text"
            value={editing.displayName || editing.name}
            onChange={(e) =>
              setEditing((prev) => ({ ...prev, displayName: e.target.value }))
            }
            className="text-lg font-semibold bg-transparent border-0 border-b border-transparent hover:border-border focus:border-brand-500 text-zinc-100 px-0 py-1 transition-colors focus:outline-none"
          />
          <span className="text-xs text-zinc-500 px-2 py-0.5 bg-zinc-800 rounded">
            {editing.name}
          </span>
        </div>
        <input
          type="text"
          value={editing.description || ""}
          onChange={(e) =>
            setEditing((prev) => ({ ...prev, description: e.target.value }))
          }
          placeholder={t("presetDescriptionPlaceholder")}
          className="mt-2 w-full text-xs text-zinc-400 bg-transparent border-0 border-b border-transparent hover:border-border focus:border-brand-500 px-0 py-1 transition-colors focus:outline-none"
        />
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm border-b-2 transition-colors ${
              activeTab === tab.key
                ? "border-brand-500 text-brand-400"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {tab.label}
          </button>
        ))}

        {/* Action buttons */}
        <div className="flex items-center gap-2 ml-auto mr-3">
          <button
            onClick={onDuplicate}
            className="p-1.5 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded transition-colors"
            title={t("duplicate")}
          >
            <Copy className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="p-1.5 text-zinc-400 hover:text-red-400 hover:bg-zinc-800 rounded transition-colors"
            title={t("delete")}
          >
            <Trash2 className="w-4 h-4" />
          </button>
          <button
            onClick={handleSave}
            disabled={saving || saved}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors ${
              saved
                ? "bg-green-600/20 text-green-400"
                : "bg-brand-600 hover:bg-brand-500 text-white"
            }`}
          >
            {saving ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Save className="w-3.5 h-3.5" />
            )}
            {saving ? t("saving") : saved ? t("saved") : t("save")}
          </button>
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {/* ── Pipeline Params ── */}
        {activeTab === "params" && (
          <div className="p-4 space-y-5">
            {STAGE_ORDER.map(({ key, stageId, labelKey }) => {
              const fields = getFieldsForStage(stageId);
              const stageParams = editing.stageParams?.[key] || {};
              return (
                <div key={key}>
                  <h4 className="text-sm font-medium text-zinc-300 mb-2">
                    {t(labelKey)}
                  </h4>
                  <div className="flex items-start gap-6 pl-3 border-l border-zinc-700">
                    {fields.map((field) => (
                      <div key={field.key} className="shrink-0">
                        <StageFormField
                          config={field}
                          value={stageParams[field.key] ?? null}
                          onChange={(value) => updateStageParam(key, field.key, value)}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ── Weights ── */}
        {activeTab === "weights" && (
          <div className="p-4 space-y-4">
            {SCORE_DIMS.map((dim) => {
              const value = (editing.weights?.[dim] ?? 0) as number;
              return (
                <div key={dim} className="flex items-center gap-4">
                  <label className="w-28 text-sm text-zinc-400 text-right">
                    {t(`scoreDims.${dim}`, { defaultValue: dim })}
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={value}
                    onChange={(e) => updateWeight(dim, parseFloat(e.target.value))}
                    className="flex-1 accent-brand-500"
                  />
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    value={value}
                    onChange={(e) =>
                      updateWeight(
                        dim,
                        parseFloat(e.target.value) || 0,
                      )
                    }
                    className="w-20 bg-zinc-900 border border-border rounded-md px-2 py-1.5 text-sm text-zinc-200 text-right tabular-nums focus:outline-none focus:border-brand-500"
                  />
                </div>
              );
            })}
          </div>
        )}

        {/* ── Prompts ── */}
        {activeTab === "prompts" && (
          <div className="flex flex-col h-full">
            <div className="flex border-b border-border">
              {PROMPT_TEMPLATES.map((name) => (
                <button
                  key={name}
                  onClick={() => setActivePrompt(name)}
                  className={`px-4 py-2 text-sm border-b-2 transition-colors ${
                    activePrompt === name
                      ? "border-brand-500 text-brand-400"
                      : "border-transparent text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
            <div className="flex-1">
              <PromptEditor
                promptName={activePrompt}
                presetOverride={editing.prompts?.[activePrompt] ?? null}
                onSaveOverride={(content) =>
                  updatePromptOverride(activePrompt, content)
                }
              />
            </div>
          </div>
        )}
      </div>

      {/* Delete confirmation modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-border rounded-lg p-6 max-w-sm w-full mx-4">
            <div className="flex items-center gap-3 mb-3">
              <AlertTriangle className="w-5 h-5 text-amber-500" />
              <h3 className="text-sm font-semibold text-zinc-200">
                {t("confirmDeleteTitle")}
              </h3>
            </div>
            <p className="text-sm text-zinc-400 mb-5">
              {t("confirmDelete", { name: preset.displayName || preset.name })}
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-3 py-1.5 text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-md transition-colors"
              >
                {tCommon("cancel")}
              </button>
              <button
                onClick={() => {
                  setShowDeleteConfirm(false);
                  onDelete();
                }}
                className="px-3 py-1.5 text-xs bg-red-600 hover:bg-red-500 text-white rounded-md transition-colors"
              >
                {tCommon("delete")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
