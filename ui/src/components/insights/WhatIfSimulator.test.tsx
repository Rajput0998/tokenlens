import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { WhatIfSimulator } from "./WhatIfSimulator";

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe("WhatIfSimulator", () => {
  it("renders loading state", () => {
    const { container } = renderWithProviders(<WhatIfSimulator loading />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders simulator controls", () => {
    renderWithProviders(<WhatIfSimulator />);
    expect(screen.getByText("What-If Simulator")).toBeInTheDocument();
    expect(screen.getByText("Run Simulation")).toBeInTheDocument();
    expect(screen.getByText(/Context Size/)).toBeInTheDocument();
    expect(screen.getByText(/Usage Change/)).toBeInTheDocument();
    expect(screen.getByText("Model")).toBeInTheDocument();
  });

  it("renders model dropdown with options", () => {
    renderWithProviders(<WhatIfSimulator />);
    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
  });
});
