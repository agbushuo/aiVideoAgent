"use client";

import { useEffect, useState } from "react";
import { getPrompt, savePrompt } from "@/lib/api";
import { useTranslations } from "next-intl";
import { Save, Loader2 } from "lucide-react";

interface PromptEditorProps {
  promptName: string;
  /** If provided, override value for this preset (stored in presets.json, not the file) */
  presetOverride?: string | null;
  onSaveOverride?: (content: string) => void;
}

export default function PromptEditor({
  promptName,
  presetOverride,
  onSaveOverride,
}: PromptEditorProps) {
  const t = useTranslations("presets");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setLoading(true);
    // If there's a preset override, use that; otherwise load the file
    if (presetOverride !== undefined) {
      setContent(presetOverride || "");
      setLoading(false);
    } else {
      getPrompt(promptName)
        .then((c) => setContent(c))
        .catch(() => setContent(""))
        .finally(() => setLoading(false));
    }
    setSaved(false);
  }, [promptName]);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (onSaveOverride) {
        // Save to preset override (stored in presets.json)
        onSaveOverride(content);
      } else {
        // Save to the prompt file
        await savePrompt(promptName, content);
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error("Failed to save prompt:", e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <div>
          <h4 className="text-sm font-medium text-zinc-200">{promptName}</h4>
          <p className="text-xs text-zinc-500">{t("promptEditHint")}</p>
        </div>
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
          {saving ? t("promptSaving") : saved ? t("promptSaved") : t("promptSave")}
        </button>
      </div>

      <div className="flex-1 overflow-hidden">
        {loading ? (
          <div className="p-4 text-xs text-zinc-500">{t("promptLoading")}</div>
        ) : (
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className="w-full h-full bg-zinc-950 border-0 px-4 py-3 text-sm font-mono text-zinc-300 resize-none focus:outline-none"
            spellCheck={false}
          />
        )}
      </div>
    </div>
  );
}
