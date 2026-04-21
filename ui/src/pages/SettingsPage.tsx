import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useSettingsStore } from "@/stores/useSettingsStore";
import { apiFetch } from "@/lib/api";
import { Save, RefreshCw, Shield, Bell, Cpu, DollarSign, Database, Info, Zap } from "lucide-react";
import { InfoTooltip } from "@/components/home/InfoTooltip";

const PLAN_OPTIONS = [
  { value: "pro", label: "Pro", tokens: "19,000", cost: "$18/mo", desc: "Basic Claude subscription" },
  { value: "max5", label: "Max 5", tokens: "88,000", cost: "$35/mo", desc: "5-hour extended sessions" },
  { value: "max20", label: "Max 20", tokens: "220,000", cost: "$140/mo", desc: "20-hour heavy usage" },
  { value: "custom", label: "Custom", tokens: "Custom", cost: "Custom", desc: "Set your own limits" },
];

const MODEL_PRICING = [
  { model: "Claude Opus 4", input: 15.0, output: 75.0, cache_creation: 18.75, cache_read: 1.5, tier: "Premium" },
  { model: "Claude Sonnet 4", input: 3.0, output: 15.0, cache_creation: 3.75, cache_read: 0.3, tier: "Balanced" },
  { model: "Claude Haiku 3.5", input: 0.80, output: 4.0, cache_creation: 1.0, cache_read: 0.08, tier: "Fast" },
  { model: "Kiro Auto", input: 3.0, output: 15.0, cache_creation: 3.75, cache_read: 0.3, tier: "Default" },
];

