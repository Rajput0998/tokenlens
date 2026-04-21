import { create } from "zustand";

export interface PerToolUsage {
  tool: string;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  cost: number;
  active: boolean;
  lastEvent: string | null;
  hourly: Array<{ hour: number; tokens: number }>;
}

export interface SessionStats {
  sessionTokens: number;
  sessionCost: number;
  sessionMessages: number;
  sessionStart: string | null;
  sessionReset: string | null;
  firstEvent: string | null;
  tokenLimit: number;
  planType: string;
  burnRatePerMin: number;
  costRatePerMin: number;
  tokensExhaustAt: string | null;
}

export interface LiveUpdate {
  todayTotal: number;
  perTool: PerToolUsage[];
  burnRate: number;
  burnRateCategory: "slow" | "normal" | "fast" | "critical";
  activeSessions: number;
  costToday: number;
  timestamp: string;
  session?: SessionStats;
}

interface TokenStore {
  todayTotal: number;
  perTool: PerToolUsage[];
  burnRate: number;
  burnRateCategory: "slow" | "normal" | "fast" | "critical";
  activeSessions: number;
  costToday: number;
  lastEventTimestamp: string | null;
  interpolatedTotal: number;
  // Session window fields
  sessionTokens: number;
  sessionCost: number;
  sessionMessages: number;
  sessionStart: string | null;
  sessionReset: string | null;
  // Prediction fields from backend
  burnRatePerMin: number;
  costRatePerMin: number;
  tokensExhaustAt: string | null;
  tokenLimit: number;
  planType: string;
  updateFromWebSocket: (data: LiveUpdate) => void;
  interpolate: () => void;
}

export const useTokenStore = create<TokenStore>((set) => ({
  todayTotal: 0,
  perTool: [],
  burnRate: 0,
  burnRateCategory: "slow",
  activeSessions: 0,
  costToday: 0,
  lastEventTimestamp: null,
  interpolatedTotal: 0,
  // Session window defaults
  sessionTokens: 0,
  sessionCost: 0,
  sessionMessages: 0,
  sessionStart: null,
  sessionReset: null,
  // Prediction defaults
  burnRatePerMin: 0,
  costRatePerMin: 0,
  tokensExhaustAt: null,
  tokenLimit: 0,
  planType: "custom",

  updateFromWebSocket: (data: LiveUpdate) => {
    const sessionUpdate = data.session
      ? {
          sessionTokens: data.session.sessionTokens,
          sessionCost: data.session.sessionCost,
          sessionMessages: data.session.sessionMessages,
          sessionStart: data.session.sessionStart,
          sessionReset: data.session.sessionReset,
          burnRatePerMin: data.session.burnRatePerMin,
          costRatePerMin: data.session.costRatePerMin,
          tokensExhaustAt: data.session.tokensExhaustAt,
          tokenLimit: data.session.tokenLimit,
          planType: data.session.planType,
        }
      : {};

    set({
      todayTotal: data.todayTotal,
      perTool: data.perTool,
      burnRate: data.burnRate,
      burnRateCategory: data.burnRateCategory,
      activeSessions: data.activeSessions,
      costToday: data.costToday,
      lastEventTimestamp: data.timestamp,
      interpolatedTotal: data.todayTotal,
      ...sessionUpdate,
    });
  },

  interpolate: () => {
    // Disabled: show actual WebSocket value instead of estimated interpolation.
    // The 5-second WebSocket push is frequent enough for a good UX.
    // Interpolation caused the counter to look like a timer when burn rate was active.
  },
}));
