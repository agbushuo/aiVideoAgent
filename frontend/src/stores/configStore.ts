import { create } from "zustand";
import {
  PresetInfo,
  ClipModeInfo,
  ScoreDimensionInfo,
  DurationTemplate,
} from "@/types/config";
import { PipelineStageInfo } from "@/types/stage";
import * as api from "@/lib/api";

interface ConfigState {
  presets: PresetInfo[];
  clipModes: ClipModeInfo[];
  sceneTypes: string[];
  scoreDimensions: ScoreDimensionInfo[];
  pipelineStages: PipelineStageInfo[];
  durationTemplates: DurationTemplate[];
  weights: Record<string, unknown>;
  loaded: boolean;

  // Actions
  loadAll: () => Promise<void>;
}

export const useConfigStore = create<ConfigState>((set) => ({
  presets: [],
  clipModes: [],
  sceneTypes: [],
  scoreDimensions: [],
  pipelineStages: [],
  durationTemplates: [],
  weights: {},
  loaded: false,

  loadAll: async () => {
    try {
      const [
        presets,
        clipModes,
        sceneTypes,
        scoreDimensions,
        pipelineStages,
        durationTemplates,
        weights,
      ] = await Promise.all([
        api.getPresets(),
        api.getClipModes(),
        api.getSceneTypes(),
        api.getScoreDimensions(),
        api.getPipelineStages(),
        api.getDurationTemplates(),
        api.getWeights(),
      ]);

      set({
        presets: presets.items,
        clipModes: clipModes.items,
        sceneTypes: sceneTypes.items,
        scoreDimensions: scoreDimensions.items,
        pipelineStages: pipelineStages.items,
        durationTemplates: durationTemplates.items,
        weights,
        loaded: true,
      });
    } catch {
      // Backend may not be running — config will load lazily
    }
  },
}));
