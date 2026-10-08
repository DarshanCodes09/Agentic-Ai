import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { EmptyState } from "../ui/State";

export function ChartShell({ children, empty }: { children: React.ReactNode; empty: boolean }) {
  if (empty) return <EmptyState title="No chart data yet." body="Data will appear after assessments are evaluated." />;
  return <div className="h-72 w-full">{children}</div>;
}

export function TrendChart({ data }: { data: { assignment_title: string; percentage: number }[] }) {
  return (
    <ChartShell empty={data.length === 0}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 16, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="#e8e3dc" vertical={false} />
          <XAxis dataKey="assignment_title" tick={{ fontSize: 12, fill: "#6f6a62" }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: "#6f6a62" }} />
          <Tooltip />
          <Line type="monotone" dataKey="percentage" stroke="#171717" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

export function BarMetricChart({
  data,
  nameKey,
  valueKey,
  max = 100
}: {
  data: object[];
  nameKey: string;
  valueKey: string;
  max?: number;
}) {
  return (
    <ChartShell empty={data.length === 0}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 16, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="#e8e3dc" vertical={false} />
          <XAxis dataKey={nameKey} tick={{ fontSize: 12, fill: "#6f6a62" }} />
          <YAxis domain={[0, max]} tick={{ fontSize: 12, fill: "#6f6a62" }} />
          <Tooltip />
          <Bar dataKey={valueKey} fill="#171717" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}
