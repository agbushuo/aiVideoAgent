"use client";

import { useCallback, useState, useRef } from "react";
import { Search, SlidersHorizontal, ChevronDown } from "lucide-react";
import { SceneFilters } from "@/stores/sceneStore";
import { getAllUniqueTags } from "@/lib/sceneUtils";

interface SceneFiltersBarProps {
  filters: SceneFilters;
  sortBy: "score" | "start";
  sortOrder: "desc" | "asc";
  allTags: string[];
  onFilterChange: (filters: Partial<SceneFilters>) => void;
  onSortChange: (sortBy: "score" | "start", sortOrder: "desc" | "asc") => void;
}

export default function SceneFiltersBar({
  filters,
  sortBy,
  sortOrder,
  allTags,
  onFilterChange,
  onSortChange,
}: SceneFiltersBarProps) {
  const [searchLocal, setSearchLocal] = useState(filters.searchQuery);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearchChange = (value: string) => {
    setSearchLocal(value);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      onFilterChange({ searchQuery: value });
    }, 300);
  };

  const toggleTag = (tag: string) => {
    const tags = filters.tags.includes(tag)
      ? filters.tags.filter((t: string) => t !== tag)
      : [...filters.tags, tag];
    onFilterChange({ tags });
  };

  const handleMinScoreChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFilterChange({ minScore: parseFloat(e.target.value) || 0 });
  };

  const sortOptions: { label: string; value: "score" | "start"; order: "desc" | "asc" }[] = [
    { label: "最高分 ↓", value: "score", order: "desc" },
    { label: "最高分 ↑", value: "score", order: "asc" },
    { label: "时间 ↑", value: "start", order: "asc" },
    { label: "时间 ↓", value: "start", order: "desc" },
  ];

  const currentSortLabel =
    sortOptions.find((o) => o.value === sortBy && o.order === sortOrder)?.label || "最高分 ↓";

  const [sortOpen, setSortOpen] = useState(false);

  return (
    <div className="flex flex-col gap-2 px-4 py-2.5 border-b border-border bg-surface shrink-0">
      {/* Row 1: Search + Min Score + Sort */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            type="text"
            value={searchLocal}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="搜索场景内容..."
            className="w-48 pl-8 pr-3 py-1.5 text-sm bg-surface-elevated border border-border rounded-md text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-brand-500 transition-colors"
          />
        </div>

        {/* Min Score */}
        <div className="flex items-center gap-1.5">
          <SlidersHorizontal className="w-3.5 h-3.5 text-zinc-500" />
          <label className="text-xs text-zinc-500">最低分:</label>
          <input
            type="number"
            min={0}
            max={10}
            step={0.5}
            value={filters.minScore || ""}
            onChange={handleMinScoreChange}
            placeholder="0"
            className="w-16 px-2 py-1.5 text-sm bg-surface-elevated border border-border rounded-md text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-brand-500 transition-colors"
          />
        </div>

        {/* Sort Dropdown */}
        <div className="relative">
          <button
            onClick={() => setSortOpen(!sortOpen)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-sm bg-surface-elevated border border-border rounded-md text-zinc-300 hover:text-zinc-200 hover:border-border-hover transition-colors"
          >
            {currentSortLabel}
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          {sortOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setSortOpen(false)} />
              <div className="absolute right-0 top-full mt-1 z-50 bg-surface border border-border rounded-md shadow-lg overflow-hidden min-w-[120px]">
                {sortOptions.map((opt) => (
                  <button
                    key={`${opt.value}-${opt.order}`}
                    onClick={() => {
                      onSortChange(opt.value, opt.order);
                      setSortOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-surface-elevated transition-colors ${
                      sortBy === opt.value && sortOrder === opt.order
                        ? "text-brand-400 bg-brand-900/20"
                        : "text-zinc-300"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Selected filters indicator */}
        {(filters.tags.length > 0 || filters.minScore > 0 || filters.searchQuery.length > 0) && (
          <button
            onClick={() => onFilterChange({ tags: [], minScore: 0, searchQuery: "" })}
            className="text-xs text-brand-400 hover:text-brand-300 transition-colors"
          >
            清除筛选
          </button>
        )}
      </div>

      {/* Row 2: Tag chips */}
      {allTags.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs text-zinc-600 mr-1">标签:</span>
          {allTags.map((tag) => {
            const isActive = filters.tags.includes(tag);
            return (
              <button
                key={tag}
                onClick={() => toggleTag(tag)}
                className={`px-2 py-0.5 text-xs rounded-full transition-colors ${
                  isActive
                    ? "bg-brand-900/50 text-brand-300 border border-brand-700/50"
                    : "bg-zinc-800 text-zinc-400 border border-transparent hover:bg-zinc-700"
                }`}
              >
                {tag}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
