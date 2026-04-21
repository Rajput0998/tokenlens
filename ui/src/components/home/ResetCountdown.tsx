import { useState, useEffect } from "react";
import { useTokenStore } from "@/stores/useTokenStore";
import { InfoTooltip } from "./InfoTooltip";

interface ResetCountdownProps {
  readonly loading?: boolean;
}

function pad(n: number): string {
  return n.toString().padStart(2, "0");
}

function getTimeRemaining(sessionReset: string | null): {
  hours: number;
  minutes: number;
  seconds: number;
  label: string;
} {
  if (sessionReset) {
    const resetTime = new Date(sessionReset);
    const now = new Date();
    const remainingMs = resetTime.getTime() - now.getTime();

    if (remainingMs > 0) {
      return {
        hours: Math.floor(remainingMs / (1000 * 60 * 60)),
        minutes: Math.floor((remainingMs % (1000 * 60 * 60)) / (1000 * 60)),
        seconds: Math.floor((remainingMs % (1000 * 60)) / 1000),
        label: "session window remaining",
      };
    }
  }

  // Fallback: show time until midnight
  const now = new Date();
  const midnight = new Date(now);
  midnight.setHours(24, 0, 0, 0);
  const diff = midnight.getTime() - now.getTime();
  return {
    hours: Math.floor(diff / (1000 * 60 * 60)),
    minutes: Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60)),
    seconds: Math.floor((diff % (1000 * 60)) / 1000),
    label: "until daily counter resets",
  };
}

export function ResetCountdown({ loading }: ResetCountdownProps) {
  const sessionReset = useTokenStore((s) => s.sessionReset);
  const [time, setTime] = useState(() => getTimeRemaining(sessionReset));

  useEffect(() => {
    const interval = setInterval(() => {
      setTime(getTimeRemaining(sessionReset));
    }, 1000);
    return () => clearInterval(interval);
  }, [sessionReset]);

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-5 animate-pulse shadow-card">
        <div className="h-4 w-20 bg-muted rounded mb-3" />
        <div className="h-10 w-36 bg-muted rounded mx-auto" />
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-card p-5 text-center shadow-card relative hover:shadow-card-hover transition-shadow">
      <div className="flex items-center justify-center gap-1.5 mb-3">
        <p className="text-[10px] font-semibold uppercase tracking-[1.5px] text-muted-foreground">Reset In</p>
        <InfoTooltip
          title="Session Reset Timer"
          description="Claude Code uses 5-hour rolling session windows. This shows time remaining in your current session. When the session expires, your token limit resets."
          tips={[
            "Claude sessions last exactly 5 hours from first message",
            "Session start is rounded down to the nearest hour",
            "Plan heavy tasks at the start of a fresh session",
            "Your usage history is preserved after reset",
          ]}
        />
      </div>
      <p className="text-3xl font-mono font-bold tabular-nums text-gradient mt-4">
        {pad(time.hours)}:{pad(time.minutes)}:{pad(time.seconds)}
      </p>
      <p className="text-[10px] text-muted-foreground mt-2">{time.label}</p>
    </div>
  );
}
