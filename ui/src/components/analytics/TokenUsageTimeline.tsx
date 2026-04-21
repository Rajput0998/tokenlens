import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Brush,
} from "recharts";
import { TrendingUp } from "lucide-react";
import { InfoTooltip } from "../home/InfoTooltip";
import type { TimePeriod } from "./TimePeriodSelector";

interface RawDataPoint {
  timestamp: string;
  tokens: number;
  cost: number;
  tool: string;
  model: string;
}

interface AggregatedPoint {
  time: string;
  rawTime: string;
  tokens: number;
  cost: number;
  cumulative: number;
}

interface TokenUsageTimelineProps {
  data: RawDataPoint[];
  period: TimePeriod;
  loading?: boolean;
  error?: string | null;
}

/** Ensure ISO string is parsed as UTC by appending Z if no timezone is present */
function toUtcDate(iso: string): Date {
  // If the string has no timezone indicator (no Z, no +, no -offset after time part), treat as UTC
  const hasTimezone = /[Z+\-]\d*$/.test(iso.trim()) || iso.endsWith("Z");
  return new Date(hasTimezone ? iso : iso + "Z");
}

function formatTime(iso: string): string {
  try {
    return toUtcDate(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso.slice(11, 16);
  }
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

/** Build a local-hour key like "2026-04-21T11" from a UTC ISO string */
function localHourKey(iso: string): string {
  const d = toUtcDate(iso);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  return `${y}-${m}-${day}T${h}`;
}

/** Aggregate raw events into hourly buckets using local time */
function aggregateByHour(data: RawDataPoint[]): AggregatedPoint[] {
  const buckets = new Map<string, { tokens: number; cost: number; rawTime: string }>();

  for (const d of data) {
    const hourKey = localHourKey(d.timestamp);
    const existing = buckets.get(hourKey);
    if (existing) {
      existing.tokens += d.tokens;
      existing.cost += d.cost;
    } else {
      buckets.set(hourKey, { tokens: d.tokens, cost: d.cost, rawTime: d.timestamp });
    }
  }

  let cumulative = 0;
  return Array.from(buckets.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, val]) => {
      cumulative += val.tokens;
      return {
        time: formatTime(val.rawTime),
        rawTime: key,
        tokens: val.tokens,
        cost: val.cost,
        cumulative,
      };
    });
}

export function TokenUsageTimeline({ data, loading, error, period }: TokenUsageTimelineProps) {
  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-center">
        <p className="text-destructive font-medium">Failed to load timeline</p>
        <p className="text-sm text-muted-foreground mt-1">{error}</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-4 animate-pulse">
        <div className="h-4 w-32 bg-muted rounded mb-4" />
        <div className="h-64 bg-muted rounded" />
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-8 text-center">
        <TrendingUp className="h-10 w-10 mx-auto text-muted-foreground/20 mb-3" />
        <p className="font-medium text-muted-foreground">No usage data for this period</p>
        <p className="text-xs text-muted-foreground/70 mt-1">
          Start using AI tools to see your token consumption timeline.
        </p>
      </div>
    );
  }

  const aggregated = aggregateByHour(data);
  const totalTokens = data.reduce((s, d) => s + d.tokens, 0);
  const totalCost = data.reduce((s, d) => s + d.cost, 0);
  const peakHour = aggregated.reduce((max, p) => (p.tokens > max.tokens ? p : max), aggregated[0]);

  return (
    <div className="rounded-lg border bg-card p-4">
      {/* Header with stats */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">Token Usage Over Time</h3>
            <InfoTooltip
              title="Token Usage Over Time"
              description="Shows how many tokens you consumed each hour. The blue area is hourly usage, the dashed purple line is cumulative total. Hover over the chart to see exact values. Use the brush at the bottom to zoom into a specific time range."
              tips={[
                "Spikes indicate heavy coding sessions or large file context",
                "Flat periods mean no AI tool activity",
                "Cumulative line helps track total daily consumption",
                "Switch between 24h, 7d, 30d to see different time ranges",
              ]}
            />
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
              {period}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Hourly token consumption • hover for details
          </p>
        </div>
        <div className="flex gap-4 text-right">
          <div>
            <p className="text-xs text-muted-foreground">Total</p>
            <p className="text-sm font-bold tabular-nums">{formatTokens(totalTokens)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Cost</p>
            <p className="text-sm font-bold tabular-nums">${totalCost.toFixed(4)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Peak</p>
            <p className="text-sm font-bold tabular-nums">{peakHour.time}</p>
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={aggregated} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id="tokenGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="cumulativeGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.2} />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted/50" />
          <XAxis
            dataKey="time"
            className="text-xs"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            className="text-xs"
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
            formatter={(value: unknown, name: unknown) => [
              `${formatTokens(Number(value))} tokens`,
              String(name) === "tokens" ? "This hour" : "Cumulative",
            ]}
            labelFormatter={(label) => `${label}`}
          />
          <Area
            type="monotone"
            dataKey="cumulative"
            stroke="#8b5cf6"
            strokeWidth={1}
            strokeDasharray="4 4"
            fill="url(#cumulativeGradient)"
            name="cumulative"
            dot={false}
          />
          <Area
            type="monotone"
            dataKey="tokens"
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#tokenGradient)"
            name="tokens"
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0, fill: "#3b82f6" }}
          />
          {aggregated.length > 10 && (
            <Brush
              dataKey="time"
              height={20}
              stroke="hsl(var(--border))"
              fill="hsl(var(--muted))"
              travellerWidth={8}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 mt-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-blue-500 rounded" />
          <span>Hourly tokens</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-purple-500 rounded" style={{ borderStyle: "dashed" }} />
          <span>Cumulative</span>
        </div>
      </div>
    </div>
  );
}
