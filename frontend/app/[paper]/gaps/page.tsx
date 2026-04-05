"use client";

import { use, useReducer } from "react";
import { useApp } from "@/contexts/AppContext";
import { useFinalReport } from "@/lib/hooks";
import { DemoMode } from "@/components/demo/DemoMode";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { DownloadButton } from "@/components/shared/DownloadButton";
import { RunPipelinePrompt } from "@/components/shared/RunPipelinePrompt";
import { GapsViewer } from "@/components/viewers/GapsViewer";
import { getDownloadUrl } from "@/lib/api";

export default function GapsPage({ params }: { params: Promise<{ paper: string }> }) {
  const { paper } = use(params);
  const { demoMode } = useApp();
  const [refreshKey, refresh] = useReducer((x: number) => x + 1, 0);
  const { data, loading, error } = useFinalReport(paper, demoMode, refreshKey);

  const isNotGenerated = !loading && !data && !!error;

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6">
      <DemoMode />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Research Gaps</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Actionable research gaps and opportunities identified
          </p>
        </div>
        {data && !demoMode && (
          <DownloadButton
            label="Download JSON"
            href={getDownloadUrl(paper, "gaps")}
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
      {data && <GapsViewer gaps={data.gaps} />}
    </div>
  );
}
