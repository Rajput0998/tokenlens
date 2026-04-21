import { cn } from "@/lib/utils";

export type TimePeriod = "24h" | "7d" | "30d";

interface TimePeriodSelectorProps {
  value: TimePeriod;
  onChange: (period: TimePeriod) => void;
}

const periods: { value: TimePeriod; label: string }[] = [
  { value: "24h", label: "24h" },
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
];

export function TimePeriodSelector({ value, onChange }: TimePeriodSelectorProps) {
  return (
    <div className="inline-flex rounded-md border bg-muted p-1" role="tablist">
      {periods.map((period) => (
        <button
          key={period.value}
          role="tab"
          aria-selected={value === period.value}
          onClick={() => onChange(period.value)}
          className={cn(
            "px-3 py-1.5 text-sm font-medium rounded transition-colors",
            value === period.value
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {period.label}
        </button>
      ))}
    </div>
  );
}
