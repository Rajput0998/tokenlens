import { Database, TrendingUp, Brain } from "lucide-react";
import { cn } from "@/lib/utils";

type ColdStartState = "collecting" | "linear" | "full";

interface ColdStartBannerProps {
  state: ColdStartState;
}

const stateConfig = {
  collecting: {
    icon: Database,
    title: "Collecting Data",
    description: "TokenLens needs more usage data before predictions are available. Keep using your tools!",
    color: "border-orange-500/30 bg-orange-500/5",
    progress: 33,
  },
  linear: {
    icon: TrendingUp,
    title: "Linear Predictions Active",
    description: "Basic trend analysis is available. More data will unlock advanced ML predictions.",
    color: "border-blue-500/30 bg-blue-500/5",
    progress: 66,
  },
  full: {
    icon: Brain,
    title: "Full ML Active",
    description: "All prediction models are trained and providing insights.",
    color: "border-green-500/30 bg-green-500/5",
    progress: 100,
  },
};

export function ColdStartBanner({ state }: ColdStartBannerProps) {
  if (state === "full") return null;

  const config = stateConfig[state];
  const Icon = config.icon;

  return (
    <div className={cn("rounded-lg border p-4 flex items-start gap-3", config.color)}>
      <Icon className="h-5 w-5 mt-0.5 shrink-0 text-muted-foreground" />
      <div className="flex-1">
        <p className="font-medium text-sm">{config.title}</p>
        <p className="text-xs text-muted-foreground mt-1">{config.description}</p>
        <div className="mt-2 h-1.5 w-full bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all"
            style={{ width: `${config.progress}%` }}
          />
        </div>
      </div>
    </div>
  );
}
