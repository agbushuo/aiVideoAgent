"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import Layout from "@/components/layout/Layout";
import StatusBadge from "@/components/StatusBadge";
import ProgressBar from "@/components/ProgressBar";
import { useTaskStore } from "@/stores/taskStore";
import { useConfigStore } from "@/stores/configStore";
import { TaskListItem } from "@/types/api";
import { FolderOpen, Plus, Clock, ChevronRight, FileVideo } from "lucide-react";
import Link from "next/link";
import FileBrowser from "@/components/FileBrowser";

export default function DashboardPage() {
  const t = useTranslations("dashboard");
  const { tasks, isLoading, fetchTasks } = useTaskStore();
  const loadAll = useConfigStore((s) => s.loadAll);
  const [videoPath, setVideoPath] = useState("");
  const [language, setLanguage] = useState("zh");
  const [preset, setPreset] = useState("viral");
  const [creating, setCreating] = useState(false);
  const [showBrowser, setShowBrowser] = useState(false);

  useEffect(() => {
    fetchTasks();
    loadAll();
  }, []);

  const handleCreate = async () => {
    if (!videoPath.trim()) return;
    setCreating(true);
    try {
      await useTaskStore.getState().createTask({
        video_path: videoPath,
        language,
        preset,
        smart_clip: true,
        clip_mode: preset,
      });
      setVideoPath("");
    } finally {
      setCreating(false);
    }
  };

  const recentTasks = [...tasks].reverse().slice(0, 10);
  const activeTasks = tasks.filter(
    (t) => !["completed", "cancelled", "error"].includes(t.status),
  );
  const completedTasks = tasks.filter((t) => t.status === "completed");

  return (
    <Layout>
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-5xl mx-auto">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold">{t("title")}</h1>
            <p className="text-zinc-400 mt-1">
              {t("subtitle")}
            </p>
          </div>

          {/* Stats cards */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="bg-surface-elevated rounded-lg p-4 border border-border">
              <div className="flex items-center gap-2 text-zinc-400 text-sm">
                <Clock className="w-4 h-4" />
                {t("activeTasks")}
              </div>
              <p className="text-3xl font-bold mt-2">{activeTasks.length}</p>
            </div>
            <div className="bg-surface-elevated rounded-lg p-4 border border-border">
              <div className="flex items-center gap-2 text-zinc-400 text-sm">
                <FolderOpen className="w-4 h-4" />
                {t("totalTasks")}
              </div>
              <p className="text-3xl font-bold mt-2">{tasks.length}</p>
            </div>
            <div className="bg-surface-elevated rounded-lg p-4 border border-border">
              <div className="flex items-center gap-2 text-zinc-400 text-sm">
                <Plus className="w-4 h-4" />
                {t("completed")}
              </div>
              <p className="text-3xl font-bold mt-2">{completedTasks.length}</p>
            </div>
          </div>

          {/* Quick create */}
          <div className="bg-surface-elevated rounded-lg p-5 border border-border mb-8">
            <h2 className="text-lg font-semibold mb-4">{t("createNewTask")}</h2>
            <div className="flex flex-wrap gap-3 items-end">
              <div className="flex-1 min-w-[280px]">
                <label className="block text-xs text-zinc-400 mb-1">{t("videoPath")}</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={videoPath}
                    onChange={(e) => setVideoPath(e.target.value)}
                    placeholder={t("videoPathPlaceholder")}
                    className="flex-1 px-3 py-2 bg-zinc-900 border border-border rounded-md text-sm focus:outline-none focus:border-brand-500"
                  />
                  <button
                    onClick={() => setShowBrowser(true)}
                    className="px-3 py-2 bg-zinc-800 hover:bg-zinc-700 border border-border rounded-md text-sm cursor-pointer transition-colors flex items-center gap-1 shrink-0"
                  >
                    <FileVideo className="w-4 h-4 text-zinc-400" />
                    浏览
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-xs text-zinc-400 mb-1">{t("language")}</label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="px-3 py-2 bg-zinc-900 border border-border rounded-md text-sm focus:outline-none focus:border-brand-500"
                >
                  <option value="zh">{t("langZh")}</option>
                  <option value="en">{t("langEn")}</option>
                  <option value="ja">{t("langJa")}</option>
                  <option value="ko">{t("langKo")}</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-zinc-400 mb-1">{t("preset")}</label>
                <select
                  value={preset}
                  onChange={(e) => setPreset(e.target.value)}
                  className="px-3 py-2 bg-zinc-900 border border-border rounded-md text-sm focus:outline-none focus:border-brand-500"
                >
                  <option value="viral">{t("presetViral")}</option>
                  <option value="douyin">{t("presetDouyin")}</option>
                  <option value="youtube">{t("presetYoutube")}</option>
                  <option value="bilibili">{t("presetBilibili")}</option>
                </select>
              </div>
              <button
                onClick={handleCreate}
                disabled={creating || !videoPath.trim()}
                className="px-4 py-2 bg-brand-600 hover:bg-brand-500 disabled:bg-zinc-700 disabled:text-zinc-500 rounded-md text-sm font-medium transition-colors"
              >
                {creating ? t("creating") : t("createTask")}
              </button>
            </div>
          </div>

          {/* Recent tasks */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">{t("recentTasks")}</h2>
              <Link
                href="/tasks"
                className="text-sm text-brand-400 hover:text-brand-300 flex items-center gap-1"
              >
                {t("viewAll")} <ChevronRight className="w-4 h-4" />
              </Link>
            </div>

            {isLoading && recentTasks.length === 0 ? (
              <p className="text-zinc-500 text-sm">{t("loadingTasks")}</p>
            ) : recentTasks.length === 0 ? (
              <div className="bg-surface-elevated rounded-lg p-8 border border-border text-center">
                <FolderOpen className="w-8 h-8 mx-auto text-zinc-600 mb-2" />
                <p className="text-zinc-400">{t("noTasks")}</p>
                <p className="text-zinc-500 text-sm mt-1">
                  {t("noTasksHint")}
                </p>
              </div>
            ) : (
              <div className="bg-surface-elevated rounded-lg border border-border overflow-hidden">
                {recentTasks.map((task, i) => (
                  <TaskRow key={task.task_id} task={task} isLast={i === recentTasks.length - 1} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      {showBrowser && (
        <FileBrowser
          onSelect={(path) => {
            setVideoPath(path);
            setShowBrowser(false);
          }}
          onClose={() => setShowBrowser(false)}
        />
      )}
    </Layout>
  );
}

function TaskRow({ task, isLast }: { task: TaskListItem; isLast: boolean }) {
  return (
    <Link
      href={`/tasks/${task.task_id}`}
      className={`flex items-center gap-4 px-4 py-3 hover:bg-zinc-800/50 transition-colors ${
        !isLast ? "border-b border-border" : ""
      }`}
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{task.video_path.split("/").pop() || task.video_path}</p>
        <p className="text-xs text-zinc-500 mt-0.5">
          {task.task_id} • {task.progress.step || "idle"}
        </p>
      </div>
      <div className="w-32">
        <ProgressBar percent={task.progress.percent} />
      </div>
      <span className="text-xs text-zinc-500 w-10 text-right">
        {Math.round(task.progress.percent)}%
      </span>
      <StatusBadge status={task.status} />
      <ChevronRight className="w-4 h-4 text-zinc-600" />
    </Link>
  );
}
