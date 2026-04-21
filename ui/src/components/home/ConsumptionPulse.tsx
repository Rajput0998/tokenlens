import { useTokenStore } from "@/stores/useTokenStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { InfoTooltip } from "./InfoTooltip";
import { Flame, DollarSign, Target, Zap, CalendarClock } from "lucide-react";
import { formatLocalTime } from "@/lib/dateUtils";

interface ConsumptionPulseProps {
  readonly loading?: boolean;
}

function formatTime(isoOrNull: string | null, fallbackLabel: string): string {
  return formatLocalTime(isoOrNull, fallbackLabel);
}

export function ConsumptionPulse({ loading }: ConsumptionPulseProps) {
  const burnRate = useTokenStore((s) => s.burnRate);
  const sessionCost = useTokenStore((s) => s.sessionCost);
  const sessionReset = useTokenStore((s) => s.sessionReset);
  const burnRatePerMin = useTokenStore((s) => s.burnRatePerMin);
  const costRatePerMin = useTokenStore((s) => s.costRatePerMin);
  const tokensExhaustAt = useTokenStore((s) => s.tokensExhaustAt);
  const monthlyBudget = useSettingsStore((s) => s.monthlyCostBudget);

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-5 shadow-card animate-pulse">
        <div className="h-4 w-40 bg-muted rounded mb-4" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <div key={i} className="h-16 bg-muted rounded-lg" />)}
        </div>
      </div>
    );
  }

  // Use backend-computed rates (accurate, based on actual session duration)
  const tokensPerMin = burnRatePerMin;
  const costPerMin = costRatePerMin;

  // Tokens will run out at (exact time from backend prediction)
  const runOutTime = tokensExhaustAt;

  // Limit resets at (exact time from session window)
  const resetAtTime = sessionReset;

  // Cost usage percentage
  const costPct = monthlyBudget > 0 ? ((sessionCost / monthlyBudget) * 100) : 0;

  const items = [
    {
      icon: Flame,
      label: "Consumption Speed",
      value: tokensPerMin >= 1 ? `${tokensPerMin.toFixed(1)}` : "<1",
      unit: "tok/min",
      color: tokensPerMin > 100 ? "var(--red)" : tokensPerMin > 50 ? "var(--orange)" : "var(--teal)",
    },
    {
      icon: DollarSign,
      label: "Cost Velocity",
      value: `$${costPerMin.toFixed(4)}`,
      unit: "/min",
      color: costPerMin > 0.02 ? "var(--red)" : costPerMin > 0.01 ? "var(--orange)" : "var(--teal)",
    },
    {
      icon: DollarSign,
      label: "Session Spend",
      value: `$${sessionCost.toFixed(2)}`,
      unit: `/ $${monthlyBudget.toFixed(0)}`,
      color: costPct > 75 ? "var(--red)" : costPct > 50 ? "var(--orange)" : "var(--teal)",
    },
    {
      icon: Target,
      label: "Tokens Exhaust At",
      value: runOutTime ? formatTime(runOutTime, "—") : "Safe",
      unit: runOutTime ? "estimated" : "won't hit limit",
      color: runOutTime ? "var(--orange)" : "var(--green)",
    },
    {
      icon: CalendarClock,
      label: "Session Resets At",
      value: formatTime(resetAtTime, "—"),
      unit: "local time",
      color: "var(--blue)",
    },
    {
      icon: Zap,
      label: "Hourly Rate",
      value: burnRate >= 1000 ? `${(burnRate / 1000).toFixed(1)}K` : `${Math.round(burnRate)}`,
      unit: "tok/hr",
      color: burnRate > 5000 ? "var(--red)" : burnRate > 1000 ? "var(--orange)" : "var(--teal)",
    },
  ];

  return (
    <div className="rounded-xl border bg-card p-5 shadow-card">
      <div className="flex items-center gap-2 mb-4">
        <Flame className="h-4 w-4" style={{ color: "var(--teal)" }} />
        <h3 className="text-sm font-semibold">Consumption Pulse</h3>
        <InfoTooltip
          title="Consumption Pulse"
          description="Real-time consumption metrics for your current session. Shows how fast you're using tokens and money, when tokens will run out at current pace, and when the session resets."
          tips={[
            "Consumption Speed: tokens consumed per minute",
            "Cost Velocity: dollars spent per minute",
            "Tokens Exhaust At: predicted time when you'll hit the limit",
            "Session Resets At: when your 5-hour window expires and limits refresh",
          ]}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="rounded-lg bg-muted/30 p-3 text-center hover:bg-muted/50 transition-colors">
              <Icon className="h-3.5 w-3.5 mx-auto mb-1.5" style={{ color: item.color }} />
              <p className="text-lg font-bold font-mono tabular-nums leading-tight" style={{ color: item.color }}>
                {item.value}
              </p>
              <p className="text-[9px] text-muted-foreground mt-0.5">{item.unit}</p>
              <p className="text-[8px] text-muted-foreground/60 mt-0.5 uppercase tracking-wider">{item.label}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
