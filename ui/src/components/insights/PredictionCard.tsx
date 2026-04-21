import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

interface PredictionCardProps {
  title: string;
  value: string;
  subtitle?: string;
  trend?: "up" | "down" | "stable";
  loading?: boolean;
}

export function PredictionCard({ title, value, subtitle, trend, loading }: PredictionCardProps) {
  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-4 animate-pulse">
        <div className="h-3 w-20 bg-muted rounded mb-2" />
        <div className="h-6 w-16 bg-muted rounded mb-1" />
        <div className="h-3 w-24 bg-muted rounded" />
      </div>
    );
  }

  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendColor = trend === "up" ? "text-red-500" : trend === "down" ? "text-green-500" : "text-muted-foreground";

  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="text-xs font-medium text-muted-foreground">{title}</p>
      <div className="flex items-center gap-2 mt-1">
        <p className="text-xl font-bold">{value}</p>
        {trend && <TrendIcon className={cn("h-4 w-4", trendColor)} />}
      </div>
      {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
    </div>
  );
}
