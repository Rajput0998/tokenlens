import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useWebSocket } from "./useWebSocket";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  readyState = 0; // CONNECTING
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  sentMessages: string[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = 3; // CLOSED
    this.onclose?.();
  }

  simulateOpen() {
    this.readyState = 1; // OPEN
    this.onopen?.();
  }

  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  static get OPEN() { return 1; }
  static get CLOSED() { return 3; }
  static get CONNECTING() { return 0; }
}

// Also set instance constants
Object.defineProperty(MockWebSocket.prototype, "OPEN", { value: 1 });
Object.defineProperty(MockWebSocket.prototype, "CLOSED", { value: 3 });
Object.defineProperty(MockWebSocket.prototype, "CONNECTING", { value: 0 });

describe("useWebSocket", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("connects to the WebSocket URL", () => {
    renderHook(() => useWebSocket({ url: "/ws/live" }));
    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toContain("/ws/live");
  });

  it("sets isConnected to true on open", () => {
    const { result } = renderHook(() => useWebSocket({ url: "/ws/live" }));

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    expect(result.current.isConnected).toBe(true);
  });

  it("parses JSON messages and calls onMessage", () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket({ url: "/ws/live", onMessage }));

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    act(() => {
      MockWebSocket.instances[0].simulateMessage({ todayTotal: 1000 });
    });

    expect(onMessage).toHaveBeenCalledWith({ todayTotal: 1000 });
  });

  it("attempts reconnection with exponential backoff", () => {
    const { result } = renderHook(() =>
      useWebSocket({ url: "/ws/live", reconnect: true, maxRetries: 3 })
    );

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    // Simulate disconnect
    act(() => {
      MockWebSocket.instances[0].close();
    });

    expect(result.current.isConnected).toBe(false);

    // After 1s backoff, should reconnect
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(MockWebSocket.instances.length).toBe(2);
    expect(result.current.reconnectAttempt).toBe(1);
  });

  it("sends data when connected", () => {
    const { result } = renderHook(() => useWebSocket({ url: "/ws/live" }));

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    act(() => {
      result.current.send({ type: "ping" });
    });

    expect(MockWebSocket.instances[0].sentMessages).toContain(
      JSON.stringify({ type: "ping" })
    );
  });
});
