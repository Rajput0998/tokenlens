import { useTokenStore } from "@/stores/useTokenStore";
import { InfoTooltip } from "./InfoTooltip";

interface LiveTokenCounterProps {
  readonly loading?: boolean;
  readonly error?: string | null;
}

export function LiveTokenCounter({ loading, error }: LiveTokenCounterProps) {
  const todayTotal = useTokenStore((s) => s.todayTotal);
  const activeSessions = useTokenStore((s) => s.activeSessions);
  const perTool = useTokenStore((s) => s.perTool);

  if (error) {
    return (
      <div className="rounded-xl border border-destructive/30 bg-red-dim p-6 text-center shadow-card">
        <p className="text-destructive font-semibold">Failed to load token data</p>
        <p className="text-sm text-muted-foreground mt-1">{error}</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-8 text-center animate-pulse shadow-card">
        <div className="h-14 w-56 bg-muted rounded-lg mx-auto mb-3" />
        <div className="h-4 w-40 bg-muted rounded mx-auto" />
      </div>
    );
  }

  const toolCount = perTool.filter((t) => t.active).length;

  return (
    <div className="rounded-xl border bg-card p-8 shadow-card relative">
      <div className="absolute top-4 right-4">
        <InfoTooltip
          title="Live Token Counter"
          description="Total tokens consumed across all AI tools today (since midnight). Updates every 5 seconds via WebSocket. Tokens include both input (your prompts) and output (AI responses)."
          tips={[
            "A typical coding conversation uses 5K-50K tokens",
            "Large file context can consume 10K+ tokens per turn",
            "Counter resets at midnight each day",
          ]}
        />
      </div>
      <div className="text-center">
        <p className="text-[10px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-3">
          Total Tokens Today
        </p>
        <p
          className="text-5xl font-extrabold font-mono tabular-nums text-gradient leading-none"
          aria-live="polite"
          aria-label={`${todayTotal.toLocaleString()} tokens used today`}
        >
          {todayTotal.toLocaleString()}
        </p>
        <p className="text-sm text-muted-foreground mt-3 font-mono">
          across {toolCount} tool{toolCount !== 1 ? "s" : ""} today
          {activeSessions > 0 && (
            <span className="ml-2 text-accent-green">● {activeSessions} active</span>
          )}
        </p>
      </div>
    </div>
  );
}
