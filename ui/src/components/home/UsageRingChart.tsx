import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { useTokenStore } from "@/stores/useTokenStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { InfoTooltip } from "./InfoTooltip";

interface UsageRingChartProps {
  readonly loading?: boolean;
}

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

export function UsageRingChart({ loading }: UsageRingChartProps) {
  const todayTotal = useTokenStore((s) => s.todayTotal);
  const sessionTokens = useTokenStore((s) => s.sessionTokens);
  const dailyLimit = useSettingsStore((s) => s.dailyTokenLimit);

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-5 animate-pulse shadow-card">
        <div className="h-4 w-20 bg-muted rounded mb-3" />
        <div className="h-28 w-28 bg-muted rounded-full mx-auto" />
      </div>
    );
  }

  // Use session tokens for the ring, with plan limit
  const used = Math.min(sessionTokens, dailyLimit);
  const remaining = Math.max(dailyLimit - sessionTokens, 0);
  const percentage = dailyLimit > 0 ? Math.round((sessionTokens / dailyLimit) * 100) : 0;

  const data = [
    { name: "Used", value: used || 1 },
    { name: "Remaining", value: remaining || (used === 0 ? 1 : 0) },
  ];

  const color = percentage >= 90 ? "var(--red)" : percentage >= 75 ? "var(--orange)" : "var(--teal)";

  return (
    <div className="rounded-xl border bg-card p-5 text-center shadow-card relative hover:shadow-card-hover transition-shadow">
      <div className="flex items-center justify-center gap-1.5 mb-3">
        <p className="text-[10px] font-semibold uppercase tracking-[1.5px] text-muted-foreground">Session Usage</p>
        <InfoTooltip
          title="Session Usage"
          description="Shows what percentage of your session token limit you've consumed. Claude Code uses 5-hour rolling session windows with plan-specific limits."
          tips={[
            "Pro plan: 19K tokens per session",
            "Max5 plan: 88K tokens per session",
            "Max20 plan: 220K tokens per session",
            "Teal = safe, Orange = caution, Red = near limit",
          ]}
        />
      </div>
      <div className="relative w-28 h-28 mx-auto">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={35}
              outerRadius={50}
              startAngle={90}
              endAngle={-270}
              dataKey="value"
              stroke="none"
            >
              <Cell fill={color} />
              <Cell fill="hsl(var(--muted))" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-bold font-mono" style={{ color }}>{percentage}%</span>
        </div>
      </div>
      <p className="text-xs text-muted-foreground mt-2 font-mono tabular-nums">
        Session: {formatTokens(sessionTokens)} / {formatTokens(dailyLimit)}
      </p>
      <p className="text-[10px] text-muted-foreground mt-0.5 font-mono tabular-nums">
        Today: {todayTotal.toLocaleString()} total
      </p>
    </div>
  );
}
