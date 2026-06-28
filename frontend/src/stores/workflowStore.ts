import { create } from "zustand";
import { PipelineStageInfo, StageId } from "@/types/stage";
import { NODE_LAYOUT } from "@/types/workflow";

export interface PipelineNode {
  id: StageId;
  type: string;
  position: { x: number; y: number };
  data: {
    label: string;
    icon: string;
    enabled: boolean;
    status: "pending" | "running" | "completed" | "failed" | "skipped";
    params: Record<string, unknown>;
    duration: number | null;
  };
}

export interface PipelineEdge {
  id: string;
  source: StageId;
  target: StageId;
}

interface WorkflowState {
  nodes: PipelineNode[];
  edges: PipelineEdge[];
  selectedNodeId: StageId | null;
  stages: PipelineStageInfo[];

  // Actions
  initFromStages: (stages: PipelineStageInfo[]) => void;
  toggleStage: (stageId: StageId) => void;
  updateStageParams: (stageId: StageId, params: Record<string, unknown>) => void;
  updateStageStatus: (stageId: StageId, status: string, duration?: number) => void;
  selectNode: (stageId: StageId | null) => void;
  resetStageParams: (stageId: StageId) => void;
  clearWorkflow: () => void;
  exportConfig: () => { stages: { stage_id: string; enabled: boolean; params: Record<string, unknown> }[] };
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  stages: [],

  initFromStages: (stages) => {
    set({ stages });
    const nodes: PipelineNode[] = stages.map((s) => {
      const layout = NODE_LAYOUT[s.stage_id];
      return {
        id: s.stage_id as StageId,
        type: "pipelineNode",
        position: layout ?? { x: 400, y: 0 },
        data: {
          label: s.label,
          icon: s.icon,
          enabled: true,
          status: "pending",
          params: { ...s.default_params },
          duration: null,
        },
      };
    });

    const edges: PipelineEdge[] = [];
    stages.forEach((s) => {
      for (const dep of s.dependencies) {
        edges.push({
          id: `${dep}-${s.stage_id}`,
          source: dep as StageId,
          target: s.stage_id as StageId,
        });
      }
    });

    set({ nodes, edges });
  },

  toggleStage: (stageId) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === stageId
          ? { ...n, data: { ...n.data, enabled: !n.data.enabled } }
          : n,
      ),
    });
  },

  updateStageParams: (stageId, params) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === stageId
          ? { ...n, data: { ...n.data, params: { ...n.data.params, ...params } } }
          : n,
      ),
    });
  },

  updateStageStatus: (stageId, status, duration) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === stageId
          ? {
              ...n,
              data: {
                ...n.data,
                status: status as PipelineNode["data"]["status"],
                duration: duration ?? n.data.duration,
              },
            }
          : n,
      ),
    });
  },

  resetStageParams: (stageId) => {
    const stage = get().stages.find((s) => s.stage_id === stageId);
    if (stage) {
      get().updateStageParams(stageId, { ...stage.default_params });
    }
  },
  clearWorkflow: () => set({ nodes: [], edges: [], selectedNodeId: null, stages: [] }),
  selectNode: (stageId) => set({ selectedNodeId: stageId }),

  exportConfig: () => {
    const { nodes } = get();
    return {
      stages: nodes.map((n) => ({
        stage_id: n.id,
        enabled: n.data.enabled,
        params: n.data.params,
      })),
    };
  },
}));
