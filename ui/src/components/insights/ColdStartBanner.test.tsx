import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ColdStartBanner } from "./ColdStartBanner";

describe("ColdStartBanner", () => {
  it("renders collecting state", () => {
    render(<ColdStartBanner state="collecting" />);
    expect(screen.getByText("Collecting Data")).toBeInTheDocument();
    expect(screen.getByText(/needs more usage data/)).toBeInTheDocument();
  });

  it("renders linear state", () => {
    render(<ColdStartBanner state="linear" />);
    expect(screen.getByText("Linear Predictions Active")).toBeInTheDocument();
    expect(screen.getByText(/Basic trend analysis/)).toBeInTheDocument();
  });

  it("renders nothing for full state", () => {
    const { container } = render(<ColdStartBanner state="full" />);
    expect(container.firstChild).toBeNull();
  });
});
