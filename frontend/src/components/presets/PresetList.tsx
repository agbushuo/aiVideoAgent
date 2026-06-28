"use client";

import { useEffect, useState } from "react";
import { listPresets } from "@/lib/api";
import type { PresetData } from "@/types/config";
import { SlidersHorizontal, Copy, Plus, Home } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";

interface PresetListProps {
  selectedName: string | null;
  onSelect: (name: string) => void;
  onNew: () => void;
  onDuplicate: (name: string) => void;
}

export default function PresetList({
  selectedName,
  onSelect,
  onNew,
  onDuplicate,
}: PresetListProps) {
  const t = useTranslations("presets");
  const [presets, setPresets] = useState<PresetData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listPresets()
      .then((data) => setPresets(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Expose a refresh function for callers (SSR-safe)
  const refresh = () => {
    listPresets()
      .then((data) => setPresets(data))
      .catch(() => {});
  };
  if (typeof window !== "undefined") {
    (window as any).__presetListRefresh = refresh;
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-border flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-200">{t("title")}</h2>
        <button
          onClick={onNew}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs bg-brand-600 hover:bg-brand-500 rounded-md transition-colors text-white"
        >
          <Plus className="w-3.5 h-3.5" />
          {t("newPreset")}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-xs text-zinc-500">{t("noPresetSelectedHint")}</div>
        ) : presets.length === 0 ? (
          <div className="p-4 text-xs text-zinc-500">{t("noPresetSelected")}</div>
        ) : (
          presets.map((preset) => (
            <div
              key={preset.name}
              onClick={() => onSelect(preset.name)}
              className={`group px-4 py-3 cursor-pointer border-b border-border/50 transition-colors ${
                selectedName === preset.name
                  ? "bg-brand-600/10 border-l-2 border-l-brand-500"
                  : "hover:bg-zinc-800/50"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-200 truncate">
                    {preset.displayName || preset.name}
                  </p>
                  <p className="text-xs text-zinc-500 truncate">{preset.description || preset.name}</p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDuplicate(preset.name);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-zinc-700 rounded transition-all"
                  title={t("duplicate")}
                >
                  <Copy className="w-3.5 h-3.5 text-zinc-400" />
                </button>
              </div>
              {/* Weight summary */}
              <div className="mt-1.5 flex gap-1 flex-wrap">
                {Object.entries(preset.weights || {})
                  .filter(([, v]) => v > 0)
                  .slice(0, 3)
                  .map(([dim, val]) => (
                    <span
                      key={dim}
                      className="inline-block px-1.5 py-0.5 text-[10px] bg-zinc-800 text-zinc-400 rounded"
                    >
                      {dim}:{(val as number).toFixed(1)}
                    </span>
                  ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Back to home */}
      <div className="p-3 border-t border-border">
        <Link
          href="/"
          className="flex items-center justify-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <Home className="w-3.5 h-3.5" />
          {t("backToHome")}
        </Link>
      </div>
    </div>
  );
}
