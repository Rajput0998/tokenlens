import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SmartAlertBanner } from "./SmartAlertBanner";

describe("SmartAlertBanner", () => {
  it("renders nothing when no alert", () => {
    const { container } = render(<SmartAlertBanner alert={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders loading state", () => {
    const { container } = render(<SmartAlertBanner alert={null} loading />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders warning alert", () => {
    render(
      <SmartAlertBanner alert={{ type: "warning", message: "75% of daily limit used" }} />
    );
    expect(screen.getByText("75% of daily limit used")).toBeInTheDocument();
  });

  it("renders critical alert", () => {
    render(
      <SmartAlertBanner alert={{ type: "critical", message: "Critical burn rate" }} />
    );
    expect(screen.getByText("Critical burn rate")).toBeInTheDocument();
  });

  it("renders info alert", () => {
    render(
      <SmartAlertBanner alert={{ type: "info", message: "Connecting..." }} />
    );
    expect(screen.getByText("Connecting...")).toBeInTheDocument();
  });
});
