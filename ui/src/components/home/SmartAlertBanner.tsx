import { Zap, AlertTriangle, Info } from "lucide-react";
import { cn } from "@/lib/utils";

export interface AlertInfo {
  type: "warning" | "critical" | "info";
  message: string;
}

interface SmartAlertBannerProps {
  alert: AlertInfo | null;
  loading?: boolean;
}

const alertStyles = {
  warning: {
    border: "border-l-[var(--orange)]",
    bg: "bg-orange-dim",
    icon: AlertTriangle,
    iconColor: "text-accent-orange",
    textColor: "text-accent-orange",
  },
  critical: {
    border: "border-l-[var(--red)]",
    bg: "bg-red-dim",
    icon: Zap,
    iconColor: "text-accent-red",
    textColor: "text-accent-red",
  },
  info: {
    border: "border-l-[var(--blue)]",
    bg: "bg-blue-dim",
    icon: Info,
    iconColor: "text-accent-blue",
    textColor: "text-accent-blue",
  },
};

export function SmartAlertBanner({ alert, loading }: SmartAlertBannerProps) {
  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-3 animate-pulse shadow-card">
        <div className="h-4 w-64 bg-muted rounded" />
      </div>
    );
  }

  if (!alert) return null;

  const style = alertStyles[alert.type];
  const Icon = style.icon;

  return (
    <div className={cn(
      "rounded-xl border-l-[3px] border bg-card p-4 flex items-center gap-3 shadow-card",
      style.border, style.bg
    )}>
      <Icon className={cn("h-4 w-4 shrink-0", style.iconColor)} />
      <p className={cn("text-sm font-semibold", style.textColor)}>{alert.message}</p>
    </div>
  );
}
