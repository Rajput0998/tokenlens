import { useTokenStore } from "@/stores/useTokenStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { InfoTooltip } from "./InfoTooltip";

interface BurnRateGaugeProps {
  readonly loading?: boolean;
}

const CATEGORIES = {
  slow: { color: "var(--green)", label: "SLOW", desc: "Light usage" },
  normal: { color: "var(--blue)", label: "NORMAL", desc: "Steady pace" },
  fast: { color: "var(--orange)", label: "FAST", desc: "Heavy usage" },
  critical: { color: "var(--red)", label: "CRITICAL", desc: "Limit at risk" },
} as const;

export function BurnRateGauge({ loading }: BurnRateGaugeProps) {
  const burnRate = useTokenStore((s) => s.burnRate);
  const burnRateCategory = useTokenStore((s) => s.burnRateCategory);
  const sessionTokens = useTokenStore((s) => s.sessionTokens);
  const sessionReset = useTokenStore((s) => s.sessionReset);
  const dailyLimit = useSettingsStore((s) => s.dailyTokenLimit);

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-5 animate-pulse shadow-card">
        <div className="h-4 w-20 bg-muted rounded mb-3" />
        <div className="h-20 w-32 bg-muted rounded-full mx-auto" />
      </div>
    );
  }

  const { color, label } = CATEGORIES[burnRateCategory];

  const maxRate = 10000;
  const ratio = Math.min(burnRate / maxRate, 1);
  const angle = Math.max(ratio * 180, burnRate > 0 ? 8 : 0);
  const radians = (angle * Math.PI) / 180;
  const endX = 70 - 45 * Math.cos(radians);
  const endY = 70 - 45 * Math.sin(radians);
  const largeArc = angle > 90 ? 1 : 0;

  // Calculate time-to-limit using session tokens and session remaining time
  const remaining = dailyLimit - sessionTokens;
  const hoursToLimit = burnRate > 0 ? remaining / burnRate : null;

  let limitText = "No activity";
  if (hoursToLimit !== null) {
    if (hoursToLimit <= 0) {
      limitText = "Session limit reached";
    } else if (sessionReset) {
      const resetTime = new Date(sessionReset);
      const now = new Date();
      const sessionHoursLeft = Math.max((resetTime.getTime() - now.getTime()) / (1000 * 60 * 60), 0);
      if (hoursToLimit > sessionHoursLeft) {
        limitText = "Won't hit limit this session";
      } else {
        const h = Math.floor(hoursToLimit);
        const m = Math.round((hoursToLimit % 1) * 60);
        limitText = `Limit in ~${h}h ${m}m`;
      }
    } else {
      if (hoursToLimit > 5) {
        limitText = "Won't hit limit this session";
      } else {
        const h = Math.floor(hoursToLimit);
        const m = Math.round((hoursToLimit % 1) * 60);
        limitText = `Limit in ~${h}h ${m}m`;
      }
    }
  }

  const rateDisplay = burnRate >= 1000
    ? `${(burnRate / 1000).toFixed(1)}K`
    : Math.round(burnRate).toString();

  return (
    <div className="rounded-xl border bg-card p-5 text-center shadow-card relative hover:shadow-card-hover transition-shadow">
      <div className="flex items-center justify-center gap-1.5 mb-3">
        <p className="text-[10px] font-semibold uppercase tracking-[1.5px] text-muted-foreground">Burn Rate</p>
        <InfoTooltip
          title="Burn Rate"
          description="How fast you're consuming tokens per hour. The gauge shows your consumption speed with a multi-color arc from green (slow) to red (critical). Time-to-limit is calculated against your session window."
          tips={[
            "Slow (<1K/hr): Light usage, no concerns",
            "Normal (1K-5K/hr): Typical coding session",
            "Fast (5K-10K/hr): Heavy usage, monitor closely",
            "Critical (>10K/hr): May hit session limit soon",
          ]}
        />
      </div>
      <div className="w-36 h-20 mx-auto">
        <svg viewBox="0 0 140 80" className="w-full h-full">
          {/* Multi-color background arc */}
          <path d="M 15 70 A 55 55 0 0 1 40 22" fill="none" stroke="#22c55e" strokeWidth="10" strokeLinecap="round" opacity="0.3"/>
          <path d="M 42 20 A 55 55 0 0 1 70 12" fill="none" stroke="#f59e0b" strokeWidth="10" strokeLinecap="round" opacity="0.3"/>
          <path d="M 72 12 A 55 55 0 0 1 100 22" fill="none" stroke="#f97316" strokeWidth="10" strokeLinecap="round" opacity="0.3"/>
          <path d="M 102 24 A 55 55 0 0 1 125 70" fill="none" stroke="#ef4444" strokeWidth="10" strokeLinecap="round" opacity="0.3"/>
          {/* Active arc */}
          {burnRate > 0 && (
            <path
              d={`M 25 70 A 45 45 0 ${largeArc} 1 ${endX} ${endY}`}
              fill="none"
              stroke={color}
              strokeWidth="10"
              strokeLinecap="round"
            />
          )}
          {/* Needle */}
          <line x1="70" y1="70" x2={endX} y2={endY} stroke="hsl(var(--foreground))" strokeWidth="2" strokeLinecap="round" opacity="0.6"/>
          <circle cx="70" cy="70" r="3" fill="hsl(var(--foreground))" opacity="0.6"/>
        </svg>
      </div>
      <p className="text-lg font-bold font-mono" style={{ color }}>{label}</p>
      <p className="text-xs text-muted-foreground font-mono tabular-nums">{rateDisplay} tok/hr</p>
      <p className="text-[10px] text-muted-foreground mt-1">{limitText}</p>
    </div>
  );
}
