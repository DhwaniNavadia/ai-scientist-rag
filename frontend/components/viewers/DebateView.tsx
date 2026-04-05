"use client";

import { GitCompare } from "lucide-react";
import { HypothesisPair } from "@/lib/types";
import { cn } from "@/lib/utils";

interface DebateViewProps {
  pairs: HypothesisPair[];
}

export function DebateView({ pairs }: DebateViewProps) {
  if (pairs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <GitCompare className="mb-3 h-10 w-10 opacity-40" />
        <p className="text-sm">No debates recorded yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {pairs.map((pair) => (
        <div key={pair.gap_id} className="space-y-3">
          {/* Title bar */}
          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="shrink-0 rounded-full bg-primary/10 px-3 py-0.5 text-xs font-medium text-primary">
              Gap: {pair.gap_id}
            </span>
            <div className="h-px flex-1 bg-border" />
          </div>

          {/* Debate transcript style */}
          <div className="space-y-4">
            {/* Agent A proposal */}
            <DebateTurn
              agent={pair.agentA.agent}
              text={pair.agentA.hypothesis}
              rationale={pair.agentA.rationale}
              side="left"
              score={pair.agentA.score}
              decision={pair.agentA.decision}
              isPreferred={pair.preferred === pair.agentA.agent}
            />

            {/* Agent B proposal */}
            <DebateTurn
              agent={pair.agentB.agent}
              text={pair.agentB.hypothesis}
              rationale={pair.agentB.rationale}
              side="right"
              score={pair.agentB.score}
              decision={pair.agentB.decision}
              isPreferred={pair.preferred === pair.agentB.agent}
            />
          </div>

          {/* Verdict */}
          <div
            className={cn(
              "rounded-lg border px-4 py-3 text-sm",
              pair.agreement
                ? "border-green-300 bg-green-50 dark:border-green-800 dark:bg-green-950/30"
                : "border-orange-300 bg-orange-50 dark:border-orange-800 dark:bg-orange-950/30"
            )}
          >
            <span className="font-semibold">
              {pair.agreement ? "Agreement" : "Disagreement"}
            </span>{" "}
            — Preferred output:{" "}
            <span className="font-mono font-medium">{pair.preferred}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function DebateTurn({
  agent,
  text,
  rationale,
  side,
  score,
  decision,
  isPreferred,
}: {
  agent: string;
  text: string;
  rationale?: string;
  side: "left" | "right";
  score?: number;
  decision?: string;
  isPreferred: boolean;
}) {
  return (
    <div className={cn("flex gap-3", side === "right" && "flex-row-reverse")}>
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold",
          side === "left"
            ? "bg-sky-200 text-sky-800 dark:bg-sky-900 dark:text-sky-300"
            : "bg-violet-200 text-violet-800 dark:bg-violet-900 dark:text-violet-300"
        )}
      >
        {agent.replace("Agent", "").slice(0, 1)}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          "max-w-[85%] rounded-xl px-4 py-3 space-y-2",
          side === "left"
            ? "rounded-tl-none bg-sky-50 dark:bg-sky-950/40"
            : "rounded-tr-none bg-violet-50 dark:bg-violet-950/40",
          isPreferred && "ring-2 ring-primary/40"
        )}
      >
        <div className="flex items-center gap-2 justify-between">
          <span className="text-xs font-semibold text-foreground">
            {agent}
            {isPreferred && <span className="ml-1.5 text-primary">★</span>}
          </span>
          <div className="flex items-center gap-2">
            {score !== undefined && (
              <span className="text-xs font-mono text-muted-foreground">
                {score.toFixed(1)}/10
              </span>
            )}
            {decision && (
              <DecisionChip decision={decision} />
            )}
          </div>
        </div>
        <p className="text-sm text-foreground leading-relaxed">{text}</p>
        {rationale && (
          <p className="text-xs text-muted-foreground italic border-t border-border/50 pt-1.5">
            {rationale}
          </p>
        )}
      </div>
    </div>
  );
}

function DecisionChip({ decision }: { decision: string }) {
  const colorMap: Record<string, string> = {
    KEEP: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    REVISE: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
    REJECT: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  };
  return (
    <span
      className={cn(
        "rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        colorMap[decision] ?? "bg-secondary text-secondary-foreground"
      )}
    >
      {decision}
    </span>
  );
}
