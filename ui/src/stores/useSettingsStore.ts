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
  dailyTokenLimit: 33000,
  monthlyCostBudget: 18,
  planType: "pro",
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
        const rawPlan = overrides["plan.type"] || s?.plan?.type || "pro";
        const planDefaults: Record<string, { tokens: number; cost: number }> = {
          pro:    { tokens: 33000,   cost: 18 },
          max5:   { tokens: 220000,  cost: 35 },
          max20:  { tokens: 880000,  cost: 140 },
          custom: { tokens: 500000,  cost: 50 },
        };
        const pd = planDefaults[rawPlan] ?? planDefaults.pro;
        set({
          dailyTokenLimit: Number(overrides["alerts.thresholds.daily_token_limit"]) || alerts?.daily_token_limit || data.daily_token_limit || pd.tokens,
          monthlyCostBudget: Number(overrides["alerts.thresholds.monthly_cost_budget"]) || alerts?.monthly_cost_budget || data.monthly_cost_budget || pd.cost,
          planType: rawPlan,
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
