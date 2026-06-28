"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { useTaskStore } from "@/stores/taskStore";
import { LogEntry } from "@/types/api";
import { ArrowDown, CirclePause, Activity } from "lucide-react";

const levelConfig = {
  info: { color: "text-zinc-400", badge: "bg-zinc-700 text-zinc-300" },
  success: { color: "text-green-400", badge: "bg-green-900/50 text-green-400" },
  warning: { color: "text-yellow-400", badge: "bg-yellow-900/30 text-yellow-400" },
  error: { color: "text-red-400", badge: "bg-red-900/40 text-red-400" },
};

function formatTime(timestamp: number): string {
  const date = new Date(timestamp * 1000);
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function LogPanel({ taskId }: { taskId: string }) {
  const t = useTranslations("console");
  const logs = useTaskStore((s) => s.consoleLogs[taskId] || []);
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [hasMore, setHasMore] = useState(false);

  const isNearBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }, []);

  // Auto-scroll on new logs
  useEffect(() => {
    if (autoScroll && logs.length > 0) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs.length, autoScroll]);

  // Track scroll position to detect manual scroll up
  const handleScroll = useCallback(() => {
    const nearBottom = isNearBottom();
    if (nearBottom !== autoScroll) {
      setAutoScroll(nearBottom);
      setHasMore(!nearBottom);
    }
  }, [isNearBottom, autoScroll]);

  // Scroll to bottom on click
  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    setAutoScroll(true);
    setHasMore(false);
  };

  if (logs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-zinc-500">
        <Activity className="w-10 h-10 mb-3 opacity-30" />
        <p className="text-sm">{t("noLogs")}</p>
        <p className="text-xs mt-1 text-zinc-600">
          {t("noLogsHint")}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[#0c0c14]">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-zinc-200">{t("logs")}</span>
          <span className="text-xs text-zinc-600">{logs.length} {t("entries")}</span>
        </div>
        <div className="flex items-center gap-2">
          {hasMore && (
            <button
              onClick={scrollToBottom}
              className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              <ArrowDown className="w-3 h-3" />
              {t("bottom")}
            </button>
          )}
          <div
            className={`flex items-center gap-1 text-xs ${
              autoScroll ? "text-blue-400" : "text-zinc-500"
            }`}
            title={autoScroll ? t("autoScroll") : t("paused")}
          >
            {autoScroll ? (
              <Activity className="w-3.5 h-3.5" />
            ) : (
              <CirclePause className="w-3.5 h-3.5" />
            )}
          </div>
        </div>
      </div>

      {/* Log entries */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto font-mono text-xs p-3"
      >
        {logs.map((log, i) => {
          const cfg = levelConfig[log.level] || levelConfig.info;
          const badgeClass = cfg.badge;

          return (
            <div
              key={i}
              className={`flex items-start gap-2 py-0.5 px-1 rounded hover:bg-white/5 ${
                log.level === "error" ? "bg-red-950/10" : ""
              }`}
            >
              {/* Timestamp */}
              <span className="text-zinc-600 shrink-0 w-20">{formatTime(log.timestamp)}</span>

              {/* Level badge */}
              <span
                className={`shrink-0 uppercase text-[10px] font-bold px-1.5 py-0.5 rounded ${badgeClass}`}
              >
                {log.level}
              </span>

              {/* Stage tag */}
              {log.step && (
                <span className="shrink-0 text-zinc-500 text-[10px] px-1 py-0.5 rounded bg-zinc-800/50">
                  {log.step}
                </span>
              )}

              {/* Message */}
              <span className={`${cfg.color} break-all`}>{log.message}</span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
