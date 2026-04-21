import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { TrendingUp } from "lucide-react";
import { InfoTooltip } from "../home/InfoTooltip";
import { formatLocalTime } from "@/lib/dateUtils";

interface RawForecastPoint {
  hour?: string;
  timestamp?: string;
  predicted_tokens?: number;
  predicted?: number;
  lower_80?: number;
  upper_80?: number;
  lowerBound?: number;
  upperBound?: number;
}

interface ChartPoint {
  time: string;
  predicted: number;
  lower: number;
  upper: number;
}

interface ForecastChartProps {
  data: RawForecastPoint[];
  loading?: boolean;
}

function formatTime(iso: string): string {
  return formatLocalTime(iso, iso.slice(11, 16));
}

function formatTokens(n: number): string {
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return Math.round(n).toString();
}

function normalize(data: RawForecastPoint[]): ChartPoint[] {
  return data.map((d) => ({
    time: formatTime(d.hour ?? d.timestamp ?? ""),
    predicted: d.predicted_tokens ?? d.predicted ?? 0,
    lower: d.lower_80 ?? d.lowerBound ?? 0,
    upper: d.upper_80 ?? d.upperBound ?? 0,
  }));
}

export function ForecastChart({ data, loading }: ForecastChartProps) {
  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-4 animate-pulse">
        <div className="h-4 w-32 bg-muted rounded mb-4" />
        <div className="h-48 bg-muted rounded" />
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-8 text-center">
        <TrendingUp className="h-10 w-10 mx-auto text-muted-foreground/20 mb-3" />
        <p className="font-medium text-muted-foreground">Not enough data for forecasting</p>
        <p className="text-xs text-muted-foreground/70 mt-1">
          Continue using tools to build prediction models.
        </p>
      </div>
    );
  }

  const chartData = normalize(data);
  const avgPredicted = chartData.reduce((s, d) => s + d.predicted, 0) / chartData.length;

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">Burn Rate Forecast</h3>
            <InfoTooltip
              title="Burn Rate Forecast"
              description="Predicts your token consumption for the next 24 hours based on recent usage patterns. The blue line is the prediction, the shaded area shows the confidence range (80% probability the actual value falls within)."
              tips={[
                "Wider confidence band = less certain prediction",
                "Flat line = consistent usage pattern detected",
                "Rising line = increasing consumption trend",
                "Predictions improve with more historical data (7+ days for ML models)",
              ]}
            />
          </div>
          <p className="text-xs text-muted-foreground">Next 24 hours • 80% confidence band</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-muted-foreground">Avg predicted</p>
          <p className="text-sm font-bold tabular-nums">{formatTokens(avgPredicted)}/hr</p>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id="forecastBand" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.15} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted/50" />
          <XAxis
            dataKey="time"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
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
              const v = formatTokens(Number(value));
              if (n === "predicted") return [`${v} tokens`, "Predicted"];
              if (n === "upper") return [`${v}`, "Upper bound"];
              if (n === "lower") return [`${v}`, "Lower bound"];
              return [v, n];
            }}
          />
          {/* Confidence band */}
          <Area type="monotone" dataKey="upper" stroke="none" fill="url(#forecastBand)" name="upper" />
          <Area type="monotone" dataKey="lower" stroke="none" fill="hsl(var(--card))" name="lower" />
          {/* Predicted line */}
          <Area
            type="monotone"
            dataKey="predicted"
            stroke="#3b82f6"
            strokeWidth={2}
            strokeDasharray="6 3"
            fill="none"
            name="predicted"
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0, fill: "#3b82f6" }}
          />
        </AreaChart>
      </ResponsiveContainer>

      <div className="flex items-center justify-center gap-6 mt-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-0.5 bg-blue-500 rounded" style={{ borderTop: "2px dashed #3b82f6" }} />
          <span>Predicted</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-2 bg-blue-500/10 rounded" />
          <span>80% confidence</span>
        </div>
      </div>
    </div>
  );
}
