"use client";

import { useEffect } from "react";
import TopBar from "./TopBar";
import Sidebar from "./Sidebar";
import { useTaskStore } from "@/stores/taskStore";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const connectSSE = useTaskStore((s) => s.connectSSE);

  // Global SSE connection — receives events for ALL tasks
  // Keeps task list and dashboard in sync without requiring the detail page open
  useEffect(() => {
    const es = connectSSE(); // no taskId = global /api/events
    return () => {
      es?.close();
    };
  }, [connectSSE]);

  return (
    <div className="h-full flex flex-col">
      <TopBar />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        {children}
      </div>
    </div>
  );
}
