import { create } from "zustand";

export interface BurnRateForecast {
  predictedLimitHit: string | null;
  confidence: number;
  hourlyRate: number;
  trend: "increasing" | "stable" | "decreasing";
}

export interface Anomaly {
  id: string;
  timestamp: string;
  type: "spike" | "unusual_pattern" | "model_switch";
  severity: "low" | "medium" | "high";
  description: string;
}

export interface BehavioralProfile {
  peakHours: number[];
  avgSessionLength: number;
  preferredModels: string[];
  efficiencyScore: number;
}

export interface BudgetProjection {
  projectedMonthlyCost: number;
  daysRemaining: number;
  onTrack: boolean;
  projectedOverage: number;
}

interface MLStore {
  coldStartState: "collecting" | "linear" | "full";
  forecast: BurnRateForecast | null;
  anomalies: Anomaly[];
  profile: BehavioralProfile | null;
  budgetProjection: BudgetProjection | null;
  loadForecast: () => Promise<void>;
  loadAnomalies: () => Promise<void>;
  loadProfile: () => Promise<void>;
  loadBudgetProjection: () => Promise<void>;
}

export const useMLStore = create<MLStore>((set) => ({
  coldStartState: "collecting",
  forecast: null,
  anomalies: [],
  profile: null,
  budgetProjection: null,

  loadForecast: async () => {
    try {
      const res = await fetch("/api/v1/predictions/burnrate");
      if (res.ok) {
        const data = await res.json();
        set({
          forecast: {
            predictedLimitHit: data.predicted_limit_hit ?? data.predictedLimitHit ?? null,
            confidence: data.confidence ?? 0.5,
            hourlyRate: data.hourly_rate ?? data.hourlyRate ?? 0,
            trend: data.trend ?? "stable",
          },
          coldStartState: data.cold_start_state ?? data.coldStartState ?? (data.model_type === "linear" ? "linear" : "full"),
        });
      }
    } catch {
      // Forecast unavailable
    }
  },

  loadAnomalies: async () => {
    try {
      const res = await fetch("/api/v1/anomalies");
      if (res.ok) {
        const data = await res.json();
        set({ anomalies: data.anomalies ?? [] });
      }
    } catch {
      // Anomalies unavailable
    }
  },

  loadProfile: async () => {
    try {
      const res = await fetch("/api/v1/predictions/profile");
      if (res.ok) {
        const data = await res.json();
        set({
          profile: {
            peakHours: data.peak_hours ?? (data.peak_hour != null ? [data.peak_hour] : data.peakHours ?? []),
            avgSessionLength: data.avg_session_length ?? data.avgSessionLength ?? 0,
            preferredModels: data.preferred_models ?? data.preferredModels ?? [],
            efficiencyScore: data.efficiency_score ?? data.efficiencyScore ?? 0,
          },
        });
      }
    } catch {
      // Profile unavailable
    }
  },

  loadBudgetProjection: async () => {
    try {
      const res = await fetch("/api/v1/predictions/budget");
      if (res.ok) {
        const data = await res.json();
        set({
          budgetProjection: {
            projectedMonthlyCost: data.projected_monthly_cost ?? data.projectedMonthlyCost ?? 0,
            daysRemaining: data.days_remaining ?? data.daysRemaining ?? 0,
            onTrack: data.is_over_budget != null ? !data.is_over_budget : (data.onTrack ?? true),
            projectedOverage: data.projected_overage ?? data.projectedOverage ?? 0,
          },
        });
      }
    } catch {
      // Budget projection unavailable
    }
  },
}));
