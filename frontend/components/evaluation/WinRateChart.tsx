"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from "recharts";

const COLORS = {
  system: "#378ADD",
  baseline: "#D85A30",
  tie: "#888780",
} as const;

interface WinRateChartProps {
  data: {
    gap_id: string;
    system_wins: number;
    baseline_wins: number;
    ties: number;
  }[];
}

export function WinRateChart({ data }: WinRateChartProps) {
  return (
    <div className="w-full">
      <h4 className="mb-3 text-sm font-semibold text-foreground">Win Rates by Gap</h4>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart
          data={data}
          margin={{ top: 5, right: 15, left: 0, bottom: 40 }}
          barGap={2}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="gap_id"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            angle={-35}
            textAnchor="end"
            interval={0}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 6,
              fontSize: 12,
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
            formatter={(value) =>
              value === "system_wins"
                ? "System"
                : value === "baseline_wins"
                ? "Baseline"
                : "Tie"
            }
          />
          <Bar dataKey="system_wins" fill={COLORS.system} radius={[3, 3, 0, 0]} name="system_wins" />
          <Bar dataKey="baseline_wins" fill={COLORS.baseline} radius={[3, 3, 0, 0]} name="baseline_wins" />
          <Bar dataKey="ties" fill={COLORS.tie} radius={[3, 3, 0, 0]} name="ties" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
