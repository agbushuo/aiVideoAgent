"use client";

import { useState, useCallback, useEffect } from "react";
import { savePreset, deletePreset, duplicatePreset, getPreset, getPresets, getClipModes } from "@/lib/api";
import type { PresetData } from "@/types/config";
import PresetList from "@/components/presets/PresetList";
import PresetEditor from "@/components/presets/PresetEditor";
import { useTranslations } from "next-intl";
import { Settings } from "lucide-react";

export default function PresetsPage() {
  const t = useTranslations("presets");
  const tCommon = useTranslations("common");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [currentPreset, setCurrentPreset] = useState<PresetData | null>(null);
  const [configPresets, setConfigPresets] = useState<{ name: string }[]>([]);
  const [configClipModes, setConfigClipModes] = useState<{ name: string }[]>([]);
  const [showNewModal, setShowNewModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDisplayName, setNewDisplayName] = useState("");
  const [newDescription, setNewDescription] = useState("");

  // Load config data for dropdowns
  useEffect(() => {
    getPresets()
      .then((res) => setConfigPresets(res.items))
      .catch(() => {});
    getClipModes()
      .then((res) => setConfigClipModes(res.items))
      .catch(() => {});
  }, []);

  const loadPreset = useCallback(async (name: string) => {
    try {
      const preset = await getPreset(name);
      setCurrentPreset(preset);
      setSelectedName(name);
    } catch (e) {
      console.error("Failed to load preset:", e);
    }
  }, []);

  const handleSave = async (preset: PresetData) => {
    await savePreset(preset);
    setCurrentPreset(preset);
  };

  const handleDelete = async () => {
    if (!selectedName) return;
    await deletePreset(selectedName);
    setSelectedName(null);
    setCurrentPreset(null);
    // Refresh list
    const refresh = (window as any).__presetListRefresh;
    if (refresh) refresh();
  };

  const handleDuplicate = async () => {
    if (!selectedName) return;
    const new_name = `${selectedName}_copy`;
    await duplicatePreset(selectedName, new_name);
    // Refresh list
    const refresh = (window as any).__presetListRefresh;
    if (refresh) refresh();
  };

  const handleCreateNew = async () => {
    if (!newName.trim()) return;

    const preset: PresetData = {
      name: newName.trim().toLowerCase().replace(/\s+/g, "-"),
      displayName: newDisplayName || newName,
      description: newDescription,
      stageParams: {
        transcribe: { language: "zh", model_name: "whisper-large-v3", device: "cuda" },
        scene_detection: { gap_threshold: 10, min_scene_duration: 3, max_scene_duration: 120 },
        scoring: { preset: "douyin", clip_mode: "all" },
        filtering: { max_clips: 0, min_gap: 0, target_duration: 0 },
        duration_planning: { target_duration: 0 },
        final_review: { num_to_select: null },
        clipping: { merge: true, transition: 0.5 },
      },
      weights: {
        hook: 0.125,
        emotion: 0.125,
        comedy: 0.125,
        action: 0.125,
        information: 0.125,
        suspense: 0.125,
        climax: 0.125,
        viral: 0.125,
      },
      prompts: {},
    };

    await savePreset(preset);
    setShowNewModal(false);
    setNewName("");
    setNewDisplayName("");
    setNewDescription("");
    setCurrentPreset(preset);
    setSelectedName(preset.name);
    // Refresh list
    const refresh = (window as any).__presetListRefresh;
    if (refresh) refresh();
  };

  return (
    <div className="flex h-full w-full">
      {/* Left: Preset list */}
      <div className="w-72 border-r border-border flex flex-col">
        <PresetList
          selectedName={selectedName}
          onSelect={loadPreset}
          onNew={() => setShowNewModal(true)}
          onDuplicate={handleDuplicate}
        />
      </div>

      {/* Right: Editor or empty state */}
      <div className="flex-1 flex flex-col">
        {currentPreset ? (
          <PresetEditor
            preset={currentPreset}
            onSave={handleSave}
            onDelete={handleDelete}
            onDuplicate={handleDuplicate}
            configPresets={configPresets}
            configClipModes={configClipModes}
          />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-zinc-500">
            <Settings className="w-12 h-12 mb-3 text-zinc-600" />
            <p className="text-sm">{t("noPresetSelected")}</p>
            <p className="text-xs mt-1">{t("noPresetSelectedHint")}</p>
          </div>
        )}
      </div>

      {/* New preset modal */}
      {showNewModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-border rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-base font-semibold text-zinc-200 mb-4">{t("newPreset")}</h3>

            <div className="space-y-3">
              <div>
                <label className="block text-xs text-zinc-400 mb-1">{t("presetName")}</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder={t("presetNamePlaceholder")}
                  className="w-full bg-zinc-800 border border-border rounded-md px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-xs text-zinc-400 mb-1">{t("presetDisplayName")}</label>
                <input
                  type="text"
                  value={newDisplayName}
                  onChange={(e) => setNewDisplayName(e.target.value)}
                  placeholder={t("presetDisplayNamePlaceholder")}
                  className="w-full bg-zinc-800 border border-border rounded-md px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-xs text-zinc-400 mb-1">{t("presetDescription")}</label>
                <textarea
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder={t("presetDescriptionPlaceholder")}
                  rows={2}
                  className="w-full bg-zinc-800 border border-border rounded-md px-3 py-2 text-sm text-zinc-200 resize-none focus:outline-none focus:border-brand-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => setShowNewModal(false)}
                className="px-3 py-1.5 text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-md transition-colors"
              >
                {tCommon("cancel")}
              </button>
              <button
                onClick={handleCreateNew}
                disabled={!newName.trim()}
                className="px-3 py-1.5 text-xs bg-brand-600 hover:bg-brand-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-md transition-colors"
              >
                {t("createPreset")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
