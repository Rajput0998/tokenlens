import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { Brain } from "lucide-react";
import { InfoTooltip } from "../home/InfoTooltip";

interface RawModelData {
  model: string;
  total_tokens?: number;
  totalTokens?: number;
  tokens?: number;
  total_cost?: number;
  totalCost?: number;
  event_count?: number;
  eventCount?: number;
}

interface ChartData {
  model: string;
  tokens: number;
  cost: number;
  events: number;
  percentage: number;
}

interface ModelUsagePieChartProps {
  data: RawModelData[];
  loading?: boolean;
}

const COLORS = ["#3b82f6", "#8b5cf6", "#22c55e", "#f97316", "#ef4444", "#06b6d4", "#ec4899", "#14b8a6"];

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function normalize(data: RawModelData[]): ChartData[] {
  const items = data.map((d) => ({
    model: d.model ?? "unknown",
    tokens: d.total_tokens ?? d.totalTokens ?? d.tokens ?? 0,
    cost: d.total_cost ?? d.totalCost ?? 0,
    events: d.event_count ?? d.eventCount ?? 0,
    percentage: 0,
  }));

  const total = items.reduce((s, i) => s + i.tokens, 0);
  for (const item of items) {
    item.percentage = total > 0 ? Math.round((item.tokens / total) * 100) : 0;
  }

  return items.sort((a, b) => b.tokens - a.tokens);
}

function shortenModelName(name: string): string {
  return name
    .replace("claude-", "")
    .replace("-20250514", "")
    .replace("-20250415", "")
    .replace("kiro-auto", "Kiro");
}

export function ModelUsagePieChart({ data, loading }: ModelUsagePieChartProps) {
  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-4 animate-pulse">
        <div className="h-4 w-32 bg-muted rounded mb-4" />
        <div className="h-48 w-48 bg-muted rounded-full mx-auto" />
      </div>
    );
  }

  const chartData = normalize(data);

  if (chartData.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-6 text-center">
        <Brain className="h-8 w-8 mx-auto text-muted-foreground/20 mb-2" />
        <p className="text-sm font-medium text-muted-foreground">No model usage data</p>
        <p className="text-xs text-muted-foreground/70 mt-1">Model breakdown appears after using AI tools.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">Model Usage</h3>
          <InfoTooltip
            title="Model Usage"
            description="Shows which AI models you're using and how many tokens each consumes. Larger slices mean more usage. Different models have different pricing — Opus is most expensive, Haiku is cheapest."
            tips={[
              "Opus ($15/M input) — best for complex reasoning, most expensive",
              "Sonnet ($3/M input) — balanced quality and cost",
              "Haiku ($0.80/M input) — fastest and cheapest for simple tasks",
              "Switch to cheaper models for formatting, renaming, and simple edits",
            ]}
          />
        </div>
        <p className="text-xs text-muted-foreground">Token distribution by AI model</p>
      </div>

      <div className="flex items-center gap-4">
        {/* Pie chart */}
        <div className="w-40 h-40 flex-shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={65}
                dataKey="tokens"
                nameKey="model"
                stroke="hsl(var(--card))"
                strokeWidth={2}
              >
                {chartData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "0.5rem",
                  fontSize: "12px",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                }}
                formatter={(value: unknown) => [`${formatTokens(Number(value))} tokens`, ""]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Legend with details */}
        <div className="flex-1 space-y-2">
          {chartData.map((item, i) => (
            <div key={item.model} className="flex items-center gap-2">
              <div
                className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                style={{ backgroundColor: COLORS[i % COLORS.length] }}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium truncate">
                    {shortenModelName(item.model)}
                  </span>
                  <span className="text-xs font-bold tabular-nums ml-2">{item.percentage}%</span>
                </div>
                <div className="flex gap-3 text-[10px] text-muted-foreground tabular-nums">
                  <span>{formatTokens(item.tokens)}</span>
                  <span>${item.cost.toFixed(4)}</span>
                  <span>{item.events} events</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
