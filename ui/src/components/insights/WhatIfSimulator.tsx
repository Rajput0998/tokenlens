import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { InfoTooltip } from "../home/InfoTooltip";
import { Sliders } from "lucide-react";

interface SimulationResult {
  baseline_monthly_cost?: number;
  projected_monthly_cost?: number;
  cost_difference?: number;
  pct_change?: number;
  scenario?: Record<string, unknown>;
}

interface WhatIfSimulatorProps {
  loading?: boolean;
}

export function WhatIfSimulator({ loading }: WhatIfSimulatorProps) {
  const [contextSize, setContextSize] = useState(1.0);
  const [usageChange, setUsageChange] = useState(0);
  const [model, setModel] = useState("");

  const simulate = useMutation({
    mutationFn: (params: { context_size: number; usage_pct_change: number; model_switch: string | null }) =>
      apiFetch<SimulationResult>("/predictions/whatif", {
        method: "POST",
        body: JSON.stringify(params),
      }),
  });

  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-4 animate-pulse">
        <div className="h-4 w-32 bg-muted rounded mb-4" />
        <div className="space-y-3">
          <div className="h-8 bg-muted rounded" />
          <div className="h-8 bg-muted rounded" />
          <div className="h-8 bg-muted rounded" />
        </div>
      </div>
    );
  }

  const handleSimulate = () => {
    simulate.mutate({
      context_size: contextSize,
      usage_pct_change: usageChange / 100,
      model_switch: model || null,
    });
  };

  const result = simulate.data;
  const baselineCost = result?.baseline_monthly_cost ?? 0;
  const projectedCost = result?.projected_monthly_cost ?? 0;
  const costDiff = result?.cost_difference ?? 0;
  const pctChange = result?.pct_change ?? 0;

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2 mb-4">
        <Sliders className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">What-If Simulator</h3>
        <InfoTooltip
          title="What-If Simulator"
          description="Simulate how changes to your workflow would affect monthly costs. Adjust context size, usage volume, or switch models to see projected impact before making changes."
          tips={[
            "Context size 0.5 = halving your context (e.g., smaller files)",
            "Usage change -30% = reducing AI usage by 30%",
            "Switching from Opus to Haiku can save 95% on token costs",
            "Results are projections based on your current monthly spend",
          ]}
        />
      </div>

      <div className="space-y-4">
        <div>
          <label className="text-xs text-muted-foreground block mb-1">
            Context Size: {contextSize.toFixed(1)}x
          </label>
          <input
            type="range"
            min={0.1}
            max={3.0}
            step={0.1}
            value={contextSize}
            onChange={(e) => setContextSize(Number(e.target.value))}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground/50">
            <span>0.1x (minimal)</span>
            <span>1x (current)</span>
            <span>3x (large)</span>
          </div>
        </div>

        <div>
          <label className="text-xs text-muted-foreground block mb-1">
            Usage Change: {usageChange > 0 ? "+" : ""}{usageChange}%
          </label>
          <input
            type="range"
            min={-50}
            max={100}
            value={usageChange}
            onChange={(e) => setUsageChange(Number(e.target.value))}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground/50">
            <span>-50% less</span>
            <span>No change</span>
            <span>+100% more</span>
          </div>
        </div>

        <div>
          <label className="text-xs text-muted-foreground block mb-1">Switch Model (optional)</label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full rounded border bg-background px-2 py-1.5 text-sm"
          >
            <option value="">Keep current model</option>
            <option value="claude-sonnet-4">Claude Sonnet 4 ($3/M in)</option>
            <option value="claude-haiku-3.5">Claude Haiku 3.5 ($0.80/M in)</option>
            <option value="claude-opus-4">Claude Opus 4 ($15/M in)</option>
          </select>
        </div>

        <button
          onClick={handleSimulate}
          disabled={simulate.isPending}
          className="w-full rounded bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {simulate.isPending ? "Simulating..." : "Run Simulation"}
        </button>

        {simulate.isError && (
          <div className="p-3 rounded bg-destructive/10 border border-destructive/20 text-sm text-destructive">
            Simulation failed. Not enough usage data to project costs.
          </div>
        )}

        {result && !simulate.isError && (
          <div className="mt-3 p-3 rounded bg-muted/50 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Current monthly</span>
              <span className="font-medium tabular-nums">${baselineCost.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Projected monthly</span>
              <span className="font-bold tabular-nums">${projectedCost.toFixed(2)}</span>
            </div>
            <div className="border-t pt-2 flex justify-between text-sm">
              <span className="text-muted-foreground">Difference</span>
              <span className={`font-bold tabular-nums ${costDiff < 0 ? "text-green-500" : costDiff > 0 ? "text-red-500" : ""}`}>
                {costDiff >= 0 ? "+" : ""}${costDiff.toFixed(2)} ({pctChange >= 0 ? "+" : ""}{pctChange.toFixed(1)}%)
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
