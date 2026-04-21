import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TimePeriodSelector } from "./TimePeriodSelector";

describe("TimePeriodSelector", () => {
  it("renders all period options", () => {
    render(<TimePeriodSelector value="24h" onChange={() => {}} />);
    expect(screen.getByText("24h")).toBeInTheDocument();
    expect(screen.getByText("7d")).toBeInTheDocument();
    expect(screen.getByText("30d")).toBeInTheDocument();
  });

  it("marks the active period as selected", () => {
    render(<TimePeriodSelector value="7d" onChange={() => {}} />);
    expect(screen.getByText("7d")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("24h")).toHaveAttribute("aria-selected", "false");
  });

  it("calls onChange when a period is clicked", () => {
    const onChange = vi.fn();
    render(<TimePeriodSelector value="24h" onChange={onChange} />);
    fireEvent.click(screen.getByText("30d"));
    expect(onChange).toHaveBeenCalledWith("30d");
  });
});
