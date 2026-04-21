import { UsageRingChart } from "./UsageRingChart";
import { BurnRateGauge } from "./BurnRateGauge";
import { ResetCountdown } from "./ResetCountdown";
import { MessageCounter } from "./MessageCounter";

interface StatsGridProps {
  readonly loading?: boolean;
}

export function StatsGrid({ loading }: StatsGridProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <UsageRingChart loading={loading} />
      <BurnRateGauge loading={loading} />
      <MessageCounter loading={loading} />
      <ResetCountdown loading={loading} />
    </div>
  );
}
