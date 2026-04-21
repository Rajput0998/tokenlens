import { create } from "zustand";

export interface AdapterConfig {
  name: string;
  enabled: boolean;
  logPath: string;
}

export interface WebhookConfig {
  url: string;
  type: "slack" | "discord" | "teams" | "generic";
  enabled: boolean;
}

interface SettingsStore {
  dailyTokenLimit: number;
  monthlyCostBudget: number;
  planType: string;
  adapters: AdapterConfig[];
  alertThresholds: number[];
  webhooks: WebhookConfig[];
  theme: "light" | "dark" | "system";
  setTheme: (theme: "light" | "dark" | "system") => void;
  updateSettings: (settings: Partial<SettingsStore>) => void;
  loadSettings: () => Promise<void>;
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  dailyTokenLimit: 500000,
  monthlyCostBudget: 50,
  planType: "custom",
  adapters: [],
  alertThresholds: [50, 75, 90, 100],
  webhooks: [],
  theme: "system",

  setTheme: (theme) => {
    set({ theme });
    localStorage.setItem("tokenlens-theme", theme);
  },

  updateSettings: (settings) => {
    set(settings);
  },

  loadSettings: async () => {
    try {
      const res = await fetch("/api/v1/settings");
      if (res.ok) {
        const data = await res.json();
        const s = data?.settings ?? data;
        const overrides = s?._overrides ?? {};
        const alerts = s?.alerts?.thresholds ?? {};
        set({
          dailyTokenLimit: Number(overrides["alerts.thresholds.daily_token_limit"]) || alerts?.daily_token_limit || data.daily_token_limit || 500000,
          monthlyCostBudget: Number(overrides["alerts.thresholds.monthly_cost_budget"]) || alerts?.monthly_cost_budget || data.monthly_cost_budget || 50,
          planType: overrides["plan.type"] || "custom",
          adapters: data.adapters ?? [],
          alertThresholds: data.alert_thresholds ?? [50, 75, 90, 100],
          webhooks: data.webhooks ?? [],
        });
      }
    } catch {
      // Settings will use defaults if API is unavailable
    }
  },
}));
