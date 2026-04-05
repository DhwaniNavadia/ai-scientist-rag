"use client";

import { use, useEffect, useReducer, useState } from "react";
import { useApp } from "@/contexts/AppContext";
import { DemoMode } from "@/components/demo/DemoMode";
import { CrossPaperView } from "@/components/viewers/CrossPaperView";
import { getCrossPaperData } from "@/lib/api";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { RunPipelinePrompt } from "@/components/shared/RunPipelinePrompt";

export default function CrossPaperPage({ params }: { params: Promise<{ paper: string }> }) {
  const { paper } = use(params);
  const { demoMode } = useApp();
  const [data, setData] = useState<{ cross_claims: unknown[]; contradictions: unknown[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, refresh] = useReducer((x: number) => x + 1, 0);

  useEffect(() => {
    if (demoMode) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    getCrossPaperData(paper)
      .then(setData)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [paper, demoMode, refreshKey]);

  const isNotGenerated = !loading && !data && !!error;

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6">
      <DemoMode />

      <div>
        <h1 className="text-xl font-bold text-foreground">Cross-Paper Analysis</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Comparative claims and contradictions across multiple papers
        </p>
      </div>

      {loading && <LoadingSpinner />}
      {isNotGenerated && !demoMode ? (
        <RunPipelinePrompt paperId={paper} onComplete={refresh} />
      ) : (
        error && <ErrorBanner message={error} />
      )}
      {!loading && !error && (
        <CrossPaperView data={data ?? undefined} />
      )}
    </div>
  );
}
