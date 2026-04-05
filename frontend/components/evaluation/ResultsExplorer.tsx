"use client";

import { useState } from "react";
import { PerGapEvalResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronRight } from "lucide-react";

interface ResultsExplorerProps {
  results: PerGapEvalResult[];
}

const decisionColor: Record<string, string> = {
  KEEP: "text-green-600 dark:text-green-400",
  REVISE: "text-yellow-600 dark:text-yellow-400",
  REJECT: "text-red-500 dark:text-red-400",
};

export function ResultsExplorer({ results }: ResultsExplorerProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Accept both shapes: types.ts uses majority_winner/avg_system_score, some responses use winner/system_score
  function winner(r: PerGapEvalResult) {
    return (r as unknown as Record<string, string>)["winner"] ?? r.majority_winner;
  }
  function sysScore(r: PerGapEvalResult) {
    return (r as unknown as Record<string, number>)["system_score"] ?? r.avg_system_score;
  }
  function baseScore(r: PerGapEvalResult) {
    return (r as unknown as Record<string, number>)["baseline_score"] ?? r.avg_baseline_score;
  }
  function decision(r: PerGapEvalResult) {
    return (r as unknown as Record<string, string>)["decision"];
  }
  function rationale(r: PerGapEvalResult) {
    return (r as unknown as Record<string, string>)["rationale"];
  }

  if (results.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-8">
        No per-gap results available.
      </p>
    );
  }

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground mb-3">
        Per-Gap Evaluation Results
      </p>
      <div className="overflow-hidden rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Gap</th>
              <th className="px-4 py-2.5 text-center text-xs font-semibold text-muted-foreground">Winner</th>
              <th className="px-4 py-2.5 text-center text-xs font-semibold text-muted-foreground">System</th>
              <th className="px-4 py-2.5 text-center text-xs font-semibold text-muted-foreground">Baseline</th>
              <th className="px-4 py-2.5 text-center text-xs font-semibold text-muted-foreground">Decision</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {results.map((r) => {
              const isOpen = expanded.has(r.gap_id);
              return (
                <>
                  <tr
                    key={r.gap_id}
                    onClick={() => toggle(r.gap_id)}
                    className="cursor-pointer hover:bg-muted/30 transition-colors"
                  >
                    <td className="px-4 py-2.5 font-mono text-xs font-medium text-primary">
                      {r.gap_id}
                    </td>
                    <td className="px-4 py-2.5 text-center text-xs font-medium text-foreground">
                      {winner(r) ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-center text-xs font-mono text-foreground">
                      {sysScore(r)?.toFixed(2) ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-center text-xs font-mono text-foreground">
                      {baseScore(r)?.toFixed(2) ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span className={cn("text-xs font-semibold", decisionColor[decision(r) ?? ""] ?? "text-foreground")}>
                        {decision(r) ?? "—"}
                      </span>
                    </td>
                    <td className="pr-3 text-center text-muted-foreground">
                      {isOpen ? (
                        <ChevronDown className="h-3.5 w-3.5 mx-auto" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 mx-auto" />
                      )}
                    </td>
                  </tr>
                  {isOpen && rationale(r) && (
                    <tr key={`${r.gap_id}-detail`} className="bg-muted/20">
                      <td colSpan={6} className="px-5 py-3">
                        <p className="text-xs text-muted-foreground leading-relaxed italic">
                          {rationale(r)}
                        </p>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
