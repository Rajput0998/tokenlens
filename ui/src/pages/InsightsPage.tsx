import { useQuery } from "@tanstack/react-query";
import { ForecastChart } from "@/components/insights/ForecastChart";
import { PredictionCard } from "@/components/insights/PredictionCard";
import { ColdStartBanner } from "@/components/insights/ColdStartBanner";
import { WhatIfSimulator } from "@/components/insights/WhatIfSimulator";
import { ProfileCard } from "@/components/insights/ProfileCard";
import { useMLStore } from "@/stores/useMLStore";
import { apiFetch } from "@/lib/api";
import { useEffect } from "react";
import { InfoTooltip } from "@/components/home/InfoTooltip";
import { formatLocalTime } from "@/lib/dateUtils";

/** Unwrap forecast data: API returns {forecast: [...]} not {data: [...]} */
function unwrapForecast(raw: unknown): unknown[] {
  if (Array.isArray(raw)) return raw;
  if (raw && typeof raw === "object") {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.forecast)) return obj.forecast;
    if (Array.isArray(obj.data)) return obj.data;
  }
  return [];
}

function unwrapAnomalies(raw: unknown): unknown[] {
  if (Array.isArray(raw)) return raw;
  if (raw && typeof raw === "object") {
    const obj = raw as Record<string, unknown>;
    if (Array.isArray(obj.anomalies)) return obj.anomalies;
  }
  return [];
}

export function InsightsPage() {
  const { coldStartState, forecast, profile, budgetProjection, loadForecast, loadProfile, loadBudgetProjection } = useMLStore();

  useEffect(() => {
    loadForecast();
    loadProfile();
    loadBudgetProjection();
  }, [loadForecast, loadProfile, loadBudgetProjection]);

  const forecastData = useQuery({
    queryKey: ["forecast", "chart"],
    queryFn: () => apiFetch<unknown>("/predictions/burnrate"),
  });

  const anomalies = useQuery({
    queryKey: ["anomalies"],
    queryFn: () => apiFetch<unknown>("/anomalies"),
  });

  const limitPrediction = useQuery({
    queryKey: ["predictions", "limit"],
    queryFn: () => apiFetch<Record<string, unknown>>("/predictions/limit"),
  });

  // Format limit prediction
  const limitData = limitPrediction.data;
  const willHitLimit = limitData?.will_hit_limit as boolean | undefined;
  const estimatedTime = limitData?.estimated_time as string | undefined;
  const limitValue = willHitLimit
    ? estimatedTime
      ? formatLocalTime(estimatedTime, "Today")
      : "Today"
    : "None";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Insights</h1>
      </div>

      <ColdStartBanner state={coldStartState} />

      <ForecastChart
        data={unwrapForecast(forecastData.data) as never[]}
        loading={forecastData.isLoading}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="relative">
          <div className="absolute top-2 right-2 z-10">
            <InfoTooltip
              title="Predicted Limit Hit"
              description="Predicts when you'll hit your daily token limit based on current burn rate. Shows the estimated time, or 'None' if you won't hit it today."
              tips={[
                "Based on your current hourly consumption rate",
                "Updates as your usage pattern changes throughout the day",
                "Configure your plan in Settings for accurate limits",
              ]}
            />
          </div>
          <PredictionCard
            title="Predicted Limit Hit"
            value={limitValue}
            subtitle={
              willHitLimit
                ? `Current: ${((limitData?.current_usage as number) ?? 0).toLocaleString()} / ${((limitData?.daily_limit as number) ?? 0).toLocaleString()}`
                : forecast ? `${Math.round(forecast.confidence * 100)}% confidence` : "Safe for today"
            }
            trend={willHitLimit ? "up" : "stable"}
            loading={limitPrediction.isLoading}
          />
        </div>

        <div className="relative">
          <div className="absolute top-2 right-2 z-10">
            <InfoTooltip
              title="Monthly Cost Projection"
              description="Projects your total monthly spend based on your daily average so far this month. 'On track' means you're within budget, 'Over budget' means you'll exceed it at current pace."
              tips={[
                "Based on: (daily average cost) × 30 days",
                "Reduce costs by using cheaper models (Haiku) for simple tasks",
                "Use the What-If Simulator below to explore savings",
              ]}
            />
          </div>
          <PredictionCard
            title="Monthly Cost"
            value={budgetProjection ? `$${budgetProjection.projectedMonthlyCost.toFixed(2)}` : "—"}
            subtitle={budgetProjection?.onTrack ? "On track" : "Over budget"}
            trend={budgetProjection?.onTrack ? "stable" : "up"}
            loading={!budgetProjection && forecastData.isLoading}
          />
        </div>

        <div className="relative">
          <div className="absolute top-2 right-2 z-10">
            <InfoTooltip
              title="Anomalies"
              description="Counts unusual usage patterns detected by the ML anomaly detector. Anomalies include sudden spikes, unusual model switches, or consumption patterns that differ significantly from your baseline."
              tips={[
                "0 anomalies = your usage is consistent and predictable",
                "Anomalies are detected using IsolationForest ML model",
                "Needs 7+ days of data for accurate anomaly detection",
              ]}
            />
          </div>
          <PredictionCard
            title="Anomalies"
            value={`${unwrapAnomalies(anomalies.data).length}`}
            subtitle="detected this period"
            loading={anomalies.isLoading}
          />
        </div>

        <div className="relative">
          <div className="absolute top-2 right-2 z-10">
            <InfoTooltip
              title="Efficiency Score"
              description="Rates how efficiently you use tokens on a 0-100 scale. Based on 5 factors: output/input ratio (30%), cache hit rate (25%), turns to completion (20%), context growth (15%), and cost per output token (10%)."
              tips={[
                "70+ = Good efficiency, keep it up",
                "30-70 = Room for improvement",
                "Below 30 = Consider shorter sessions and smaller context",
                "Improve by: fewer turns, more cache hits, less context bloat",
              ]}
            />
          </div>
          <PredictionCard
            title="Efficiency Score"
            value={profile ? `${profile.efficiencyScore}/100` : "—"}
            loading={!profile && forecastData.isLoading}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <WhatIfSimulator loading={forecastData.isLoading} />
        <ProfileCard profile={profile} loading={!profile && forecastData.isLoading} />
      </div>
    </div>
  );
}
