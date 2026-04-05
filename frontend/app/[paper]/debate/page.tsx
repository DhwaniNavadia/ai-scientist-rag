"use client";

import { use, useReducer } from "react";
import { useApp } from "@/contexts/AppContext";
import { useFinalReport } from "@/lib/hooks";
import { DemoMode } from "@/components/demo/DemoMode";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { RunPipelinePrompt } from "@/components/shared/RunPipelinePrompt";
import { DebateView } from "@/components/viewers/DebateView";

export default function DebatePage({ params }: { params: Promise<{ paper: string }> }) {
  const { paper } = use(params);
  const { demoMode } = useApp();
  const [refreshKey, refresh] = useReducer((x: number) => x + 1, 0);
  const { data, loading, error } = useFinalReport(paper, demoMode, refreshKey);

  const isNotGenerated = !loading && !data && !!error;

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6">
      <DemoMode />

      <div>
        <h1 className="text-xl font-bold text-foreground">Agent Debate</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Side-by-side view of AgentA vs AgentB hypothesis proposals
        </p>
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
      {data && <DebateView pairs={data.hypothesis_pairs} />}
    </div>
  );
}
