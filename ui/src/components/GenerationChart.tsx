import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHART_COLORS } from "../colors";
import type { PeriodPoint } from "../types";

interface Props {
  data: PeriodPoint[];
}

export function GenerationChart({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e1e2e" />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 10, fill: "#888" }}
          interval={5}
          stroke="#333"
        />
        <YAxis
          tick={{ fontSize: 10, fill: "#888" }}
          stroke="#333"
          label={{
            value: "MW",
            angle: -90,
            position: "insideLeft",
            fill: "#666",
            fontSize: 10,
          }}
        />
        <Tooltip
          contentStyle={{
            background: "#111118",
            border: "1px solid #1e1e2e",
            borderRadius: 4,
            fontSize: 11,
            color: "#e0e0e0",
          }}
          formatter={(value: number, name: string) => [
            `${value.toFixed(1)} MW`,
            name,
          ]}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, color: "#aaa" }}
          formatter={(value) =>
            value.charAt(0).toUpperCase() + value.slice(1)
          }
        />
        <ReferenceLine y={0} stroke="#444" />
        <Line
          type="monotone"
          dataKey="actual"
          stroke={CHART_COLORS.actual}
          dot={false}
          strokeWidth={2}
          name="actual"
        />
        <Line
          type="monotone"
          dataKey="estimated"
          stroke={CHART_COLORS.estimated}
          dot={false}
          strokeWidth={2}
          name="estimated"
          strokeDasharray="6 3"
        />
        <Line
          type="monotone"
          dataKey="residual"
          stroke={CHART_COLORS.residual}
          dot={false}
          strokeWidth={1.5}
          name="residual"
          strokeDasharray="2 2"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
