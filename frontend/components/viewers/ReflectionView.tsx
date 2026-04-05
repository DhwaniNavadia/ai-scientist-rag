"use client";

import { RefreshCw } from "lucide-react";
import { ReflectionEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ReflectionViewProps {
  reflections: ReflectionEntry[];
}

export function ReflectionView({ reflections }: ReflectionViewProps) {
  if (reflections.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <RefreshCw className="mb-3 h-10 w-10 opacity-40" />
        <p className="text-sm">No reflection logs available.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {reflections.map((entry) => (
        <div
          key={entry.gap_id}
          className="rounded-xl border border-border bg-card overflow-hidden"
        >
          {/* Header */}
          <div className="border-b border-border bg-muted/30 px-5 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <RefreshCw className="h-4 w-4 text-muted-foreground" />
              <span className="font-mono text-xs font-medium text-primary">{entry.gap_id}</span>
            </div>
            {entry.improvement_score !== undefined && (
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Improvement:</span>
                <ImprovementBar score={entry.improvement_score} />
              </div>
            )}
          </div>

          <div className="p-5 space-y-4">
            {/* Original hypothesis */}
            <div className="space-y-1.5">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Original Hypothesis
              </p>
              <p className="text-sm text-foreground leading-relaxed bg-muted/40 rounded-md px-3 py-2">
                {entry.original_hypothesis}
              </p>
            </div>

            {/* Improvement plan */}
            {entry.improvement_plan && (
              <div className="space-y-1.5">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  Improvement Plan
                </p>
                <p className="text-sm text-foreground leading-relaxed border-l-2 border-primary/40 pl-3">
                  {entry.improvement_plan}
                </p>
              </div>
            )}

            {/* Revised hypothesis */}
            {entry.revised_hypothesis && (
              <div className="space-y-1.5">
                <p className="text-xs font-semibold text-primary uppercase tracking-wide">
                  Revised Hypothesis
                </p>
                <p className="text-sm text-foreground leading-relaxed bg-primary/5 rounded-md px-3 py-2 border border-primary/20">
                  {entry.revised_hypothesis}
                </p>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function ImprovementBar({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, score * 100));
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            pct >= 70
              ? "bg-green-500"
              : pct >= 40
              ? "bg-yellow-500"
              : "bg-red-400"
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-mono text-muted-foreground">
        {(score * 100).toFixed(0)}%
      </span>
    </div>
  );
}
