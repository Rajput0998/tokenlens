import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SessionList } from "./SessionList";
import type { SessionData } from "./SessionList";

const mockSessions: SessionData[] = [
  {
    id: "abc12345-6789-0000-0000-000000000001",
    tool: "claude_code",
    startTime: "14:30",
    duration: "12m",
    totalTokens: 4200,
    turns: [
      { turnNumber: 1, inputTokens: 1000, outputTokens: 500, contextSize: 1000, cacheHit: false },
      { turnNumber: 2, inputTokens: 1500, outputTokens: 700, contextSize: 2500, cacheHit: true },
      { turnNumber: 3, inputTokens: 300, outputTokens: 200, contextSize: 3000, cacheHit: true },
    ],
    cacheRatio: 0.67,
  },
];

describe("SessionList", () => {
  it("renders loading state", () => {
    const { container } = render(<SessionList sessions={[]} loading />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(<SessionList sessions={[]} />);
    expect(screen.getByText("No sessions recorded yet.")).toBeInTheDocument();
  });

  it("renders session rows", () => {
    render(<SessionList sessions={mockSessions} />);
    expect(screen.getByText("claude_code")).toBeInTheDocument();
    expect(screen.getByText("4,200")).toBeInTheDocument();
    expect(screen.getByText("67%")).toBeInTheDocument();
  });

  it("expands row to show turn breakdown", () => {
    render(<SessionList sessions={mockSessions} />);

    // Click to expand
    fireEvent.click(screen.getByText("claude_code"));

    // Should show turn details
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("#2")).toBeInTheDocument();
    expect(screen.getByText("#3")).toBeInTheDocument();
    expect(screen.getAllByText("1,000").length).toBeGreaterThan(0);
  });
});
