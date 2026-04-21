import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { LiveTokenCounter } from "./LiveTokenCounter";
import { useTokenStore } from "@/stores/useTokenStore";

describe("LiveTokenCounter", () => {
  beforeEach(() => {
    useTokenStore.setState({
      interpolatedTotal: 0,
      activeSessions: 0,
      perTool: [],
      burnRate: 0,
    });
  });

  it("renders loading state", () => {
    render(<LiveTokenCounter loading />);
    // Should show skeleton (no text content)
    expect(screen.queryByText(/tokens today/)).not.toBeInTheDocument();
  });

  it("renders error state", () => {
    render(<LiveTokenCounter error="Connection failed" />);
    expect(screen.getByText("Failed to load token data")).toBeInTheDocument();
    expect(screen.getByText("Connection failed")).toBeInTheDocument();
  });

  it("renders token count", () => {
    useTokenStore.setState({
      interpolatedTotal: 45231,
      activeSessions: 2,
      perTool: [
        { tool: "claude_code", inputTokens: 30000, outputTokens: 15000, totalTokens: 45000, cost: 0.35, active: true, lastEvent: null },
        { tool: "kiro", inputTokens: 200, outputTokens: 31, totalTokens: 231, cost: 0.01, active: true, lastEvent: null },
      ],
    });

    render(<LiveTokenCounter />);
    expect(screen.getByText("45,231")).toBeInTheDocument();
    expect(screen.getByText(/across 2 tools today/)).toBeInTheDocument();
  });

  it("shows empty state with 0 tokens", () => {
    render(<LiveTokenCounter />);
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getByText(/across 0 tools today/)).toBeInTheDocument();
  });
});
