"use client";

import { Zap, X } from "lucide-react";
import { useApp } from "@/contexts/AppContext";

export function DemoMode() {
  const { demoMode, toggleDemoMode } = useApp();

  if (!demoMode) return null;

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2.5 dark:border-amber-700 dark:bg-amber-950/30">
      <div className="flex items-center gap-2">
        <Zap className="h-4 w-4 text-amber-500 shrink-0" />
        <p className="text-xs text-amber-800 dark:text-amber-300">
          <span className="font-semibold">Demo mode</span> — viewing pre-loaded sample data.
          All API calls are disabled. Toggle off in the sidebar to use real pipeline outputs.
        </p>
      </div>
      <button
        onClick={toggleDemoMode}
        className="shrink-0 rounded p-1 hover:bg-amber-200/50 dark:hover:bg-amber-800/30 text-amber-700 dark:text-amber-400"
        aria-label="Disable demo mode"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
