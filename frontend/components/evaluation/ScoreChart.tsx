"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from "recharts";

interface ScoreChartProps {
  data: {
    gap_id: string;
    system_score: number;
    baseline_score: number;
  }[];
}

export function ScoreChart({ data }: ScoreChartProps) {
  return (
    <div className="w-full">
      <h4 className="mb-3 text-sm font-semibold text-foreground">
        Hypothesis Scores by Gap
      </h4>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart
          data={data}
          margin={{ top: 5, right: 15, left: 0, bottom: 40 }}
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
            domain={[0, 10]}
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 6,
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          <ReferenceLine y={5} stroke="hsl(var(--muted-foreground))" strokeDasharray="4 2" />
          <Line
            type="monotone"
            dataKey="system_score"
            stroke="#378ADD"
            strokeWidth={2}
            dot={{ r: 4 }}
            name="System"
          />
          <Line
            type="monotone"
            dataKey="baseline_score"
            stroke="#D85A30"
            strokeWidth={2}
            dot={{ r: 4 }}
            name="Baseline"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
