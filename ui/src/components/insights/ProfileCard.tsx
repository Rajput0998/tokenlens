import { User } from "lucide-react";
import type { BehavioralProfile } from "@/stores/useMLStore";
import { InfoTooltip } from "../home/InfoTooltip";

interface ProfileCardProps {
  profile: BehavioralProfile | null;
  loading?: boolean;
}

export function ProfileCard({ profile, loading }: ProfileCardProps) {
  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-4 animate-pulse">
        <div className="h-4 w-24 bg-muted rounded mb-3" />
        <div className="space-y-2">
          <div className="h-3 w-full bg-muted rounded" />
          <div className="h-3 w-3/4 bg-muted rounded" />
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="rounded-lg border bg-card p-4 text-center">
        <p className="text-sm text-muted-foreground">Profile not yet available.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <User className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-medium">Your Profile</h3>
        <InfoTooltip
          title="Your Coding Profile"
          description="A behavioral analysis of how you use AI tools. Shows your peak activity hours, average session length, preferred models, and overall efficiency. Built from your last 7 days of usage data."
          tips={[
            "Peak hours help you plan when to tackle complex tasks",
            "Short avg sessions with high efficiency = optimal workflow",
            "Preferred models show which AI you rely on most",
            "Profile updates automatically as your patterns change",
          ]}
        />
      </div>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Peak hours</span>
          <span className="font-medium">
            {profile.peakHours.map((h) => `${h}:00`).join(", ")}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Avg session</span>
          <span className="font-medium">{profile.avgSessionLength} min</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Preferred models</span>
          <span className="font-medium">{profile.preferredModels.join(", ")}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Efficiency</span>
          <span className="font-medium">{profile.efficiencyScore}/100</span>
        </div>
      </div>
    </div>
  );
}
