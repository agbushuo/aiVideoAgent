"use client";

import { useEffect, useMemo } from "react";
import { useParams } from "next/navigation";
import { useSceneStore } from "@/stores/sceneStore";
import SceneFiltersBar from "./SceneFiltersBar";
import SceneTable from "./SceneTable";
import SceneEditModal from "./SceneEditModal";
import EmptyState from "./EmptyState";
import { getAllUniqueTags } from "@/lib/sceneUtils";

export default function SceneExplorer() {
  const params = useParams();
  const taskId = params?.id as string;

  // Store selectors
  const scenes = useSceneStore((s) => s.scenes);
  const filters = useSceneStore((s) => s.filters);
  const sortBy = useSceneStore((s) => s.sortBy);
  const sortOrder = useSceneStore((s) => s.sortOrder);
  const selectedSceneIds = useSceneStore((s) => s.selectedSceneIds);
  const isLoading = useSceneStore((s) => s.isLoading);
  const isEditing = useSceneStore((s) => s.isEditing);
  const editingScene = useSceneStore((s) => s.editingScene);

  // Store actions
  const fetchScenes = useSceneStore((s) => s.fetchScenes);
  const setFilters = useSceneStore((s) => s.setFilters);
  const setSortBy = useSceneStore((s) => s.setSortBy);
  const setSortOrder = useSceneStore((s) => s.setSortOrder);
  const toggleSceneSelection = useSceneStore((s) => s.toggleSceneSelection);
  const selectAllScenes = useSceneStore((s) => s.selectAllScenes);
  const clearSelection = useSceneStore((s) => s.clearSelection);
  const openEditScene = useSceneStore((s) => s.openEditScene);
  const closeEditScene = useSceneStore((s) => s.closeEditScene);
  const updateScene = useSceneStore((s) => s.updateScene);

  // Auto-fetch on mount
  useEffect(() => {
    if (taskId) {
      fetchScenes(taskId);
    }
  }, [taskId]);

  // Re-fetch when filters or sort change (debounced)
  useEffect(() => {
    if (!taskId) return;
    const timer = setTimeout(() => {
      fetchScenes(taskId);
    }, 300);
    return () => clearTimeout(timer);
  }, [filters.tags.length, filters.minScore, filters.searchQuery, sortBy, sortOrder]);

  // Derive unique tags for filter chips
  const allTags = useMemo(() => getAllUniqueTags(scenes), [scenes]);

  // Check if we have any active filters
  const hasFilters =
    filters.tags.length > 0 || filters.minScore > 0 || filters.searchQuery.length > 0;

  const handleSortChange = (newSortBy: "score" | "start", newSortOrder: "desc" | "asc") => {
    setSortBy(newSortBy);
    setSortOrder(newSortOrder);
  };

  return (
    <div className="flex-1 flex flex-col min-w-0">
      {/* Filters bar */}
      <SceneFiltersBar
        filters={filters}
        sortBy={sortBy}
        sortOrder={sortOrder}
        allTags={allTags}
        onFilterChange={setFilters}
        onSortChange={handleSortChange}
      />

      {/* Selection indicator bar */}
      {selectedSceneIds.size > 0 && (
        <div className="flex items-center gap-3 px-4 py-1.5 bg-brand-900/20 border-b border-border shrink-0">
          <span className="text-sm text-brand-300">
            已选 {selectedSceneIds.size} 个场景
          </span>
          <button
            onClick={clearSelection}
            className="text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            清除选择
          </button>
        </div>
      )}

      {/* Table or empty state */}
      {scenes.length === 0 ? (
        <EmptyState hasFilters={hasFilters} />
      ) : (
        <SceneTable
          scenes={scenes}
          selectedSceneIds={selectedSceneIds}
          isLoading={isLoading}
          onToggleScene={toggleSceneSelection}
          onToggleAll={selectAllScenes}
          onEdit={openEditScene}
        />
      )}

      {/* Edit modal */}
      {isEditing && editingScene && (
        <SceneEditModal
          scene={editingScene}
          taskId={taskId}
          onClose={closeEditScene}
          onSave={updateScene}
        />
      )}
    </div>
  );
}
