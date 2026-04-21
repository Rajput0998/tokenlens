import { useTokenStore } from "@/stores/useTokenStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { InfoTooltip } from "./InfoTooltip";
import { MessageSquare } from "lucide-react";

interface MessageCounterProps {
  readonly loading?: boolean;
}

const PLAN_MESSAGE_LIMITS: Record<string, number> = {
  pro: 250,
  max5: 1000,
  max20: 2000,
  custom: 250,
};

export function MessageCounter({ loading }: MessageCounterProps) {
  const sessionMessages = useTokenStore((s) => s.sessionMessages);
  const planType = useSettingsStore((s) => s.planType);

  const messageLimit = PLAN_MESSAGE_LIMITS[planType] ?? 250;
  const percentage = messageLimit > 0 ? Math.round((sessionMessages / messageLimit) * 100) : 0;
  const color = percentage >= 90 ? "var(--red)" : percentage >= 75 ? "var(--orange)" : "var(--teal)";

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-5 animate-pulse shadow-card">
        <div className="h-4 w-20 bg-muted rounded mb-3" />
        <div className="h-8 w-24 bg-muted rounded mx-auto" />
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-card p-5 text-center shadow-card relative hover:shadow-card-hover transition-shadow">
      <div className="flex items-center justify-center gap-1.5 mb-3">
        <p className="text-[10px] font-semibold uppercase tracking-[1.5px] text-muted-foreground">Messages</p>
        <InfoTooltip
          title="Session Messages"
          description="Number of messages (API calls) in your current 5-hour session. Each plan has a message limit per session."
          tips={[
            "Pro plan: 250 messages per session",
            "Max5 plan: 1,000 messages per session",
            "Max20 plan: 2,000 messages per session",
            "Each tool call counts as a separate message",
          ]}
        />
      </div>

      {/* Progress bar */}
      <div className="w-full h-2 bg-muted rounded-full overflow-hidden mb-3">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${Math.min(percentage, 100)}%`,
            backgroundColor: color,
          }}
        />
      </div>

      <div className="flex items-center justify-center gap-2">
        <MessageSquare className="h-4 w-4" style={{ color }} />
        <p className="text-2xl font-bold font-mono tabular-nums" style={{ color }}>
          {sessionMessages}
        </p>
        <p className="text-sm text-muted-foreground font-mono">/ {messageLimit}</p>
      </div>

      <p className="text-[10px] text-muted-foreground mt-1">
        {percentage}% used this session
      </p>
    </div>
  );
}
