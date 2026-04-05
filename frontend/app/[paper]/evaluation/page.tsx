"use client";

import { use, useReducer } from "react";
import { useApp } from "@/contexts/AppContext";
import { useEvalReport } from "@/lib/hooks";
import { DemoMode } from "@/components/demo/DemoMode";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { DownloadButton } from "@/components/shared/DownloadButton";
import { RunPipelinePrompt } from "@/components/shared/RunPipelinePrompt";
import { EvalDashboard } from "@/components/evaluation/EvalDashboard";
import { getDownloadUrl } from "@/lib/api";

export default function EvaluationPage({ params }: { params: Promise<{ paper: string }> }) {
  const { paper } = use(params);
  const { demoMode } = useApp();
  const [refreshKey, refresh] = useReducer((x: number) => x + 1, 0);
  const { data, loading, error } = useEvalReport(paper, demoMode, refreshKey);

  const isNotGenerated = !loading && !data && !!error;

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-6">
      <DemoMode />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Evaluation Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Win-rate, scores, and decision breakdown for generated hypotheses
          </p>
        </div>
        {data && !demoMode && (
          <DownloadButton
            label="Download Report"
            href={getDownloadUrl(paper, "evaluation")}
          />
        )}
      </div>

      {loading && (
        <div className="flex justify-center py-16">
          <LoadingSpinner size="lg" />
        </div>
      )}
      {isNotGenerated && !demoMode ? (
        <RunPipelinePrompt paperId={paper} onComplete={refresh} />
      ) : (
        error && <ErrorBanner message={error} />
      )}
      {data && <EvalDashboard report={data} />}
    </div>
  );
}
