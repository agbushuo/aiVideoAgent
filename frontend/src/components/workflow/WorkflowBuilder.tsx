"use client";

import { useState, useEffect } from "react";
import { useWorkflowStore } from "@/stores/workflowStore";
import { useConfigStore } from "@/stores/configStore";
import { useTaskStore } from "@/stores/taskStore";
import ReactFlowCanvas from "./ReactFlowCanvas";
import ConfigPanel from "./ConfigPanel";
import { Play, Loader2 } from "lucide-react";
import { LANGUAGE_OPTIONS } from "@/types/workflow";

export default function WorkflowBuilder() {
  const stages = useConfigStore((s) => s.pipelineStages);
  const loaded = useConfigStore((s) => s.loaded);
  const initFromStages = useWorkflowStore((s) => s.initFromStages);
  const exportConfig = useWorkflowStore((s) => s.exportConfig);
  const createTask = useTaskStore((s) => s.createTask);
  const currentTask = useTaskStore((s) => s.currentTask);
  const resumeTask = useTaskStore((s) => s.resumeTask);

  const [videoPath, setVideoPath] = useState("");
  const [language, setLanguage] = useState("zh");
  const [skipExistingTranscript, setSkipExistingTranscript] = useState(false);
  const [isRunning, setIsRunning] = useState(false);

  // If viewing an existing task, pre-fill video path from it (read-only)
  useEffect(() => {
    if (currentTask) {
      setVideoPath(currentTask.video_path);
      setLanguage(currentTask.language || "zh");
    }
  }, [currentTask?.task_id]);

  // Initialize workflow from config stages
  useEffect(() => {
    if (loaded && stages.length > 0) {
      initFromStages(stages);
    }
  }, [loaded, stages]);

  const handleRun = async () => {
    if (!videoPath.trim() || isRunning) return;
    setIsRunning(true);
    try {
      if (currentTask) {
        // Resume existing task
        await resumeTask(currentTask.task_id);
      } else {
        // Create new task
        const pipelineConfig = exportConfig();
        await createTask({
          video_path: videoPath.trim(),
          language,
          pipeline_config: pipelineConfig,
          skip_existing_transcript: skipExistingTranscript,
          smart_clip: true,
        });
      }
    } catch {
      // Error handled by store
    } finally {
      setIsRunning(false);
    }
  };

  const isEditMode = !!currentTask;

  return (
    <div className="h-full w-full flex flex-col min-w-0">
      {/* Run Pipeline Bar */}
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border bg-surface-elevated shrink-0">
        <label className="text-xs text-zinc-400 whitespace-nowrap">视频路径</label>
        <input
          type="text"
          value={videoPath}
          onChange={(e) => setVideoPath(e.target.value)}
          placeholder="/path/to/video.mp4"
          readOnly={isEditMode}
          className={`flex-1 bg-zinc-900 border border-border rounded-md px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-brand-500 transition-colors min-w-0 ${
            isEditMode ? "opacity-60 cursor-not-allowed" : ""
          }`}
        />

        {!isEditMode && (
          <>
            <label className="text-xs text-zinc-400 whitespace-nowrap">语言</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="bg-zinc-900 border border-border rounded-md px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-brand-500 transition-colors"
            >
              {LANGUAGE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            <label className="flex items-center gap-1.5 text-xs text-zinc-400 cursor-pointer select-none whitespace-nowrap">
              <input
                type="checkbox"
                checked={skipExistingTranscript}
                onChange={(e) => setSkipExistingTranscript(e.target.checked)}
                className="rounded border-border bg-zinc-900 text-brand-500 focus:ring-brand-500 focus:ring-offset-0"
              />
              跳过已有转录
            </label>
          </>
        )}

        <button
          onClick={handleRun}
          disabled={!videoPath.trim() || isRunning}
          className="flex items-center gap-2 px-4 py-1.5 bg-brand-600 hover:bg-brand-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-sm font-medium rounded-md transition-colors shrink-0"
        >
          {isRunning ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          {isRunning
            ? "运行中..."
            : isEditMode
              ? "继续运行"
              : "运行管线"}
        </button>
      </div>

      {/* Canvas fills top, ConfigPanel below */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex-1 min-h-0">
          <ReactFlowCanvas />
        </div>
        <ConfigPanel />
      </div>
    </div>
  );
}
