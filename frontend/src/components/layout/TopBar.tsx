"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Film,
  Play,
  Square,
  Download,
  Settings,
  Languages,
} from "lucide-react";
import { useTaskStore } from "@/stores/taskStore";

export default function TopBar() {
  const t = useTranslations("topbar");
  const pathname = usePathname();
  const currentTask = useTaskStore((s) => s.currentTask);
  const sseConnected = useTaskStore((s) => s.sseConnected);
  const resumeTask = useTaskStore((s) => s.resumeTask);
  const cancelTask = useTaskStore((s) => s.cancelTask);

  const isWorkspace = pathname?.startsWith("/tasks/") && pathname.split("/").length > 2;
  const isDone = currentTask && ["completed", "cancelled", "error"].includes(currentTask.status);

  const switchLocale = (locale: string) => {
    document.cookie = `NEXT_LOCALE=${locale};path=/;max-age=31536000`;
    window.location.reload();
  };

  return (
    <header className="h-12 border-b border-border bg-surface flex items-center justify-between px-4 shrink-0">
      {/* Left: Logo + Project */}
      <div className="flex items-center gap-3">
        <Link href="/" className="flex items-center gap-2">
          <Film className="w-5 h-5 text-brand-400" />
          <span className="font-semibold text-sm">VideoAgent</span>
        </Link>
        {isWorkspace && currentTask && (
          <>
            <span className="text-zinc-600">/</span>
            <span className="text-sm text-zinc-300 truncate max-w-xs">
              {currentTask.video_path.split("/").pop()}
            </span>
          </>
        )}
      </div>

      {/* Center: Action buttons */}
      {isWorkspace && currentTask && (
        <div className="flex items-center gap-2">
          {!isDone && (
            <button
              onClick={() => resumeTask(currentTask.task_id)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-brand-600 hover:bg-brand-500 rounded-md transition-colors"
              title={t("runPipeline")}
            >
              <Play className="w-3.5 h-3.5" />
              {t("run")}
            </button>
          )}
          {!isDone && (
            <button
              onClick={() => cancelTask(currentTask.task_id)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-zinc-700 hover:bg-zinc-600 rounded-md transition-colors"
              title={t("stopPipeline")}
            >
              <Square className="w-3.5 h-3.5" />
              {t("stop")}
            </button>
          )}
          <button
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-zinc-700 hover:bg-zinc-600 rounded-md transition-colors"
            title={t("exportClips")}
          >
            <Download className="w-3.5 h-3.5" />
            {t("export")}
          </button>
        </div>
      )}

      {/* Right: Status + Language + Settings */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <div
            className={`w-2 h-2 rounded-full ${sseConnected ? "bg-green-400" : "bg-zinc-600"}`}
          />
          <span className="text-xs text-zinc-400">
            {sseConnected ? t("connected") : t("disconnected")}
          </span>
        </div>
        <button
          className="flex items-center gap-1 px-2 py-1 text-xs text-zinc-400 hover:text-zinc-200 transition-colors rounded"
          onClick={() => switchLocale("en")}
          title="Switch to English"
        >
          <Languages className="w-3.5 h-3.5" />
          {t("langEn")}
        </button>
        <button className="text-zinc-400 hover:text-zinc-200 transition-colors" title={t("settings")}>
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
