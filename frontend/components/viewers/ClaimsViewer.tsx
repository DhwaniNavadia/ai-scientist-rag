"use client";

import { useState } from "react";
import { Tag } from "lucide-react";
import { cn } from "@/lib/utils";
import { Claim } from "@/lib/types";

interface ClaimsViewerProps {
  claims: Claim[];
}

export function ClaimsViewer({ claims }: ClaimsViewerProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");

  if (claims.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <Tag className="mb-3 h-10 w-10 opacity-40" />
        <p className="text-sm">No claims extracted yet.</p>
      </div>
    );
  }

  const filtered = claims.filter(
    (c) =>
      !filter ||
      c.claim_text.toLowerCase().includes(filter.toLowerCase()) ||
      c.section?.toLowerCase().includes(filter.toLowerCase())
  );

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-4">
      {/* Search */}
      <input
        type="text"
        placeholder="Filter claims…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
      />

      <p className="text-xs text-muted-foreground">
        {filtered.length} of {claims.length} claims
      </p>

      {/* Claims list */}
      <div className="space-y-3">
        {filtered.map((claim) => {
          const isOpen = expanded.has(claim.claim_id);
          const confidence = typeof claim.confidence === "number" ? claim.confidence : null;
          return (
            <div
              key={claim.claim_id}
              className="rounded-lg border border-border bg-card p-4"
            >
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-mono font-medium text-primary">
                    {claim.claim_id}
                  </span>
                  {claim.section && (
                    <span className="rounded bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground">
                      {claim.section}
                    </span>
                  )}
                </div>
                {confidence !== null && (
                  <span
                    className={cn(
                      "shrink-0 text-xs font-medium",
                      confidence >= 0.8
                        ? "text-green-600 dark:text-green-400"
                        : confidence >= 0.6
                        ? "text-yellow-600 dark:text-yellow-400"
                        : "text-red-500"
                    )}
                  >
                    {(confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>

              <p className="text-sm text-foreground leading-relaxed">{claim.claim_text}</p>

              {claim.evidence_text && (
                <button
                  onClick={() => toggle(claim.claim_id)}
                  className="mt-2 text-xs text-primary hover:underline"
                >
                  {isOpen ? "Hide evidence ▲" : "Show evidence ▼"}
                </button>
              )}
              {isOpen && claim.evidence_text && (
                <p className="mt-2 rounded bg-muted/50 px-3 py-2 text-xs text-muted-foreground leading-relaxed italic">
                  {claim.evidence_text}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
