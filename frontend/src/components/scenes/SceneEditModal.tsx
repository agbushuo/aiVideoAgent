"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { Scene, SceneUpdateRequest, SCENE_TYPES, MULTI_SCORE_DIMENSIONS } from "@/types/scene";

interface SceneEditModalProps {
  scene: Scene | null;
  taskId: string;
  onClose: () => void;
  onSave: (taskId: string, sceneId: number, data: SceneUpdateRequest) => Promise<void>;
}

const SCORE_DIMENSION_LABELS: Record<string, string> = {
  hook: "开头吸引力",
  emotion: "情绪强度",
  comedy: "搞笑程度",
  action: "动作/冲突",
  information: "信息密度",
  suspense: "悬念感",
  climax: "高潮程度",
  viral: "传播潜力",
};

export default function SceneEditModal({ scene, taskId, onClose, onSave }: SceneEditModalProps) {
  if (!scene) return null;

  const [sceneType, setSceneType] = useState(scene.scene_type);
  const [tagsText, setTagsText] = useState(scene.tags.join(", "));
  const [summary, setSummary] = useState(scene.summary);
  const [scores, setScores] = useState<Record<string, number>>({ ...scene.multi_score });
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    const data: SceneUpdateRequest = {
      scene_type: sceneType,
      tags: tagsText
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      summary,
      multi_score: scores,
    };
    await onSave(taskId, scene.scene_id, data);
    setSaving(false);
  };

  const handleScoreChange = (dim: string, value: string) => {
    const num = parseFloat(value);
    if (!isNaN(num)) {
      setScores((prev) => ({ ...prev, [dim]: Math.min(10, Math.max(0, num)) }));
    }
  };

  // Close on Escape key
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-surface border border-border rounded-lg shadow-2xl w-full max-w-xl mx-4 max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-zinc-200">编辑场景</h2>
            <span className="text-xs text-zinc-500 font-mono">场景 #{scene.scene_id}</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-zinc-500 hover:text-zinc-200 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {/* Scene Type */}
          <div>
            <label className="block text-xs text-zinc-500 mb-1.5 uppercase">场景类型</label>
            <select
              value={sceneType}
              onChange={(e) => setSceneType(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded-md text-zinc-200 focus:outline-none focus:border-brand-500 transition-colors"
            >
              {SCENE_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>

          {/* Tags */}
          <div>
            <label className="block text-xs text-zinc-500 mb-1.5 uppercase">标签</label>
            <input
              type="text"
              value={tagsText}
              onChange={(e) => setTagsText(e.target.value)}
              placeholder="tag1, tag2, tag3"
              className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded-md text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-brand-500 transition-colors"
            />
            <p className="text-xs text-zinc-600 mt-1">用逗号分隔多个标签</p>
          </div>

          {/* Summary */}
          <div>
            <label className="block text-xs text-zinc-500 mb-1.5 uppercase">摘要</label>
            <textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 text-sm bg-surface-elevated border border-border rounded-md text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-brand-500 transition-colors resize-none"
            />
          </div>

          {/* Multi-Score */}
          <div>
            <label className="block text-xs text-zinc-500 mb-2 uppercase">多维评分</label>
            <div className="grid grid-cols-2 gap-x-4 gap-y-2">
              {MULTI_SCORE_DIMENSIONS.map((dim) => (
                <div key={dim} className="flex items-center gap-2">
                  <span className="text-xs text-zinc-500 w-20 truncate" title={SCORE_DIMENSION_LABELS[dim] || dim}>
                    {SCORE_DIMENSION_LABELS[dim] || dim}
                  </span>
                  <input
                    type="number"
                    min={0}
                    max={10}
                    step={0.5}
                    value={scores[dim] ?? ""}
                    onChange={(e) => handleScoreChange(dim, e.target.value)}
                    className="w-16 px-2 py-1.5 text-sm bg-surface-elevated border border-border rounded-md text-zinc-200 text-center focus:outline-none focus:border-brand-500 transition-colors"
                  />
                  <span className="text-xs text-zinc-600">/10</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-border shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm bg-brand-600 hover:bg-brand-500 disabled:bg-brand-800 disabled:text-zinc-500 text-white rounded-md transition-colors flex items-center gap-2"
          >
            {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            保存
          </button>
        </div>
      </div>
    </div>
  );
}

const Loader2 = ({ className }: { className?: string }) => (
  <svg
    className={className}
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
  </svg>
);
