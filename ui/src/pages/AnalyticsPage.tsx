import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TimePeriodSelector } from "@/components/analytics/TimePeriodSelector";
import type { TimePeriod } from "@/components/analytics/TimePeriodSelector";
import { TokenUsageTimeline } from "@/components/analytics/TokenUsageTimeline";
import { ToolComparisonBarChart } from "@/components/analytics/ToolComparisonBarChart";
import { ModelUsagePieChart } from "@/components/analytics/ModelUsagePieChart";
import { TokenIntensityHeatmap } from "@/components/analytics/TokenIntensityHeatmap";
import { SessionList } from "@/components/analytics/SessionList";
import { apiFetch } from "@/lib/api";

/** Unwrap API response: bare array or {data: [...]} or {sessions: [...]}. */
function unwrap(raw: unknown, key = "data"): unknown[] {
if (Array.isArray(raw)) return raw;
if (raw && typeof raw === "object" && key in raw) {
const val = (raw as Record<string, unknown>)[key];
return Array.isArray(val) ? val : [];
}
return [];
}

export function AnalyticsPage() {
const [period, setPeriod] = useState<TimePeriod>("24h");

const timeline = useQuery({
queryKey: ["analytics", "timeline", period],
queryFn: () => apiFetch<unknown>(`/analytics/timeline?period=${period}`),
});

const tools = useQuery({
queryKey: ["analytics", "tools", period],
queryFn: () => apiFetch<unknown>(`/analytics/tools?period=${period}`),
});

const models = useQuery({
queryKey: ["analytics", "models", period],
queryFn: () => apiFetch<unknown>(`/analytics/models?period=${period}`),
});

const heatmap = useQuery({
queryKey: ["analytics", "heatmap"],
queryFn: () => {
const tzOffset = -(new Date().getTimezoneOffset()); // Convert JS offset (minutes behind UTC) to minutes ahead of UTC
return apiFetch<unknown>(`/analytics/heatmap?tz_offset_minutes=${tzOffset}`);
},
});

const sessions = useQuery({
queryKey: ["sessions", period],
queryFn: () => apiFetch<unknown>(`/sessions?period=${period}`),
});

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Analytics</h1>
        <TimePeriodSelector value={period} onChange={setPeriod} />
      </div>

      <TokenUsageTimeline
        data={unwrap(timeline.data) as never[]}
        period={period}
        loading={timeline.isLoading}
        error={timeline.error?.message ?? null}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ToolComparisonBarChart
          data={unwrap(tools.data) as never[]}
          loading={tools.isLoading}
        />
        <ModelUsagePieChart
          data={unwrap(models.data) as never[]}
          loading={models.isLoading}
        />
      </div>

      <TokenIntensityHeatmap
        data={unwrap(heatmap.data) as never[]}
        loading={heatmap.isLoading}
      />

      <SessionList
        sessions={unwrap(sessions.data, "sessions") as never[]}
        loading={sessions.isLoading}
      />
    </div>
  );
}
