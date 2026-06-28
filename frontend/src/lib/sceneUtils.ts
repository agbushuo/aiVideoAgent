import { Scene } from "@/types/scene";

// Chinese labels (default)
const ZH_SCORE_DIMENSION_LABELS: Record<string, string> = {
  hook: "开头吸引力",
  emotion: "情绪强度",
  comedy: "搞笑程度",
  action: "动作/冲突",
  information: "信息密度",
  suspense: "悬念感",
  climax: "高潮程度",
  viral: "传播潜力",
};

// English labels
const EN_SCORE_DIMENSION_LABELS: Record<string, string> = {
  hook: "Hook",
  emotion: "Emotion",
  comedy: "Comedy",
  action: "Action",
  information: "Information",
  suspense: "Suspense",
  climax: "Climax",
  viral: "Viral",
};

/**
 * Get a localized label for a score dimension key.
 * @param key - The dimension key (e.g. "hook", "emotion")
 * @param locale - Locale string; defaults to "zh" if not provided
 * @returns The localized label, or the key itself if not found
 */
export function getScoreDimLabel(key: string, locale = "zh"): string {
  if (locale === "en") return EN_SCORE_DIMENSION_LABELS[key] || key;
  return ZH_SCORE_DIMENSION_LABELS[key] || key;
}

// Backward-compatible export (Chinese defaults)
export const SCORE_DIMENSION_LABELS_MAP = ZH_SCORE_DIMENSION_LABELS;

export function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function getMaxScore(scene: Scene): number {
  const values = Object.values(scene.multi_score);
  return values.length ? Math.max(...values) : 0;
}

export function getAverageScore(scene: Scene): number {
  const values = Object.values(scene.multi_score);
  if (values.length === 0) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

export function getScoreColor(score: number): string {
  if (score >= 8) return "text-green-400";
  if (score >= 5) return "text-yellow-400";
  return "text-red-400";
}

export function getScoreBarColor(score: number): string {
  if (score >= 8) return "bg-green-500";
  if (score >= 5) return "bg-yellow-500";
  return "bg-red-500";
}

export function getAllUniqueTags(scenes: Scene[]): string[] {
  const tagSet = new Set<string>();
  for (const scene of scenes) {
    for (const tag of scene.tags) {
      tagSet.add(tag);
    }
  }
  return Array.from(tagSet).sort();
}

export function truncate(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return text.slice(0, maxChars) + "...";
}

const SCENE_TYPE_COLORS: Record<string, string> = {
  Dialogue: "bg-blue-900/50 text-blue-300",
  Comedy: "bg-yellow-900/50 text-yellow-300",
  Fight: "bg-red-900/50 text-red-300",
  Emotion: "bg-pink-900/50 text-pink-300",
  Romance: "bg-pink-900/50 text-pink-300",
  Knowledge: "bg-cyan-900/50 text-cyan-300",
  Teaching: "bg-cyan-900/50 text-cyan-300",
  Suspense: "bg-purple-900/50 text-purple-300",
  Climax: "bg-orange-900/50 text-orange-300",
  Hook: "bg-green-900/50 text-green-300",
  Speech: "bg-indigo-900/50 text-indigo-300",
  Transition: "bg-zinc-700/50 text-zinc-400",
  Music: "bg-violet-900/50 text-violet-300",
  "B-roll": "bg-teal-900/50 text-teal-300",
  Other: "bg-zinc-800 text-zinc-400",
};

export function getSceneTypeColor(sceneType: string): string {
  return SCENE_TYPE_COLORS[sceneType] || "bg-zinc-800 text-zinc-400";
}
