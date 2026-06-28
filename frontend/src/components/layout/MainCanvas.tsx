"use client";

import { useTranslations } from "next-intl";
import { Workflow, Layers } from "lucide-react";
import dynamic from "next/dynamic";

const WorkflowBuilder = dynamic(() => import("@/components/workflow/WorkflowBuilder"), {
  ssr: false,
});

const SceneExplorer = dynamic(() => import("@/components/scenes/SceneExplorer"), {
  ssr: false,
});

type ViewMode = "workflow" | "scenes";

export type { ViewMode };

const viewIcons: Record<ViewMode, typeof Workflow> = {
  workflow: Workflow,
  scenes: Layers,
};

interface MainCanvasProps {
  activeView: ViewMode;
  onViewChange: (view: ViewMode) => void;
}

export default function MainCanvas({ activeView, onViewChange }: MainCanvasProps) {
  const t = useTranslations("mainCanvas");
  const views: ViewMode[] = ["workflow", "scenes"];

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-background">
      {/* View tabs */}
      <div className="flex items-center border-b border-border bg-surface px-4 gap-1">
        {views.map((viewId) => {
          const isActive = activeView === viewId;
          const Icon = viewIcons[viewId];
          return (
            <button
              key={viewId}
              onClick={() => onViewChange(viewId)}
              className={`flex items-center gap-2 px-3 py-2.5 text-sm border-b-2 transition-colors ${
                isActive
                  ? "border-brand-500 text-brand-400"
                  : "border-transparent text-zinc-400 hover:text-zinc-200"
              }`}
              title={t(viewId + "Desc")}
            >
              <Icon className="w-4 h-4" />
              {t(viewId)}
            </button>
          );
        })}
      </div>

      {/* Canvas area */}
      <div className="flex-1 overflow-hidden">
        {activeView === "workflow" && <WorkflowBuilder />}
        {activeView === "scenes" && <SceneExplorer />}
      </div>
    </div>
  );
}
