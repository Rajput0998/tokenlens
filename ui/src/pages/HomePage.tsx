import { useCallback } from "react";
import { LiveTokenCounter } from "@/components/home/LiveTokenCounter";
import { StatsGrid } from "@/components/home/StatsGrid";
import { ToolStatusCards } from "@/components/home/ToolStatusCards";
import { ConsumptionPulse } from "@/components/home/ConsumptionPulse";
import { SmartAlertBanner } from "@/components/home/SmartAlertBanner";
import type { AlertInfo } from "@/components/home/SmartAlertBanner";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useTokenStore } from "@/stores/useTokenStore";
import { useSettingsStore } from "@/stores/useSettingsStore";
import type { LiveUpdate } from "@/stores/useTokenStore";

export function HomePage() {
  const updateFromWebSocket = useTokenStore((s) => s.updateFromWebSocket);
  const todayTotal = useTokenStore((s) => s.todayTotal);
  const burnRateCategory = useTokenStore((s) => s.burnRateCategory);
  const dailyLimit = useSettingsStore((s) => s.dailyTokenLimit);

  const handleMessage = useCallback(
    (raw: unknown) => {
      // WebSocket sends {type: "live_update", data: {...}} envelope
      const envelope = raw as Record<string, unknown>;
      const payload = (envelope?.type === "live_update" ? envelope.data : envelope) as Record<string, unknown> | undefined;
      if (!payload) return;

      // Transform per_tool_details from API array or fallback from per_tool object
      const perToolDetails = payload.per_tool_details as Array<Record<string, unknown>> | undefined;
      const perToolRaw = payload.per_tool as Record<string, number> | undefined;

      const perToolArray = perToolDetails
        ? perToolDetails.map((t) => ({
            tool: (t.tool as string) ?? "unknown",
            inputTokens: 0,
            outputTokens: 0,
            totalTokens: (t.total_tokens as number) ?? 0,
            cost: (t.cost as number) ?? 0,
            active: (t.active as boolean) ?? true,
            lastEvent: null,
            hourly: (t.hourly as Array<{ hour: number; tokens: number }>) ?? [],
          }))
        : perToolRaw
          ? Object.entries(perToolRaw).map(([tool, totalTokens]) => ({
              tool,
              inputTokens: 0,
              outputTokens: 0,
              totalTokens,
              cost: 0,
              active: true,
              lastEvent: null,
              hourly: [] as Array<{ hour: number; tokens: number }>,
            }))
          : [];

      updateFromWebSocket({
        todayTotal: (payload.today_total as number) ?? 0,
        perTool: perToolArray,
        burnRate: (payload.burn_rate as number) ?? 0,
        burnRateCategory: ((payload.burn_rate_category as string) ?? "slow") as LiveUpdate["burnRateCategory"],
        activeSessions: (payload.active_sessions as number) ?? 0,
        costToday: (payload.cost_today as number) ?? 0,
        timestamp: (payload.last_event_timestamp as string) ?? new Date().toISOString(),
        session: payload.session
          ? {
              sessionTokens: ((payload.session as Record<string, unknown>).session_tokens as number) ?? 0,
              sessionCost: ((payload.session as Record<string, unknown>).session_cost as number) ?? 0,
              sessionMessages: ((payload.session as Record<string, unknown>).session_messages as number) ?? 0,
              sessionStart: ((payload.session as Record<string, unknown>).session_start as string) ?? null,
              sessionReset: ((payload.session as Record<string, unknown>).session_reset as string) ?? null,
              firstEvent: ((payload.session as Record<string, unknown>).first_event as string) ?? null,
              tokenLimit: ((payload.session as Record<string, unknown>).token_limit as number) ?? 0,
              planType: ((payload.session as Record<string, unknown>).plan_type as string) ?? "custom",
              burnRatePerMin: ((payload.session as Record<string, unknown>).burn_rate_per_min as number) ?? 0,
              costRatePerMin: ((payload.session as Record<string, unknown>).cost_rate_per_min as number) ?? 0,
              tokensExhaustAt: ((payload.session as Record<string, unknown>).tokens_exhaust_at as string) ?? null,
            }
          : undefined,
      });
    },
    [updateFromWebSocket]
  );

  const { isConnected } = useWebSocket({
    url: "/ws/live",
    onMessage: handleMessage,
  });

  // Determine the most important alert
  const getAlert = (): AlertInfo | null => {
    const pct = dailyLimit > 0 ? (todayTotal / dailyLimit) * 100 : 0;
    if (pct >= 90) {
      return { type: "critical", message: `${Math.round(pct)}% of daily limit used` };
    }
    if (burnRateCategory === "critical") {
      return { type: "critical", message: "Critical burn rate — on pace to hit limit soon" };
    }
    if (burnRateCategory === "fast") {
      return { type: "warning", message: "Fast burn rate — consider optimizing prompts" };
    }
    if (pct >= 75) {
      return { type: "warning", message: `${Math.round(pct)}% of daily limit used` };
    }
    if (!isConnected) {
      return { type: "info", message: "Connecting to live data..." };
    }
    return null;
  };

  return (
    <div className="space-y-6">
      <LiveTokenCounter />
      <StatsGrid />
      <ConsumptionPulse />
      <ToolStatusCards />
      <SmartAlertBanner alert={getAlert()} />
    </div>
  );
}
