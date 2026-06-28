"use client";

import { X, ChevronRight, FolderOpen, FileVideo, HardDrive } from "lucide-react";
import { useEffect, useState, useCallback } from "react";

interface FsEntry {
  name: string;
  path: string;
  type: "directory" | "file";
  size: number | null;
  is_video: boolean;
  extension: string;
}

interface FileBrowserProps {
  onSelect: (path: string) => void;
  onClose: () => void;
}

export default function FileBrowser({ onSelect, onClose }: FileBrowserProps) {
  const [currentPath, setCurrentPath] = useState("");
  const [items, setItems] = useState<FsEntry[]>([]);
  const [drives, setDrives] = useState<FsEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "video">("video");

  const fetchDrives = useCallback(async () => {
    try {
      const res = await fetch("/api/fs/drives");
      const data = await res.json();
      const driveItems = data.items || [];
      setDrives(driveItems);
      setItems(driveItems);
      setCurrentPath("");
    } catch {
      setError("Failed to load drives");
    }
  }, []);

  const fetchDirectory = useCallback(async (path: string) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/fs/list?path=${encodeURIComponent(path)}`);
      if (!res.ok) {
        const err = await res.json();
        setError(err.detail || "Failed to list directory");
        setItems([]);
        return;
      }
      const data = await res.json();
      setItems(data.items || []);
      setCurrentPath(data.path || path);
    } catch {
      setError("Network error");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDrives();
  }, [fetchDrives]);

  const navigateTo = (path: string) => {
    fetchDirectory(path);
  };

  const handleSelect = (entry: FsEntry) => {
    if (entry.type === "directory") {
      navigateTo(entry.path);
    } else {
      onSelect(entry.path);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
  };

  const filteredItems =
    filter === "video"
      ? items.filter((i) => i.is_video || i.type === "directory")
      : items;

  const pathParts = currentPath.split("\\").filter(Boolean);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="bg-zinc-900 border border-border rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <FolderOpen className="w-4 h-4" />
            选择视频文件
          </h2>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-zinc-900/50">
          {drives.length > 0 && currentPath ? (
            <button
              onClick={() => {
                setItems(drives);
                setCurrentPath("");
              }}
              className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1 px-2 py-1 rounded hover:bg-zinc-800"
            >
              <HardDrive className="w-3 h-3" />
              驱动器
            </button>
          ) : null}
          {pathParts.map((part, i) => {
            const parentPath = pathParts.slice(0, i + 1).join("\\");
            return (
              <span key={parentPath} className="flex items-center gap-1">
                {i > 0 && <ChevronRight className="w-3 h-3 text-zinc-600" />}
                <button
                  onClick={() => navigateTo(parentPath)}
                  className="text-xs text-zinc-400 hover:text-zinc-200 px-1 py-0.5 rounded hover:bg-zinc-800"
                >
                  {part}
                </button>
              </span>
            );
          })}
          <div className="ml-auto flex items-center gap-1">
            <button
              onClick={() => setFilter("video")}
              className={`text-xs px-2 py-1 rounded ${
                filter === "video"
                  ? "bg-zinc-700 text-zinc-200"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              视频
            </button>
            <button
              onClick={() => setFilter("all")}
              className={`text-xs px-2 py-1 rounded ${
                filter === "all"
                  ? "bg-zinc-700 text-zinc-200"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              全部
            </button>
          </div>
        </div>

        {/* File list */}
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-zinc-500 text-sm">
              加载中...
            </div>
          ) : error ? (
            <div className="flex items-center justify-center py-12 text-red-400 text-sm">
              {error}
            </div>
          ) : (
            <table className="w-full">
              <tbody>
                {filteredItems.map((item) => (
                  <tr
                    key={item.path}
                    onClick={() => handleSelect(item)}
                    className="hover:bg-zinc-800/50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-1.5">
                      <div className="flex items-center gap-2">
                        {item.type === "directory" ? (
                          <FolderOpen className="w-4 h-4 text-amber-400 shrink-0" />
                        ) : item.is_video ? (
                          <FileVideo className="w-4 h-4 text-brand-400 shrink-0" />
                        ) : (
                          <FileVideo className="w-4 h-4 text-zinc-600 shrink-0" />
                        )}
                        <span
                          className={`text-sm truncate ${
                            item.type === "directory"
                              ? "text-zinc-200 font-medium"
                              : item.is_video
                              ? "text-zinc-300"
                              : "text-zinc-500"
                          }`}
                        >
                          {item.name}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-1.5 text-xs text-zinc-500 text-right">
                      {item.size ? formatSize(item.size) : ""}
                    </td>
                  </tr>
                ))}
                {filteredItems.length === 0 && !loading && (
                  <tr>
                    <td colSpan={2} className="py-8 text-center text-zinc-500 text-sm">
                      空目录
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-border text-xs text-zinc-500">
          <span>{filteredItems.length} 个项目</span>
          <span>双击选择</span>
        </div>
      </div>
    </div>
  );
}
