"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Play, Square } from "lucide-react";
import { runPipeline, getPipelineStatus } from "@/lib/api";
import { PipelineStatus } from "@/lib/types";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorBanner } from "@/components/shared/ErrorBanner";

interface PipelineControlsProps {
  paperId: string;
  onComplete?: () => void;
}

type Mode = "full" | "tier1" | "tier2" | "eval";

const MODES: { id: Mode; label: string; description: string }[] = [
  { id: "full", label: "Run Full Pipeline", description: "All stages end-to-end (incl. cross-paper if 2+ papers uploaded)" },
  { id: "tier1", label: "Run Tier 1", description: "Single-paper extraction only" },
  { id: "tier2", label: "Run Tier 2", description: "Cross-paper comparison (needs 2+ papers)" },
  { id: "eval", label: "Run Evaluation", description: "Evaluate existing outputs" },
];

export function PipelineControls({ paperId, onComplete }: PipelineControlsProps) {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [launching, setLaunching] = useState<Mode | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await getPipelineStatus(paperId);
      setStatus(s);
      if (s.status === "completed" || s.status === "error") {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
        if (s.status === "completed") onComplete?.();
      }
    } catch {
      // silently ignore poll errors
    }
  }, [paperId, onComplete]);

  // Poll while running
  useEffect(() => {
    fetchStatus();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paperId]);

  const startPoll = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(fetchStatus, 3000);
  }, [fetchStatus]);

  async function handleRun(mode: Mode) {
    setError(null);
    setLaunching(mode);
    try {
      await runPipeline(paperId, mode);
      setStatus({ status: "running", current_step: "Starting…", progress: 0 });
      startPoll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start pipeline.");
    } finally {
      setLaunching(null);
    }
  }

  const isRunning = status?.status === "running";

  return (
    <div className="space-y-4">
      {/* Status indicator */}
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-muted-foreground">Status:</span>
        <StatusBadge status={status?.status ?? "idle"} />
        {isRunning && (status?.message || (status as unknown as Record<string, string>)?.["current_step"]) && (
          <span className="text-sm text-muted-foreground">
            {(status as unknown as Record<string, string>)?.["current_step"] ?? status?.message}
          </span>
        )}
        {isRunning && (
          <LoadingSpinner size="sm" />
        )}
      </div>

      {/* Progress bar */}
      {isRunning && typeof (status as unknown as Record<string, number>)?.["progress"] === "number" && (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500"
            style={{ width: `${Math.min(100, (status as unknown as Record<string, number>)?.["progress"] ?? 0)}%` }}
          />
        </div>
      )}

      {/* Error message from pipeline */}
      {status?.status === "error" && status.message && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {status.message}
        </div>
      )}

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Buttons */}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {MODES.map(({ id, label, description }) => (
          <button
            key={id}
            onClick={() => handleRun(id)}
            disabled={isRunning || !!launching}
            className="flex items-center gap-3 rounded-lg border border-input bg-background px-4 py-3 text-left transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            {launching === id ? (
              <LoadingSpinner size="sm" />
            ) : isRunning ? (
              <Square className="h-4 w-4 text-muted-foreground" />
            ) : (
              <Play className="h-4 w-4 text-primary" />
            )}
            <div>
              <p className="text-sm font-medium text-foreground">{label}</p>
              <p className="text-xs text-muted-foreground">{description}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
