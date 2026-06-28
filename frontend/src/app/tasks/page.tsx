"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import Layout from "@/components/layout/Layout";
import StatusBadge from "@/components/StatusBadge";
import ProgressBar from "@/components/ProgressBar";
import { useTaskStore } from "@/stores/taskStore";
import { TaskListItem, TaskStatus } from "@/types/api";
import { FolderOpen, Filter, ChevronRight, Trash2, CheckCheck, X } from "lucide-react";
import Link from "next/link";

export default function TasksPage() {
  const t = useTranslations("tasks");
  const { tasks, isLoading, fetchTasks, deleteTask, bulkDeleteTasks, selectedTaskIds, toggleSelectTask, selectAllTasks, clearSelection } = useTaskStore();
  const [statusFilter, setStatusFilter] = useState<TaskStatus | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleteOutputs, setDeleteOutputs] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    fetchTasks();
  }, []);

  // Poll for updates while tasks are running — fallback when SSE is down
  const hasRunning = tasks.some((t) =>
    !["completed", "cancelled", "error"].includes(t.status)
  );
  useEffect(() => {
    if (!hasRunning) return;
    const timer = setInterval(() => fetchTasks(), 5000);
    return () => clearInterval(timer);
  }, [hasRunning, tasks]);

  const filteredTasks = tasks.filter((t) => {
    if (statusFilter !== "all" && t.status !== statusFilter) return false;
    if (searchQuery && !t.video_path.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const filteredTaskIds = new Set(filteredTasks.map((t) => t.task_id));
  const allFilteredSelected = filteredTasks.length > 0 && filteredTasks.every((t) => selectedTaskIds.includes(t.task_id));
  const someSelected = filteredTasks.some((t) => selectedTaskIds.includes(t.task_id));

  const handleSelectAll = () => {
    if (allFilteredSelected) {
      // Deselect all filtered tasks
      clearSelection();
    } else {
      // Select all filtered tasks
      const newSelected = [...new Set([...selectedTaskIds, ...filteredTaskIds])];
      // We need to set them individually since there's no bulk set
      useTaskStore.setState({ selectedTaskIds: newSelected });
    }
  };

  const handleBulkDelete = async () => {
    if (selectedTaskIds.length === 0) return;
    setIsDeleting(true);
    try {
      await bulkDeleteTasks(selectedTaskIds, deleteOutputs);
      setShowDeleteDialog(false);
    } finally {
      setIsDeleting(false);
    }
  };

  const runningStatuses = new Set(["pending", "transcribing", "review_subtitles", "analyzing", "scoring", "filtering", "clipping"]);
  const selectedTasks = tasks.filter((t) => selectedTaskIds.includes(t.task_id));
  const hasRunningSelected = selectedTasks.some((t) => runningStatuses.has(t.status));

  const statusOptions: { key: string; value: TaskStatus | "all" }[] = [
    { key: "all", value: "all" },
    { key: "active", value: "transcribing" },
    { key: "review", value: "review_subtitles" },
    { key: "completed", value: "completed" },
    { key: "error", value: "error" },
  ];

  return (
    <Layout>
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-5xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold">{t("title")}</h1>
              <p className="text-zinc-400 mt-1">
                {filteredTasks.length} {t(filteredTasks.length !== 1 ? "taskCount_other" : "taskCount_one")}
              </p>
            </div>
            <Link
              href="/"
              className="px-4 py-2 bg-brand-600 hover:bg-brand-500 rounded-md text-sm font-medium transition-colors"
            >
              {t("newTask")}
            </Link>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-3 mb-4">
            <div className="flex items-center gap-2 bg-surface-elevated border border-border rounded-md px-2 py-1">
              <Filter className="w-3.5 h-3.5 text-zinc-500" />
              {statusOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setStatusFilter(opt.value)}
                  className={`px-2.5 py-1 text-xs rounded transition-colors ${
                    statusFilter === opt.value
                      ? "bg-zinc-700 text-zinc-100"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  {t(opt.key)}
                </button>
              ))}
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t("searchPlaceholder")}
              className="px-3 py-1.5 bg-zinc-900 border border-border rounded-md text-sm focus:outline-none focus:border-brand-500 ml-auto w-64"
            />
          </div>

          {/* Bulk action bar */}
          {selectedTaskIds.length > 0 && (
            <div className="flex items-center gap-3 mb-4 bg-zinc-800/80 border border-border rounded-md px-4 py-2.5">
              <CheckCheck className="w-4 h-4 text-brand-400" />
              <span className="text-sm">
                {t("selectedCount", { count: selectedTaskIds.length })}
              </span>
              <button
                onClick={() => setShowDeleteDialog(true)}
                className="ml-auto px-3 py-1.5 bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-600/30 rounded-md text-xs flex items-center gap-1.5 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                {t("bulkDelete")}
              </button>
              <button
                onClick={clearSelection}
                className="px-2 py-1.5 text-zinc-400 hover:text-zinc-200 text-xs transition-colors"
              >
                {t("cancel")}
              </button>
            </div>
          )}

          {/* Task list */}
          {isLoading && tasks.length === 0 ? (
            <p className="text-zinc-500 text-sm">{t("loading")}</p>
          ) : filteredTasks.length === 0 ? (
            <div className="bg-surface-elevated rounded-lg p-8 border border-border text-center">
              <FolderOpen className="w-8 h-8 mx-auto text-zinc-600 mb-2" />
              <p className="text-zinc-400">{t("noTasks")}</p>
              <p className="text-zinc-500 text-sm mt-1">
                {statusFilter !== "all" ? t("noTasksHint") : t("createHint")}
              </p>
            </div>
          ) : (
            <div className="bg-surface-elevated rounded-lg border border-border overflow-hidden">
              {/* Table header */}
              <div className="flex items-center gap-4 px-4 py-2 border-b border-border text-xs text-zinc-500 uppercase">
                <div className="w-8">
                  <input
                    type="checkbox"
                    checked={allFilteredSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = !allFilteredSelected && someSelected;
                    }}
                    onChange={handleSelectAll}
                    className="rounded border-zinc-600 bg-zinc-800 text-brand-500 focus:ring-brand-500 focus:ring-offset-0"
                  />
                </div>
                <div className="flex-1">{t("video")}</div>
                <div className="w-32">{t("progress")}</div>
                <div className="w-10 text-right">{t("percent")}</div>
                <div className="w-24">{t("status")}</div>
                <div className="w-8" />
              </div>

              {filteredTasks.map((task) => (
                <TaskRow
                  key={task.task_id}
                  task={task}
                  isSelected={selectedTaskIds.includes(task.task_id)}
                  onSelect={toggleSelectTask}
                  onDelete={() => deleteTask(task.task_id)}
                  t={t}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Delete confirmation dialog */}
      {showDeleteDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-zinc-900 border border-border rounded-lg p-6 w-full max-w-md mx-4 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-red-400 flex items-center gap-2">
                <Trash2 className="w-5 h-5" />
                确认批量删除
              </h3>
              <button
                onClick={() => setShowDeleteDialog(false)}
                className="text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-zinc-300 text-sm mb-4">
              即将删除 <span className="font-bold text-white">{selectedTaskIds.length}</span> 个任务。
            </p>

            {hasRunningSelected && (
              <div className="bg-yellow-600/10 border border-yellow-600/30 rounded-md p-3 mb-4">
                <p className="text-yellow-400 text-xs">
                  警告: 其中有正在运行的任务，删除后无法恢复。
                </p>
              </div>
            )}

            <label className="flex items-center gap-2.5 mb-5 cursor-pointer group">
              <input
                type="checkbox"
                checked={deleteOutputs}
                onChange={(e) => setDeleteOutputs(e.target.checked)}
                className="rounded border-zinc-600 bg-zinc-800 text-brand-500 focus:ring-brand-500 focus:ring-offset-0"
              />
              <span className="text-sm text-zinc-300 group-hover:text-zinc-100 transition-colors">
                同时删除输出文件（字幕、报告、剪辑视频）
              </span>
            </label>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowDeleteDialog(false)}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 border border-border rounded-md text-sm transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleBulkDelete}
                disabled={isDeleting}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 disabled:bg-red-800 disabled:text-zinc-400 rounded-md text-sm font-medium transition-colors"
              >
                {isDeleting ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}

function TaskRow({
  task,
  isSelected,
  onSelect,
  onDelete,
  t,
}: {
  task: TaskListItem;
  isSelected: boolean;
  onSelect: (taskId: string) => void;
  onDelete: () => void;
  t: (key: string) => string;
}) {
  return (
    <div className={`flex items-center gap-4 px-4 py-3 hover:bg-zinc-800/50 transition-colors border-b border-border last:border-b-0 group ${isSelected ? "bg-brand-600/5" : ""}`}>
      <div className="w-8 flex-shrink-0">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onSelect(task.task_id)}
          className="rounded border-zinc-600 bg-zinc-800 text-brand-500 focus:ring-brand-500 focus:ring-offset-0"
        />
      </div>
      <Link
        href={`/tasks/${task.task_id}`}
        className="flex-1 min-w-0 flex items-center gap-3"
      >
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">
            {task.video_path.split("/").pop() || task.video_path}
          </p>
          <p className="text-xs text-zinc-500 mt-0.5">
            {task.task_id} • {task.progress.step || "idle"}
          </p>
        </div>
      </Link>
      <div className="w-32">
        <ProgressBar percent={task.progress.percent} />
      </div>
      <span className="text-xs text-zinc-500 w-10 text-right">
        {Math.round(task.progress.percent)}%
      </span>
      <div className="w-24">
        <StatusBadge status={task.status} />
      </div>
      <div className="w-8 flex justify-end opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={onDelete}
          className="text-zinc-600 hover:text-red-400 transition-colors"
          title={t("deleteTask")}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
