"use client";

import { Lightbulb, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { HypothesisPair } from "@/lib/types";
import { cn } from "@/lib/utils";

interface HypothesesViewerProps {
  pairs: HypothesisPair[];
}

const decisionConfig: Record<
  string,
  { icon: React.ElementType; classes: string; label: string }
> = {
  KEEP: {
    icon: TrendingUp,
    classes: "text-green-600 bg-green-100 dark:text-green-400 dark:bg-green-900/30",
    label: "KEEP",
  },
  REVISE: {
    icon: Minus,
    classes: "text-yellow-600 bg-yellow-100 dark:text-yellow-400 dark:bg-yellow-900/30",
    label: "REVISE",
  },
  REJECT: {
    icon: TrendingDown,
    classes: "text-red-500 bg-red-100 dark:text-red-400 dark:bg-red-900/30",
    label: "REJECT",
  },
};

export function HypothesesViewer({ pairs }: HypothesesViewerProps) {
  if (pairs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <Lightbulb className="mb-3 h-10 w-10 opacity-40" />
        <p className="text-sm">No hypothesis pairs generated yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {pairs.map((pair) => (
        <div
          key={pair.gap_id}
          className="rounded-xl border border-border bg-card overflow-hidden"
        >
          {/* Header */}
          <div className="border-b border-border bg-muted/30 px-5 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-medium text-primary">
                {pair.gap_id}
              </span>
              <span className="text-xs text-muted-foreground">—</span>
              <span className="text-xs text-muted-foreground">
                Preferred: <span className="font-medium text-foreground">{pair.preferred}</span>
              </span>
            </div>
            {pair.agreement !== undefined && (
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs font-medium",
                  pair.agreement
                    ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                    : "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
                )}
              >
                {pair.agreement ? "Agreed" : "Disagreed"}
              </span>
            )}
          </div>

          {/* Two agents side by side */}
          <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-border">
            {[pair.agentA, pair.agentB].map((agent) => {
              const cfg = decisionConfig[agent.decision ?? ""] ?? decisionConfig.KEEP;
              const DecisionIcon = cfg.icon;
              const isPreferred = pair.preferred === agent.agent;
              return (
                <div
                  key={agent.agent}
                  className={cn("p-5 space-y-3", isPreferred && "bg-primary/3")}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-sm text-foreground">
                      {agent.agent}
                      {isPreferred && (
                        <span className="ml-2 text-xs text-primary">★ Preferred</span>
                      )}
                    </span>
                    <div className="flex items-center gap-2">
                      {agent.score !== undefined && (
                        <span className="text-xs font-mono font-medium text-muted-foreground">
                          {agent.score.toFixed(1)}/10
                        </span>
                      )}
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                          cfg.classes
                        )}
                      >
                        <DecisionIcon className="h-3 w-3" />
                        {cfg.label}
                      </span>
                    </div>
                  </div>

                  <p className="text-sm text-foreground leading-relaxed">
                    {agent.hypothesis}
                  </p>

                  {agent.rationale && (
                    <p className="text-xs text-muted-foreground italic leading-relaxed border-t border-border pt-2">
                      {agent.rationale}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
