import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Layers } from "lucide-react";
import { InfoTooltip } from "../home/InfoTooltip";

interface RawToolData {
  tool: string;
  total_tokens?: number;
  totalTokens?: number;
  total_cost?: number;
  totalCost?: number;
  session_count?: number;
  sessionCount?: number;
}

interface ChartData {
  tool: string;
  tokens: number;
  cost: number;
  sessions: number;
}

interface ToolComparisonBarChartProps {
  data: RawToolData[];
  loading?: boolean;
}

const TOOL_COLORS: Record<string, string> = {
  kiro: "#3b82f6",
  claude_code: "#8b5cf6",
};

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function normalize(data: RawToolData[]): ChartData[] {
  return data.map((d) => ({
    tool: (d.tool ?? "unknown").replace("_", " "),
    tokens: d.total_tokens ?? d.totalTokens ?? 0,
    cost: d.total_cost ?? d.totalCost ?? 0,
    sessions: d.session_count ?? d.sessionCount ?? 0,
  }));
}

export function ToolComparisonBarChart({ data, loading }: ToolComparisonBarChartProps) {
  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-4 animate-pulse">
        <div className="h-4 w-32 bg-muted rounded mb-4" />
        <div className="h-48 bg-muted rounded" />
      </div>
    );
  }

  const chartData = normalize(data);

  if (chartData.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-6 text-center">
        <Layers className="h-8 w-8 mx-auto text-muted-foreground/20 mb-2" />
        <p className="text-sm font-medium text-muted-foreground">No tool comparison data</p>
        <p className="text-xs text-muted-foreground/70 mt-1">Use multiple AI tools to compare usage.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">Tool Comparison</h3>
            <InfoTooltip
              title="Tool Comparison"
              description="Compares token consumption across your AI tools (Kiro, Claude Code, etc.). Taller bars mean more tokens used. The stats below show cost and session count per tool."
              tips={[
                "Compare which tool consumes more tokens for similar tasks",
                "Higher cost doesn't always mean less efficient — check output quality",
                "Session count shows how often you use each tool",
              ]}
            />
          </div>
          <p className="text-xs text-muted-foreground">Tokens consumed per tool</p>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted/50" vertical={false} />
          <XAxis
            dataKey="tool"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            tickFormatter={(v: number) => formatTokens(v)}
            tickLine={false}
            axisLine={false}
            width={45}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "0.5rem",
              fontSize: "12px",
              boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
            }}
            formatter={(value: unknown, name: unknown) => {
              const n = String(name);
              if (n === "tokens") return [`${formatTokens(Number(value))}`, "Tokens"];
              if (n === "cost") return [`$${Number(value).toFixed(4)}`, "Cost"];
              return [String(value), n];
            }}
          />
          <Bar dataKey="tokens" name="tokens" radius={[6, 6, 0, 0]} maxBarSize={60}>
            {chartData.map((entry) => (
              <Cell
                key={entry.tool}
                fill={TOOL_COLORS[entry.tool.replace(" ", "_")] ?? "#3b82f6"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Stats below chart */}
      <div className="grid grid-cols-1 gap-2 mt-3 pt-3 border-t">
        {chartData.map((t) => (
          <div key={t.tool} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <div
                className="w-2.5 h-2.5 rounded-sm"
                style={{ backgroundColor: TOOL_COLORS[t.tool.replace(" ", "_")] ?? "#3b82f6" }}
              />
              <span className="font-medium capitalize">{t.tool}</span>
            </div>
            <div className="flex gap-4 text-muted-foreground tabular-nums">
              <span>{formatTokens(t.tokens)} tokens</span>
              <span>${t.cost.toFixed(4)}</span>
              <span>{t.sessions} sessions</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
