import { Activity, Calendar, Gauge } from 'lucide-react';
import type { AnalyticsData } from '../types/analytics';

interface HeroMetricsProps {
  data: AnalyticsData;
}

function MetricCard({
  icon,
  label,
  value,
  subtext,
  progress,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  subtext?: string;
  progress?: number;
}) {
  return (
    <div className="glass-card p-6 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-gray-400">
          {icon}
          <span className="stat-label">{label}</span>
        </div>
      </div>
      <div className="stat-value">{value}</div>
      {subtext && <p className="text-xs text-gray-500">{subtext}</p>}
      {progress !== undefined && (
        <div className="mt-1">
          <div className="flex justify-between text-xs text-gray-400 mb-1.5">
            <span>Used</span>
            <span>{Math.round(progress * 100)}%</span>
          </div>
          <div className="h-1.5 bg-glass-heavy rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${Math.min(progress * 100, 100)}%`,
                background: progress >= 0.9
                  ? 'linear-gradient(90deg, #fb7185, #f43f5e)'
                  : 'linear-gradient(90deg, #5e9eff, #a78bfa)',
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default function HeroMetrics({ data }: HeroMetricsProps) {
  const progress = data.current_day_usage / data.quota_limit;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <MetricCard
        icon={<Activity className="w-4 h-4" />}
        label="Today's Usage"
        value={data.current_day_usage}
        subtext={`out of ${data.quota_limit} daily requests`}
        progress={progress}
      />
      <MetricCard
        icon={<Calendar className="w-4 h-4" />}
        label="Last 30 Days"
        value={data.total_requests_30_days.toLocaleString()}
        subtext="total API requests"
      />
      <MetricCard
        icon={<Gauge className="w-4 h-4" />}
        label="Quota Remaining"
        value={Math.max(0, data.quota_limit - data.current_day_usage)}
        subtext={`of ${data.quota_limit} daily limit`}
        progress={1 - progress}
      />
    </div>
  );
}