import { useTokenStore } from "@/stores/useTokenStore";
import type { PerToolUsage } from "@/stores/useTokenStore";
import { AreaChart, Area, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { Cpu, TrendingUp, Clock, DollarSign } from "lucide-react";
import { InfoTooltip } from "./InfoTooltip";

interface ToolStatusCardsProps {
  loading?: boolean;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function ToolCard({ tool }: { tool: PerToolUsage }) {
  // Use real hourly data if available, otherwise show empty state
  const hasHourlyData = tool.hourly && tool.hourly.length > 0;
  const currentHour = new Date().getHours();

  // Backend sends hourly buckets in UTC hours (0-23).
  // Convert to local hours before filtering and display.
  const tzOffsetHours = -(new Date().getTimezoneOffset()) / 60;

  // Build chart data: convert UTC hour → local, filter up to current local hour
  const chartData = hasHourlyData
    ? tool.hourly
        .map((h) => ({
          hour: (h.hour + tzOffsetHours + 24) % 24,
          tokens: h.tokens,
        }))
        .filter((h) => h.hour <= currentHour)
        .sort((a, b) => a.hour - b.hour)
        .map((h) => ({
          hour: `${h.hour}:00`,
          tokens: h.tokens,
        }))
    : [];

  // Calculate peak hour in local time
  const peakHour = hasHourlyData
    ? tool.hourly
        .map((h) => ({
          hour: (h.hour + tzOffsetHours + 24) % 24,
          tokens: h.tokens,
        }))
        .reduce((max, h) => (h.tokens > max.tokens ? h : max), { hour: 0, tokens: 0 })
    : null;

  // Calculate average tokens per active hour
  const activeHours = chartData.filter((h) => h.tokens > 0).length;
  const avgPerHour = activeHours > 0 ? Math.round(tool.totalTokens / activeHours) : 0;

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-primary/10">
            <Cpu className="h-4 w-4 text-primary" />
          </div>
          <span className="font-semibold text-sm capitalize">{tool.tool.replace("_", " ")}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <InfoTooltip
            title={`${tool.tool.replace("_", " ")} Usage`}
            description="Token consumption for this AI tool today. The chart shows hourly usage patterns — hover over it to see exact tokens per hour. Stats below show cost, average rate, and your peak usage hour."
            tips={[
              "The sparkline shows real hourly data from your sessions",
              "Peak hour helps you understand when you code most intensively",
              "Cost is calculated using the model's per-token pricing",
            ]}
          />
          <span
            className={`h-2.5 w-2.5 rounded-full ring-2 ring-offset-1 ring-offset-card ${
              tool.active ? "bg-green-500 ring-green-500/30" : "bg-muted-foreground/30 ring-muted/30"
            }`}
          />
        </div>
      </div>

      {/* Main stat */}
      <div>
        <p className="text-3xl font-bold tabular-nums tracking-tight">
          {formatTokens(tool.totalTokens)}
        </p>
        <p className="text-xs text-muted-foreground">tokens today</p>
      </div>

      {/* Sparkline chart */}
      <div className="h-16 -mx-1">
        {chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 2, right: 2, left: 2, bottom: 0 }}>
              <defs>
                <linearGradient id={`gradient-${tool.tool}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <XAxis dataKey="hour" hide />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "0.375rem",
                  fontSize: "11px",
                  padding: "4px 8px",
                }}
                formatter={(value: unknown) => [`${formatTokens(Number(value))} tokens`, ""]}
                labelFormatter={(label) => `${label}`}
              />
              <Area
                type="monotone"
                dataKey="tokens"
                stroke="hsl(var(--primary))"
                strokeWidth={1.5}
                fill={`url(#gradient-${tool.tool})`}
                dot={false}
                activeDot={{ r: 3, strokeWidth: 0, fill: "hsl(var(--primary))" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center">
            <p className="text-xs text-muted-foreground/50">Hourly data available after more usage</p>
          </div>
        )}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-2 pt-1 border-t">
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 text-muted-foreground">
            <DollarSign className="h-3 w-3" />
          </div>
          <p className="text-xs font-medium tabular-nums">${tool.cost.toFixed(4)}</p>
          <p className="text-[10px] text-muted-foreground">cost</p>
        </div>
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 text-muted-foreground">
            <TrendingUp className="h-3 w-3" />
          </div>
          <p className="text-xs font-medium tabular-nums">{formatTokens(avgPerHour)}</p>
          <p className="text-[10px] text-muted-foreground">avg/hr</p>
        </div>
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 text-muted-foreground">
            <Clock className="h-3 w-3" />
          </div>
          <p className="text-xs font-medium tabular-nums">
            {peakHour && peakHour.tokens > 0 ? `${peakHour.hour}:00` : "—"}
          </p>
          <p className="text-[10px] text-muted-foreground">peak</p>
        </div>
      </div>
    </div>
  );
}

export function ToolStatusCards({ loading }: ToolStatusCardsProps) {
  const perTool = useTokenStore((s) => s.perTool);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[1, 2].map((i) => (
          <div key={i} className="rounded-lg border bg-card p-4 animate-pulse">
            <div className="h-4 w-24 bg-muted rounded mb-2" />
            <div className="h-8 w-16 bg-muted rounded mb-2" />
            <div className="h-16 w-full bg-muted rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (perTool.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-6 text-center">
        <Cpu className="h-8 w-8 mx-auto text-muted-foreground/30 mb-2" />
        <p className="text-sm font-medium text-muted-foreground">No tool data yet</p>
        <p className="text-xs text-muted-foreground/70 mt-1">
          Start using Claude Code or Kiro to see usage here.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {perTool.map((tool) => (
        <ToolCard key={tool.tool} tool={tool} />
      ))}
    </div>
  );
}