export function SettingsPage() {
  const settings = useSettingsStore();
  const [plan, setPlan] = useState(settings.planType);
  const [dailyLimit, setDailyLimit] = useState(settings.dailyTokenLimit);
  const [monthlyBudget, setMonthlyBudget] = useState(settings.monthlyCostBudget);
  const [thresholds, setThresholds] = useState(settings.alertThresholds.join(", "));
  const [saved, setSaved] = useState(false);

  const adapters = useQuery({
    queryKey: ["settings", "adapters"],
    queryFn: () => apiFetch<Array<{ name: string; enabled: boolean; available: boolean }>>("/settings/adapters"),
  });

  useEffect(() => {
    settings.loadSettings();
  }, []);

  useEffect(() => {
    setDailyLimit(settings.dailyTokenLimit);
    setMonthlyBudget(settings.monthlyCostBudget);
    setThresholds(settings.alertThresholds.join(", "));
    setPlan(settings.planType);
  }, [settings.dailyTokenLimit, settings.monthlyCostBudget, settings.alertThresholds, settings.planType]);

  useEffect(() => {
    if (plan === "pro") { setDailyLimit(19000); setMonthlyBudget(18); }
    else if (plan === "max5") { setDailyLimit(88000); setMonthlyBudget(35); }
    else if (plan === "max20") { setDailyLimit(220000); setMonthlyBudget(140); }
  }, [plan]);

  const saveMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiFetch("/settings", { method: "PUT", body: JSON.stringify({ settings: data }) }),
    onSuccess: () => {
      settings.updateSettings({
        dailyTokenLimit: dailyLimit,
        monthlyCostBudget: monthlyBudget,
        planType: plan,
        alertThresholds: thresholds.split(",").map((s) => Number(s.trim())).filter(Boolean),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const handleSave = () => {
    saveMutation.mutate({
      "alerts.thresholds.daily_token_limit": dailyLimit,
      "alerts.thresholds.monthly_cost_budget": monthlyBudget,
      "plan.type": plan,
    });
  };

  const adapterList = Array.isArray(adapters.data) ? adapters.data : [];

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Settings</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors shadow-sm"
          >
            {saveMutation.isPending ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save
          </button>
          {saved && <span className="text-sm text-green-500 font-medium">✓ Saved</span>}
          {saveMutation.isError && (
            <span className="text-sm text-destructive">Failed to save</span>
          )}
        </div>
      </div>

      {/* Plan Selection */}
      <section className="rounded-lg border bg-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-primary" />
          <h2 className="font-semibold">Subscription Plan</h2>
          <InfoTooltip
            title="Subscription Plan"
            description="Select your Claude subscription plan to set accurate daily token limits and monthly cost budgets. Limits auto-adjust when you change plans. Choose 'Custom' to set your own values."
            tips={[
              "Pro: 19K tokens/day, good for light coding",
              "Max 5: 88K tokens/day, for regular development",
              "Max 20: 220K tokens/day, for heavy AI-assisted coding",
              "Custom: set any limit you want",
            ]}
          />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {PLAN_OPTIONS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPlan(p.value)}
              className={`rounded-lg border-2 p-3 text-left transition-all ${
                plan === p.value
                  ? "border-primary bg-primary/5 shadow-sm"
                  : "border-transparent bg-muted/30 hover:bg-muted/50"
              }`}
            >
              <p className="font-semibold text-sm">{p.label}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{p.tokens} tokens/day</p>
              <p className="text-xs text-muted-foreground">{p.cost}</p>
            </button>
          ))}
        </div>
      </section>

      {/* Budget Limits */}
      <section className="rounded-lg border bg-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <DollarSign className="h-4 w-4 text-primary" />
          <h2 className="font-semibold">Budget Limits</h2>
          <InfoTooltip
            title="Budget Limits"
            description="Set your daily token limit and monthly cost budget. Alerts fire at the threshold percentages below when you approach these limits. Auto-set when you select a plan above."
            tips={[
              "Daily limit controls when you get usage warnings",
              "Monthly budget tracks your total spend across the month",
              "These values feed into the Home page ring chart and Insights predictions",
            ]}
          />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1.5">
              Daily Token Limit
            </label>
            <input
              type="number"
              value={dailyLimit}
              onChange={(e) => setDailyLimit(Number(e.target.value))}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm tabular-nums"
            />
            <p className="text-[10px] text-muted-foreground mt-1">
              {dailyLimit.toLocaleString()} tokens per day
            </p>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1.5">
              Monthly Cost Budget
            </label>
            <div className="relative">
              <span className="absolute left-3 top-2 text-sm text-muted-foreground">$</span>
              <input
                type="number"
                step="0.01"
                value={monthlyBudget}
                onChange={(e) => setMonthlyBudget(Number(e.target.value))}
                className="w-full rounded-lg border bg-background pl-7 pr-3 py-2 text-sm tabular-nums"
              />
            </div>
            <p className="text-[10px] text-muted-foreground mt-1">
              ~${(monthlyBudget / 30).toFixed(2)}/day budget
            </p>
          </div>
        </div>
      </section>

      {/* Alert Thresholds */}
      <section className="rounded-lg border bg-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Bell className="h-4 w-4 text-primary" />
          <h2 className="font-semibold">Alert Thresholds</h2>
          <InfoTooltip
            title="Alert Thresholds"
            description="Percentages of your daily limit at which you receive warnings. At 50% and 75% you get 'warning' alerts, at 90% and 100% you get 'critical' alerts. Alerts are deduped — you won't get the same alert twice in 24 hours."
            tips={[
              "Default: 50, 75, 90, 100 covers most use cases",
              "Remove 50 if you don't want early warnings",
              "Add 25 for very early heads-up",
              "Alerts show on the Home page and via desktop notifications",
            ]}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground block mb-1.5">
            Warning percentages (comma-separated)
          </label>
          <input
            type="text"
            value={thresholds}
            onChange={(e) => setThresholds(e.target.value)}
            placeholder="50, 75, 90, 100"
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
          />
          {/* Visual preview */}
          <div className="flex gap-1 mt-2">
            {thresholds.split(",").map((t) => {
              const pct = Number(t.trim());
              if (!pct || pct <= 0 || pct > 100) return null;
              return (
                <div
                  key={pct}
                  className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                    pct >= 90 ? "bg-red-500/10 text-red-500" : pct >= 75 ? "bg-orange-500/10 text-orange-500" : "bg-blue-500/10 text-blue-500"
                  }`}
                >
                  {pct}%
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Tool Configuration */}
      <section className="rounded-lg border bg-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Cpu className="h-4 w-4 text-primary" />
          <h2 className="font-semibold">Tool Configuration</h2>
          <InfoTooltip
            title="Tool Configuration"
            description="Shows which AI tool adapters are registered and whether they can find log files on your system. 'Available' means log files were found. The daemon parses these logs to track token usage."
            tips={[
              "Claude Code: reads ~/.claude/projects/*.jsonl",
              "Kiro: tracked via MCP server (no log files needed)",
              "Run 'tokenlens init' to configure adapters",
              "Green = active and tracking, Gray = configured but no logs found",
            ]}
          />
        </div>
        {adapters.isLoading ? (
          <div className="space-y-2">
            {[1, 2].map((i) => (
              <div key={i} className="h-12 bg-muted rounded-lg animate-pulse" />
            ))}
          </div>
        ) : adapterList.length === 0 ? (
          <div className="p-4 rounded-lg bg-muted/30 text-center">
            <Cpu className="h-6 w-6 mx-auto text-muted-foreground/30 mb-2" />
            <p className="text-sm text-muted-foreground">No adapters found</p>
            <p className="text-xs text-muted-foreground/70 mt-1">
              Run <code className="bg-muted px-1.5 py-0.5 rounded text-xs">tokenlens init</code> to configure
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {adapterList.map((adapter) => (
              <div key={adapter.name} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                <div className="flex items-center gap-3">
                  <div className={`h-2.5 w-2.5 rounded-full ${adapter.available ? "bg-green-500" : "bg-muted-foreground/30"}`} />
                  <div>
                    <span className="text-sm font-medium capitalize">{adapter.name.replace("_", " ")}</span>
                    <p className="text-[10px] text-muted-foreground">
                      {adapter.available ? "Log files found — tracking active" : "No log files found"}
                    </p>
                  </div>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  adapter.enabled ? "bg-green-500/10 text-green-500" : "bg-muted text-muted-foreground"
                }`}>
                  {adapter.enabled ? "Enabled" : "Disabled"}
                </span>
              </div>
            ))}
            {/* MCP Server status */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="h-2.5 w-2.5 rounded-full bg-green-500" />
                <div>
                  <span className="text-sm font-medium">Kiro MCP Server</span>
                  <p className="text-[10px] text-muted-foreground">
                    Logs via MCP tool calls — no file parsing needed
                  </p>
                </div>
              </div>
              <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/10 text-green-500">
                Active
              </span>
            </div>
          </div>
        )}
      </section>

      {/* Model Pricing */}
      <section className="rounded-lg border bg-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-primary" />
          <h2 className="font-semibold">Model Pricing</h2>
          <InfoTooltip
            title="Model Pricing"
            description="Per-model token pricing used for cost calculations. Prices are in USD per million tokens. Cache creation costs 1.25× the input rate, cache read costs 0.1× the input rate. Override in ~/.tokenlens/config.toml."
            tips={[
              "Opus is 5× more expensive than Sonnet for input",
              "Haiku is 3.75× cheaper than Sonnet — use for simple tasks",
              "Cache read tokens are very cheap — high cache hit rate saves money",
              "Prices are from Anthropic's published rates",
            ]}
          />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-muted-foreground border-b">
                <th className="text-left py-2 pr-4">Model</th>
                <th className="text-left py-2 pr-4">Tier</th>
                <th className="text-right py-2 pr-4">Input</th>
                <th className="text-right py-2 pr-4">Output</th>
                <th className="text-right py-2 pr-4">Cache Write</th>
                <th className="text-right py-2">Cache Read</th>
              </tr>
            </thead>
            <tbody>
              {MODEL_PRICING.map((m) => (
                <tr key={m.model} className="border-b border-muted/50 last:border-0">
                  <td className="py-2.5 pr-4 font-medium">{m.model}</td>
                  <td className="py-2.5 pr-4">
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                      m.tier === "Premium" ? "bg-purple-500/10 text-purple-500" :
                      m.tier === "Balanced" ? "bg-blue-500/10 text-blue-500" :
                      m.tier === "Fast" ? "bg-green-500/10 text-green-500" :
                      "bg-muted text-muted-foreground"
                    }`}>
                      {m.tier}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">${m.input.toFixed(2)}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">${m.output.toFixed(2)}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">${m.cache_creation.toFixed(2)}</td>
                  <td className="py-2.5 text-right tabular-nums">${m.cache_read.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[10px] text-muted-foreground mt-2">
            Prices in USD per million tokens. Override in <code className="bg-muted px-1 rounded">~/.tokenlens/config.toml</code>
          </p>
        </div>
      </section>

      {/* Data Management */}
      <section className="rounded-lg border bg-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-primary" />
          <h2 className="font-semibold">Data Management</h2>
          <InfoTooltip
            title="Data Management"
            description="Manage your TokenLens database. Archive moves old data to a backup file. Prune permanently deletes data older than a specified number of days. Use these to keep the database small and fast."
            tips={[
              "Archive before pruning to keep a backup",
              "Prune data older than 90 days for optimal performance",
              "Database location: ~/.tokenlens/tokenlens.db",
            ]}
          />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="p-3 rounded-lg bg-muted/30">
            <p className="text-sm font-medium">Archive Data</p>
            <p className="text-xs text-muted-foreground mt-0.5">Export old data to backup file</p>
            <code className="text-xs bg-muted px-2 py-1 rounded block mt-2">tokenlens data archive</code>
          </div>
          <div className="p-3 rounded-lg bg-muted/30">
            <p className="text-sm font-medium">Prune Data</p>
            <p className="text-xs text-muted-foreground mt-0.5">Delete data older than N days</p>
            <code className="text-xs bg-muted px-2 py-1 rounded block mt-2">tokenlens data prune --days 90</code>
          </div>
        </div>
      </section>

      {/* About */}
      <section className="rounded-lg border bg-card p-5">
        <div className="flex items-center gap-2 mb-2">
          <Info className="h-4 w-4 text-primary" />
          <h2 className="font-semibold">About</h2>
        </div>
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">TokenLens</span> — AI Token Usage Intelligence Platform
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          Settings saved via this page are stored in the database. Config file: <code className="bg-muted px-1 rounded">~/.tokenlens/config.toml</code>
        </p>
      </section>
    </div>
  );
}
