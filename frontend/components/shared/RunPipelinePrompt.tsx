"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Play, Loader2, CheckCircle2, AlertTriangle, FlaskConical } from "lucide-react";
import { runPipeline, getPipelineStatus } from "@/lib/api";
import type { PipelineStatus } from "@/lib/types";

interface RunPipelinePromptProps {
  paperId: string;
  /** Called when the pipeline finishes successfully so the parent can re-fetch data. */
  onComplete?: () => void;
}

export function RunPipelinePrompt({ paperId, onComplete }: RunPipelinePromptProps) {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll for status while running
  const startPolling = useCallback(() => {
    if (intervalRef.current) return;
    intervalRef.current = setInterval(async () => {
      try {
        const s = await getPipelineStatus(paperId);
        setStatus(s);
        if (s.status === "completed" || s.status === "error") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          intervalRef.current = null;
          if (s.status === "completed") onComplete?.();
        }
      } catch {
        // ignore transient poll failures
      }
    }, 5000);
  }, [paperId, onComplete]);

  // Check initial status on mount
  useEffect(() => {
    getPipelineStatus(paperId)
      .then((s) => {
        setStatus(s);
        if (s.status === "running") startPolling();
      })
      .catch(() => {
        // no status yet — that's fine
      });
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [paperId, startPolling]);

  const handleRun = async (mode: "tier1" | "full") => {
    setLaunching(true);
    setError(null);
    try {
      await runPipeline(paperId, mode);
      setStatus({ paper_id: paperId, status: "running", mode, message: "Pipeline started…", started_at: new Date().toISOString(), completed_at: null });
      startPolling();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLaunching(false);
    }
  };

  const isRunning = status?.status === "running";
  const isCompleted = status?.status === "completed";
  const isError = status?.status === "error";

  return (
    <div className="rounded-xl border border-border bg-card p-10 text-center space-y-4">
      {/* Icon */}
      <div className="flex justify-center">
        {isRunning ? (
          <Loader2 className="h-12 w-12 text-primary animate-spin" />
        ) : isCompleted ? (
          <CheckCircle2 className="h-12 w-12 text-green-500" />
        ) : isError ? (
          <AlertTriangle className="h-12 w-12 text-destructive" />
        ) : (
          <FlaskConical className="h-12 w-12 text-muted-foreground opacity-50" />
        )}
      </div>

      {/* Message */}
      {isRunning && (
        <>
          <p className="text-sm font-medium text-foreground">Pipeline is running…</p>
          <p className="text-xs text-muted-foreground">
            Mode: <span className="font-mono">{status?.mode}</span> — started{" "}
            {status?.started_at
              ? new Date(status.started_at).toLocaleTimeString()
              : "just now"}
          </p>
          <p className="text-xs text-muted-foreground">This page will refresh automatically when complete.</p>
        </>
      )}

      {isCompleted && (
        <>
          <p className="text-sm font-medium text-green-600 dark:text-green-400">
            Pipeline completed!
          </p>
          <p className="text-xs text-muted-foreground">Refreshing data…</p>
        </>
      )}

      {isError && (
        <>
          <p className="text-sm font-medium text-destructive">Pipeline failed</p>
          <p className="text-xs text-muted-foreground">{status?.message}</p>
        </>
      )}

      {!isRunning && !isCompleted && (
        <>
          <p className="text-sm text-muted-foreground">
            No analysis outputs found for this paper. Run the pipeline to get started.
          </p>

          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              onClick={() => handleRun("tier1")}
              disabled={launching}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {launching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run Tier 1 (Single Paper)
            </button>
            <button
              onClick={() => handleRun("full")}
              disabled={launching}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-5 py-2.5 text-sm font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50"
            >
              {launching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run Full Pipeline
            </button>
          </div>

          {error && (
            <p className="text-xs text-destructive pt-1">{error}</p>
          )}
        </>
      )}
    </div>
  );
}
