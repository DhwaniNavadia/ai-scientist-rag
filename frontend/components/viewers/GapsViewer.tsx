"use client";

import { Target, ArrowRight } from "lucide-react";
import { Gap } from "@/lib/types";
import { cn } from "@/lib/utils";

interface GapsViewerProps {
  gaps: Gap[];
}

const priorityColors: Record<number, string> = {
  1: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  2: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  3: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
};

export function GapsViewer({ gaps }: GapsViewerProps) {
  if (gaps.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <Target className="mb-3 h-10 w-10 opacity-40" />
        <p className="text-sm">No research gaps identified yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        {gaps.length} research gap{gaps.length !== 1 ? "s" : ""} identified
      </p>
      {gaps.map((gap) => (
        <div
          key={gap.gap_id}
          className="rounded-lg border border-border bg-card p-5 space-y-3"
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-mono font-medium text-primary">
                {gap.gap_id}
              </span>
              {gap.gap_type && (
                <span className="rounded bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground capitalize">
                  {gap.gap_type.replace(/_/g, " ")}
                </span>
              )}
            </div>
            {gap.priority !== undefined && gap.priority !== null && (
              <span
                className={cn(
                  "shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold",
                  priorityColors[gap.priority] ?? "bg-secondary text-secondary-foreground"
                )}
              >
                P{gap.priority}
              </span>
            )}
          </div>

          {/* Gap description */}
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">Gap Description</p>
            <p className="text-sm text-foreground leading-relaxed">{gap.gap_description}</p>
          </div>

          {/* Actionable direction */}
          {gap.actionable_direction && (
            <div className="flex items-start gap-2 rounded-md bg-primary/5 px-3 py-2.5">
              <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <div>
                <p className="text-xs font-medium text-primary mb-0.5">Actionable Direction</p>
                <p className="text-sm text-foreground leading-relaxed">
                  {gap.actionable_direction}
                </p>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
