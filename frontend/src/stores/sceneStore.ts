import { create } from "zustand";
import { Scene, ClipCandidate, SceneUpdateRequest } from "@/types/scene";
import * as api from "@/lib/api";

export interface SceneFilters {
  tags: string[];
  minScore: number;
  searchQuery: string;
}

interface SceneState {
  scenes: Scene[];
  candidates: ClipCandidate[];
  filters: SceneFilters;
  sortBy: "score" | "start";
  sortOrder: "desc" | "asc";
  selectedSceneIds: Set<number>;
  isLoading: boolean;

  // Editing state
  isEditing: boolean;
  editingScene: Scene | null;

  // Actions
  fetchScenes: (taskId: string) => Promise<void>;
  fetchCandidates: (taskId: string) => Promise<void>;
  setFilters: (filters: Partial<SceneFilters>) => void;
  setSortBy: (sortBy: "score" | "start") => void;
  setSortOrder: (sortOrder: "desc" | "asc") => void;
  toggleSceneSelection: (sceneId: number) => void;
  selectAllScenes: () => void;
  clearSelection: () => void;
  bulkSelect: (taskId: string, sceneIds: number[], selected: boolean) => Promise<void>;

  // Editing actions
  openEditScene: (scene: Scene) => void;
  closeEditScene: () => void;
  updateScene: (taskId: string, sceneId: number, data: SceneUpdateRequest) => Promise<void>;
}

export const useSceneStore = create<SceneState>((set, get) => ({
  scenes: [],
  candidates: [],
  filters: { tags: [], minScore: 0, searchQuery: "" },
  sortBy: "score",
  sortOrder: "desc",
  selectedSceneIds: new Set(),
  isLoading: false,

  isEditing: false,
  editingScene: null,

  fetchScenes: async (taskId) => {
    set({ isLoading: true });
    try {
      const { scenes, total } = await api.listScenes(taskId, {
        tag: get().filters.tags[0],
        min_score: get().filters.minScore || undefined,
        search: get().filters.searchQuery || undefined,
        sort: get().sortBy,
        order: get().sortOrder,
      });
      set({ scenes: scenes.slice(0, total), isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  fetchCandidates: async (taskId) => {
    try {
      const { candidates } = await api.listCandidates(taskId, get().sortBy, get().sortOrder);
      set({ candidates });
    } catch {
      // Scene not available yet
    }
  },

  setFilters: (filters) => {
    set({ filters: { ...get().filters, ...filters } });
  },

  setSortBy: (sortBy) => set({ sortBy }),

  setSortOrder: (sortOrder) => set({ sortOrder }),

  toggleSceneSelection: (sceneId) => {
    const selected = new Set(get().selectedSceneIds);
    if (selected.has(sceneId)) {
      selected.delete(sceneId);
    } else {
      selected.add(sceneId);
    }
    set({ selectedSceneIds: selected });
  },

  selectAllScenes: () => {
    const ids = get().scenes.map((s) => s.scene_id);
    set({ selectedSceneIds: new Set(ids) });
  },

  clearSelection: () => set({ selectedSceneIds: new Set() }),

  bulkSelect: async (taskId, sceneIds, selected) => {
    await api.bulkSelectCandidates(taskId, { scene_ids: sceneIds, selected });
    await get().fetchCandidates(taskId);
  },

  openEditScene: (scene) => {
    set({ isEditing: true, editingScene: { ...scene } });
  },

  closeEditScene: () => {
    set({ isEditing: false, editingScene: null });
  },

  updateScene: async (taskId, sceneId, data) => {
    try {
      const updatedScene = await api.updateScene(taskId, sceneId, data);
      set({
        scenes: get().scenes.map((s) =>
          s.scene_id === sceneId ? { ...s, ...updatedScene } : s,
        ),
        isEditing: false,
        editingScene: null,
      });
    } catch {
      // Update failed - keep modal open
    }
  },
}));
