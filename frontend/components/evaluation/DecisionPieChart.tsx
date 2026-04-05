"use client";

import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
} from "recharts";

const DECISION_COLORS: Record<string, string> = {
  KEEP: "#639922",
  REVISE: "#BA7517",
  REJECT: "#E24B4A",
};

interface DecisionPieChartProps {
  keep: number;
  revise: number;
  reject: number;
}

export function DecisionPieChart({ keep, revise, reject }: DecisionPieChartProps) {
  const total = keep + revise + reject;
  const data = [
    { name: "KEEP", value: keep },
    { name: "REVISE", value: revise },
    { name: "REJECT", value: reject },
  ].filter((d) => d.value > 0);

  return (
    <div className="w-full">
      <h4 className="mb-3 text-sm font-semibold text-foreground">Decision Distribution</h4>
      {total === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-8">No data</p>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={55}
              outerRadius={85}
              paddingAngle={3}
              dataKey="value"
              label={({ name, percent }) =>
                percent > 0.05 ? `${(percent * 100).toFixed(0)}%` : ""
              }
              labelLine={false}
            >
              {data.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={DECISION_COLORS[entry.name] ?? "#ccc"}
                />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number, name: string) => [`${value} (${((value / total) * 100).toFixed(1)}%)`, name]}
              contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
                borderRadius: 6,
                fontSize: 12,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
