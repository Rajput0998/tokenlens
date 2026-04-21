import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SettingsPage } from "./SettingsPage";
import { useSettingsStore } from "@/stores/useSettingsStore";

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe("SettingsPage", () => {
  beforeEach(() => {
    useSettingsStore.setState({
      dailyTokenLimit: 500000,
      monthlyCostBudget: 50,
      alertThresholds: [50, 75, 90, 100],
      adapters: [],
      webhooks: [],
    });
  });

  it("renders all settings sections", () => {
    renderWithProviders(<SettingsPage />);
    expect(screen.getByText("Budget Limits")).toBeInTheDocument();
    expect(screen.getByText("Alert Thresholds")).toBeInTheDocument();
    expect(screen.getByText("Tool Configuration")).toBeInTheDocument();
    expect(screen.getByText("Model Pricing")).toBeInTheDocument();
    expect(screen.getByText("Data Management")).toBeInTheDocument();
    expect(screen.getByText("About")).toBeInTheDocument();
  });

  it("renders save button", () => {
    renderWithProviders(<SettingsPage />);
    expect(screen.getByText("Save Settings")).toBeInTheDocument();
  });

  it("shows adapter empty state when no adapters configured", () => {
    renderWithProviders(<SettingsPage />);
    expect(screen.getByText(/No adapters configured/)).toBeInTheDocument();
  });

  it("shows adapters when configured", () => {
    useSettingsStore.setState({
      adapters: [{ name: "claude_code", enabled: true, logPath: "/tmp/log" }],
    });
    renderWithProviders(<SettingsPage />);
    expect(screen.getByText("claude_code")).toBeInTheDocument();
    expect(screen.getByText("Enabled")).toBeInTheDocument();
  });
});
