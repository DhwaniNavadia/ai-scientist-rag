"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FlaskConical, FileText, ArrowRight } from "lucide-react";
import { useApp } from "@/contexts/AppContext";
import { listPapers } from "@/lib/api";
import { UploadPanel } from "@/components/upload/UploadPanel";
import { DemoMode } from "@/components/demo/DemoMode";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";

export default function HomePage() {
  const router = useRouter();
  const { papers, setPapers, setCurrentPaper, demoMode } = useApp();
  const [loading, setLoading] = useState(!demoMode);

  useEffect(() => {
    if (demoMode) {
      setLoading(false);
      return;
    }
    listPapers()
      .then((ids) => setPapers(ids))
      .catch(() => {/* silently ignore if backend not running */})
      .finally(() => setLoading(false));
  }, [demoMode, setPapers]);

  function selectPaper(id: string) {
    setCurrentPaper(id);
    router.push(`/${id}/sections`);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <DemoMode />

      {/* Hero */}
      <div className="rounded-2xl border border-border bg-card p-8 text-center space-y-3">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
          <FlaskConical className="h-7 w-7 text-primary" />
        </div>
        <h1 className="text-2xl font-bold text-foreground">Autonomous AI Scientist</h1>
        <p className="text-muted-foreground text-sm max-w-md mx-auto">
          Upload research papers to automatically extract claims, identify research gaps,
          generate competing hypotheses, and evaluate them — all fully automated.
          Upload multiple papers for cross-paper analysis.
        </p>
      </div>

      {/* Upload */}
      {!demoMode && (
        <div className="rounded-xl border border-border bg-card p-6 space-y-4">
          <h2 className="text-base font-semibold text-foreground">Upload Papers</h2>
          <UploadPanel />
        </div>
      )}

      {/* Paper list */}
      <div className="rounded-xl border border-border bg-card p-6 space-y-4">
        <h2 className="text-base font-semibold text-foreground">
          {demoMode ? "Demo Papers" : "Available Papers"}
        </h2>
        {loading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner size="lg" />
          </div>
        ) : papers.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-6">
            {demoMode
              ? "No demo papers found."
              : "No papers yet. Upload a PDF to get started."}
          </p>
        ) : (
          <ul className="space-y-2">
            {papers.map((id) => (
              <li key={id}>
                <button
                  onClick={() => selectPaper(id)}
                  className="flex w-full items-center gap-3 rounded-lg border border-border bg-background px-4 py-3 text-left transition-colors hover:bg-accent"
                >
                  <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="flex-1 text-sm font-medium text-foreground">{id}</span>
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
