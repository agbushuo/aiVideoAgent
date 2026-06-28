"use client";

import { Layers } from "lucide-react";

interface EmptyStateProps {
  hasFilters: boolean;
}

export default function EmptyState({ hasFilters }: EmptyStateProps) {
  return (
    <div className="flex-1 flex items-center justify-center text-zinc-500">
      <div className="text-center">
        <Layers className="w-12 h-12 mx-auto mb-3 opacity-50" />
        <p className="text-lg font-medium text-zinc-400">
          {hasFilters ? "没有匹配的场景" : "暂无场景数据"}
        </p>
        <p className="text-sm mt-1 text-zinc-600">
          {hasFilters
            ? "尝试调整筛选条件"
            : "视频尚未完成 AI 分析，请先运行管线"}
        </p>
      </div>
    </div>
  );
}
