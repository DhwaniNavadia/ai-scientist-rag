"use client";

import { useEffect, useState } from "react";
import { getFinalReport, getEvaluationReport } from "@/lib/api";
import { demoFinalReports, demoEvalReports } from "@/lib/demo-data";
import type { FinalReport, EvaluationReport } from "@/lib/types";

export function useFinalReport(paperId: string | null, demoMode: boolean, refreshKey?: number) {
  const [data, setData] = useState<FinalReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!paperId) {
      setLoading(false);
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);

    if (demoMode) {
      const demo = demoFinalReports[paperId] ?? null;
      setData(demo);
      if (!demo) setError(`No demo data for paper: ${paperId}`);
      setLoading(false);
      return;
    }

    getFinalReport(paperId)
      .then(setData)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [paperId, demoMode, refreshKey]);

  return { data, loading, error };
}

export function useEvalReport(paperId: string | null, demoMode: boolean, refreshKey?: number) {
  const [data, setData] = useState<EvaluationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!paperId) {
      setLoading(false);
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);

    if (demoMode) {
      const demo = demoEvalReports[paperId] ?? null;
      setData(demo);
      if (!demo) setError(`No demo evaluation data for paper: ${paperId}`);
      setLoading(false);
      return;
    }

    getEvaluationReport(paperId)
      .then(setData)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [paperId, demoMode, refreshKey]);

  return { data, loading, error };
}
