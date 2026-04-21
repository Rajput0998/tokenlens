import { describe, it, expect, beforeEach } from "vitest";
import { useTokenStore } from "./useTokenStore";
import type { LiveUpdate } from "./useTokenStore";

describe("useTokenStore", () => {
  beforeEach(() => {
    useTokenStore.setState({
      todayTotal: 0,
      perTool: [],
      burnRate: 0,
      burnRateCategory: "slow",
      activeSessions: 0,
      costToday: 0,
      lastEventTimestamp: null,
      interpolatedTotal: 0,
    });
  });

  it("updates state from WebSocket data", () => {
    const update: LiveUpdate = {
      todayTotal: 45000,
      perTool: [
        {
          tool: "claude_code",
          inputTokens: 30000,
          outputTokens: 15000,
          totalTokens: 45000,
          cost: 0.35,
          active: true,
          lastEvent: "2025-01-15T14:00:00Z",
        },
      ],
      burnRate: 3200,
      burnRateCategory: "normal",
      activeSessions: 1,
      costToday: 0.35,
      timestamp: "2025-01-15T14:00:00Z",
    };

    useTokenStore.getState().updateFromWebSocket(update);

    const state = useTokenStore.getState();
    expect(state.todayTotal).toBe(45000);
    expect(state.perTool).toHaveLength(1);
    expect(state.perTool[0].tool).toBe("claude_code");
    expect(state.burnRate).toBe(3200);
    expect(state.burnRateCategory).toBe("normal");
    expect(state.activeSessions).toBe(1);
    expect(state.costToday).toBe(0.35);
    expect(state.lastEventTimestamp).toBe("2025-01-15T14:00:00Z");
    expect(state.interpolatedTotal).toBe(45000);
  });

  it("interpolates token count when active sessions exist", () => {
    useTokenStore.setState({
      todayTotal: 45000,
      interpolatedTotal: 45000,
      burnRate: 3600, // 3600 tokens/hour = 5 tokens per 5s tick
      activeSessions: 1,
    });

    useTokenStore.getState().interpolate();

    const state = useTokenStore.getState();
    expect(state.interpolatedTotal).toBe(45005);
  });

  it("does not interpolate when no active sessions", () => {
    useTokenStore.setState({
      todayTotal: 45000,
      interpolatedTotal: 45000,
      burnRate: 3600,
      activeSessions: 0,
    });

    useTokenStore.getState().interpolate();

    const state = useTokenStore.getState();
    expect(state.interpolatedTotal).toBe(45000);
  });
});
