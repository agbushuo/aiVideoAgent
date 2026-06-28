"use client";

import { useMemo } from "react";
import { Pencil, Check, Loader2 } from "lucide-react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from "@tanstack/react-table";
import { Scene } from "@/types/scene";
import {
  formatTime,
  getMaxScore,
  getScoreColor,
  getScoreBarColor,
  getSceneTypeColor,
  truncate,
} from "@/lib/sceneUtils";

interface SceneTableProps {
  scenes: Scene[];
  selectedSceneIds: Set<number>;
  isLoading: boolean;
  onToggleScene: (sceneId: number) => void;
  onToggleAll: () => void;
  onEdit: (scene: Scene) => void;
}

const columnHelper = createColumnHelper<Scene>();

export default function SceneTable({
  scenes,
  selectedSceneIds,
  isLoading,
  onToggleScene,
  onToggleAll,
  onEdit,
}: SceneTableProps) {
  const allSelected = scenes.length > 0 && selectedSceneIds.size === scenes.length;
  const someSelected = selectedSceneIds.size > 0 && !allSelected;

  const columns = useMemo(
    () => [
      // Checkbox
      columnHelper.display({
        id: "select",
        header: ({ table }) => (
          <Checkbox
            checked={allSelected}
            indeterminate={someSelected}
            onChange={() => {
              if (allSelected) {
                // Deselect all by toggling each selected
                // Simple approach: clear via toggling all
                table.getRowModel().rows.forEach((row) => {
                  onToggleScene(row.original.scene_id);
                });
              } else {
                onToggleAll();
              }
            }}
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={selectedSceneIds.has(row.original.scene_id)}
            onChange={() => onToggleScene(row.original.scene_id)}
          />
        ),
        size: 48,
        minSize: 48,
      }),

      // Scene ID
      columnHelper.accessor("scene_id", {
        header: "#",
        cell: (info) => (
          <span className="text-zinc-400 font-mono text-xs">{info.getValue()}</span>
        ),
        size: 60,
        minSize: 60,
      }),

      // Time
      columnHelper.accessor((row) => row.start, {
        id: "time",
        header: "时间",
        cell: (info) => {
          const scene = info.row.original;
          return (
            <div className="text-xs">
              <span className="text-zinc-300">
                {formatTime(scene.start)} - {formatTime(scene.end)}
              </span>
              <span className="text-zinc-500 ml-1.5">({formatTime(scene.duration)})</span>
            </div>
          );
        },
        size: 140,
        minSize: 120,
      }),

      // Scene Type
      columnHelper.accessor("scene_type", {
        header: "类型",
        cell: (info) => (
          <span className={`px-2 py-0.5 text-xs rounded-full ${getSceneTypeColor(info.getValue())}`}>
            {info.getValue()}
          </span>
        ),
        size: 90,
        minSize: 70,
      }),

      // Tags
      columnHelper.accessor("tags", {
        header: "标签",
        cell: (info) => {
          const tags = info.getValue();
          if (!tags || tags.length === 0) {
            return <span className="text-zinc-600 text-xs">—</span>;
          }
          return (
            <div className="flex gap-1 flex-wrap" title={tags.join(", ")}>
              {tags.slice(0, 3).map((tag) => (
                <span
                  key={tag}
                  className="px-1.5 py-0.5 text-xs bg-zinc-800 text-zinc-400 rounded"
                >
                  {tag}
                </span>
              ))}
              {tags.length > 3 && (
                <span className="text-xs text-zinc-600">+{tags.length - 3}</span>
              )}
            </div>
          );
        },
        size: 160,
        minSize: 100,
      }),

      // Summary
      columnHelper.accessor("summary", {
        header: "摘要",
        cell: (info) => (
          <div
            className="text-xs text-zinc-400"
            style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}
            title={info.getValue()}
          >
            {truncate(info.getValue(), 120)}
          </div>
        ),
        size: 300,
        minSize: 200,
      }),

      // Max Score with mini bar
      columnHelper.display({
        id: "maxScore",
        header: "最高分",
        cell: ({ row }) => {
          const scene = row.original;
          const maxScore = getMaxScore(scene);
          const scoreColor = getScoreColor(maxScore);
          const barColor = getScoreBarColor(maxScore);

          // Find which dimension has the max score
          let maxDim = "";
          for (const [dim, val] of Object.entries(scene.multi_score)) {
            if (val === maxScore) {
              maxDim = dim;
              break;
            }
          }

          return (
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${barColor} transition-all`}
                  style={{ width: `${(maxScore / 10) * 100}%` }}
                />
              </div>
              <span className={`text-xs font-mono ${scoreColor}`} title={`维度: ${maxDim}`}>
                {maxScore.toFixed(1)}
              </span>
            </div>
          );
        },
        size: 110,
        minSize: 90,
      }),

      // Actions
      columnHelper.display({
        id: "actions",
        cell: ({ row }) => (
          <button
            onClick={() => onEdit(row.original)}
            className="p-1 text-zinc-500 hover:text-brand-400 transition-colors"
            title="编辑"
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>
        ),
        size: 44,
        minSize: 44,
      }),
    ],
    [allSelected, someSelected, selectedSceneIds, onToggleScene, onToggleAll, onEdit],
  );

  const table = useReactTable({
    data: scenes,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  if (isLoading && scenes.length === 0) {
    return (
      <div className="flex-1 overflow-auto">
        <div className="min-w-[900px] px-4 py-8">
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4 animate-pulse">
                <div className="w-6 h-4 bg-zinc-800 rounded" />
                <div className="w-8 h-4 bg-zinc-800 rounded" />
                <div className="w-28 h-4 bg-zinc-800 rounded" />
                <div className="w-16 h-4 bg-zinc-800 rounded" />
                <div className="w-24 h-4 bg-zinc-800 rounded" />
                <div className="flex-1 h-4 bg-zinc-800 rounded" />
                <div className="w-20 h-4 bg-zinc-800 rounded" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto">
      <div className="min-w-[900px]">
        <table className="w-full border-collapse">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="border-b border-border bg-surface-elevated/50">
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-2 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider"
                    style={{ width: header.getSize() }}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => {
              const isSelected = selectedSceneIds.has(row.original.scene_id);
              return (
                <tr
                  key={row.original.scene_id}
                  className={`border-b border-border/50 transition-colors ${
                    isSelected
                      ? "bg-brand-900/10"
                      : "hover:bg-surface-elevated/30"
                  }`}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="px-4 py-2.5 text-sm align-middle"
                      style={{ width: cell.column.getSize() }}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-border bg-surface-elevated/30 text-xs text-zinc-500">
        <span>共 {scenes.length} 个场景</span>
        {selectedSceneIds.size > 0 && (
          <span className="text-brand-400">已选 {selectedSceneIds.size} 个</span>
        )}
      </div>
    </div>
  );
}

function Checkbox({
  checked,
  indeterminate = false,
  onChange,
}: {
  checked: boolean;
  indeterminate?: boolean;
  onChange: () => void;
}) {
  return (
    <button
      onClick={onChange}
      className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
        checked
          ? "bg-brand-600 border-brand-500"
          : indeterminate
            ? "bg-brand-800 border-brand-600"
            : "bg-zinc-800 border-zinc-600 hover:border-zinc-500"
      }`}
    >
      {checked && <Check className="w-3 h-3 text-white" />}
      {indeterminate && !checked && (
        <div className="w-2 h-0.5 bg-brand-300 rounded" />
      )}
    </button>
  );
}
