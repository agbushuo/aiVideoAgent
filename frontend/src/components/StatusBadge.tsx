"use client";

import { useTranslations } from "next-intl";
import { TaskStatus } from "@/types/api";

const statusStyles: Record<TaskStatus, string> = {
  pending: "bg-zinc-700 text-zinc-200",
  transcribing: "bg-blue-900/50 text-blue-300 animate-pulse",
  review_subtitles: "bg-yellow-900/50 text-yellow-300",
  analyzing: "bg-purple-900/50 text-purple-300 animate-pulse",
  scoring: "bg-indigo-900/50 text-indigo-300 animate-pulse",
  filtering: "bg-cyan-900/50 text-cyan-300 animate-pulse",
  clipping: "bg-orange-900/50 text-orange-300 animate-pulse",
  completed: "bg-green-900/50 text-green-300",
  cancelled: "bg-zinc-800 text-zinc-400",
  error: "bg-red-900/50 text-red-300",
};

export default function StatusBadge({ status }: { status: TaskStatus }) {
  const t = useTranslations("status");

  return (
    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusStyles[status]}`}>
      {t(status)}
    </span>
  );
}
