"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Layout from "@/components/layout/Layout";
import StatusBadge from "@/components/StatusBadge";
import ProgressBar from "@/components/ProgressBar";
import MainCanvas from "@/components/layout/MainCanvas";
import { useTaskStore } from "@/stores/taskStore";
import { useConfigStore } from "@/stores/configStore";
import { TaskDetailResponse } from "@/types/api";
import type { ViewMode } from "@/components/layout/MainCanvas";
import { ArrowLeft, RefreshCw, Trash2, FileVideo } from "lucide-react";
import Link from "next/link";

export default function TaskWorkspacePage() {
  const t = useTranslations("taskDetail");
  const params = useParams();
  const taskId = params?.id as string;
  const { currentTask, fetchTask, deleteTask } = useTaskStore();
  const loadAll = useConfigStore((s) => s.loadAll);
  const [activeView, setActiveView] = useState<ViewMode>("workflow");

  useEffect(() => {
    fetchTask(taskId);
    loadAll();
  }, [taskId]);

  // Auto-refresh for running tasks
  useEffect(() => {
    if (currentTask && !["completed", "cancelled", "error"].includes(currentTask.status)) {
      const timer = setInterval(() => fetchTask(taskId), 3000);
      return () => clearInterval(timer);
    }
  }, [currentTask?.status, taskId]);

  if (!currentTask) {
    return (
      <Layout>
        <div className="flex-1 flex items-center justify-center text-zinc-500">
          <div className="text-center">
            <FileVideo className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p className="text-lg font-medium">{t("taskLoading")}</p>
            <p className="text-sm mt-1">{t("taskId")}: {taskId}</p>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="flex-1 flex flex-col min-w-0">
        {/* Task info bar */}
        <div className="flex items-center gap-4 px-4 py-2 border-b border-border bg-surface shrink-0">
          <Link
            href="/tasks"
            className="text-zinc-400 hover:text-zinc-200 transition-colors"
            title={t("backToTasks")}
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>

          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">
              {currentTask.video_path.split("/").pop() || currentTask.video_path}
            </p>
          </div>

          <StatusBadge status={currentTask.status} />

          <div className="w-40">
            <ProgressBar percent={currentTask.progress.percent} />
          </div>
          <span className="text-xs text-zinc-500 w-10 text-right">
            {Math.round(currentTask.progress.percent)}%
          </span>

          {currentTask.progress.step && (
            <span className="text-xs text-zinc-400">{currentTask.progress.step}</span>
          )}

          <button
            onClick={() => fetchTask(taskId)}
            className="text-zinc-400 hover:text-zinc-200 transition-colors"
            title={t("refresh")}
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => deleteTask(taskId)}
            className="text-zinc-400 hover:text-red-400 transition-colors"
            title={t("deleteTask")}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Stage progress bar */}
        <StageProgress stages={currentTask.stage_results} />

        {/* Main canvas */}
        <MainCanvas activeView={activeView} onViewChange={setActiveView} />
      </div>
    </Layout>
  );
}

function StageProgress({ stages }: { stages: Record<string, any> }) {
  const t = useTranslations("taskDetail");
  const stageOrder = [
    "transcribe", "scene_detection", "llm_annotation", "scoring",
    "filtering", "duration_planning", "final_review", "clipping",
  ];
  const stageKeys: Record<string, string> = {
    transcribe: "stageTranscribe",
    scene_detection: "stageScene",
    llm_annotation: "stageAnnotation",
    scoring: "stageScoring",
    filtering: "stageFiltering",
    duration_planning: "stagePlanning",
    final_review: "stageReview",
    clipping: "stageClipping",
  };

  const stageEntries = Object.entries(stages).filter(([k]) => stageOrder.includes(k));
  if (stageEntries.length === 0) return null;

  return (
    <div className="flex items-center gap-1 px-4 py-1.5 border-b border-border bg-surface-elevated shrink-0 overflow-x-auto">
      {stageOrder
        .filter((id) => stages[id])
        .map((id, i, arr) => {
          const stage = stages[id];
          const color =
            stage.status === "completed"
              ? "bg-green-500"
              : stage.status === "running"
                ? "bg-blue-500 animate-pulse"
                : stage.status === "failed"
                  ? "bg-red-500"
                  : stage.status === "skipped"
                    ? "bg-zinc-600"
                    : "bg-zinc-700";

          return (
            <div key={id} className="flex items-center gap-1 shrink-0">
              {i > 0 && <div className="w-3 h-px bg-zinc-700" />}
              <div
                className={`w-2 h-2 rounded-full ${color}`}
                title={`${t(stageKeys[id] || id)}: ${stage.status}`}
              />
              <span className="text-xs text-zinc-400">{t(stageKeys[id] || id)}</span>
            </div>
          );
        })}
    </div>
  );
}
