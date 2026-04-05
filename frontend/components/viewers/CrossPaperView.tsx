"use client";

import { Layers } from "lucide-react";

interface CrossPaperViewProps {
  data?: {
    cross_claims?: Array<{ source?: string; claim?: string; [key: string]: unknown }>;
    contradictions?: unknown[];
  };
}

export function CrossPaperView({ data }: CrossPaperViewProps) {
  const crossClaims = data?.cross_claims ?? [];
  const contradictions = data?.contradictions ?? [];

  if (crossClaims.length === 0 && contradictions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <Layers className="mb-3 h-10 w-10 opacity-40" />
        <p className="text-sm font-medium">No cross-paper analysis available.</p>
        <p className="mt-1 text-xs text-center max-w-xs">
          Upload and run multiple papers to see cross-paper claim comparisons and contradictions.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {contradictions.length > 0 && (
        <Section title="Contradictions" count={contradictions.length} variant="danger">
          {(contradictions as Array<Record<string, unknown>>).map((item, i) => (
            <div
              key={i}
              className="rounded-lg border border-red-200 bg-red-50/50 p-4 dark:border-red-900 dark:bg-red-950/20"
            >
              <pre className="text-xs text-foreground whitespace-pre-wrap">
                {JSON.stringify(item, null, 2)}
              </pre>
            </div>
          ))}
        </Section>
      )}

      {crossClaims.length > 0 && (
        <Section title="Cross-Paper Claims" count={crossClaims.length} variant="default">
          {crossClaims.map((item, i) => (
            <div key={i} className="rounded-lg border border-border bg-card p-4 space-y-1">
              {item.source && (
                <span className="inline-block rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                  {item.source}
                </span>
              )}
              <p className="text-sm text-foreground">
                {typeof item.claim === "string" ? item.claim : JSON.stringify(item, null, 2)}
              </p>
            </div>
          ))}
        </Section>
      )}
    </div>
  );
}

function Section({
  title,
  count,
  variant,
  children,
}: {
  title: string;
  count: number;
  variant: "default" | "danger";
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="font-semibold text-sm text-foreground">{title}</h3>
        <span
          className={
            variant === "danger"
              ? "rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400"
              : "rounded-full bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground"
          }
        >
          {count}
        </span>
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}
