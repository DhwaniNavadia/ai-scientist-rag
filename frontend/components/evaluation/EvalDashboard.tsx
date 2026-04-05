"use client";

import { EvaluationReport, PerGapEvalResult } from "@/lib/types";
import { WinRateChart } from "./WinRateChart";
import { ScoreChart } from "./ScoreChart";
import { DecisionPieChart } from "./DecisionPieChart";
import { ResultsExplorer } from "./ResultsExplorer";

interface EvalDashboardProps {
  report: EvaluationReport;
}

export function EvalDashboard({ report }: EvalDashboardProps) {
  const m = report.metrics;

  // Helper to read fields from both naming conventions (types.ts vs extended backend shape)
  type AnyResult = PerGapEvalResult & Record<string, unknown>;
  const asAny = (r: PerGapEvalResult): AnyResult => r as AnyResult;

  const winRateData = report.per_gap_results.map((r) => ({
    gap_id: r.gap_id,
    system_wins: r.system_wins ?? 0,
    baseline_wins: r.baseline_wins ?? 0,
    ties: r.ties ?? 0,
  }));

  const scoreData = report.per_gap_results.map((r) => ({
    gap_id: r.gap_id,
    system_score: (asAny(r)["system_score"] as number | undefined) ?? r.avg_system_score ?? 0,
    baseline_score: (asAny(r)["baseline_score"] as number | undefined) ?? r.avg_baseline_score ?? 0,
  }));

  function decisionOf(r: PerGapEvalResult): string | undefined {
    return asAny(r)["decision"] as string | undefined;
  }

  const keep = report.per_gap_results.filter((r) => decisionOf(r) === "KEEP").length;
  const revise = report.per_gap_results.filter((r) => decisionOf(r) === "REVISE").length;
  const reject = report.per_gap_results.filter((r) => decisionOf(r) === "REJECT").length;

  return (
    <div className="space-y-8">
      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiCard
          label="Win Rate"
          value={`${(m.win_rate * 100).toFixed(1)}%`}
          sub="system vs baseline"
        />
        <KpiCard
          label="Avg Score"
          value={m.avg_hypothesis_score.toFixed(2)}
          sub="out of 10"
        />
        <KpiCard
          label="Keep Rate"
          value={`${(m.keep_rate * 100).toFixed(1)}%`}
          sub="hypotheses kept"
        />
        <KpiCard
          label="Agreement"
          value={`${(m.agent_agreement_rate * 100).toFixed(1)}%`}
          sub="agent agreement"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 rounded-xl border border-border bg-card p-5">
          {winRateData.length > 0 ? (
            <WinRateChart data={winRateData} />
          ) : (
            <ScoreChart data={scoreData} />
          )}
        </div>
        <div className="rounded-xl border border-border bg-card p-5">
          <DecisionPieChart keep={keep} revise={revise} reject={reject} />
        </div>
      </div>

      {/* Score chart if we also showed win rate above */}
      {winRateData.length > 0 && scoreData.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-5">
          <ScoreChart data={scoreData} />
        </div>
      )}

      {/* Summary */}
      {report.summary && (
        <div className="rounded-xl border border-border bg-card p-5 space-y-3">
          <h4 className="text-sm font-semibold text-foreground">Summary</h4>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {report.summary.conclusion}
          </p>
          {report.summary.strengths?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-green-600 dark:text-green-400 mb-1">
                Strengths
              </p>
              <ul className="space-y-0.5">
                {report.summary.strengths.map((s, i) => (
                  <li key={i} className="text-sm text-foreground flex gap-2">
                    <span className="text-green-500 mt-0.5">✓</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {report.summary.weaknesses?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-red-500 dark:text-red-400 mb-1">
                Weaknesses
              </p>
              <ul className="space-y-0.5">
                {report.summary.weaknesses.map((w, i) => (
                  <li key={i} className="text-sm text-foreground flex gap-2">
                    <span className="text-red-400 mt-0.5">✗</span>
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Per-gap table */}
      <ResultsExplorer results={report.per_gap_results} />
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-bold text-foreground">{value}</p>
      <p className="text-xs text-muted-foreground">{sub}</p>
    </div>
  );
}
