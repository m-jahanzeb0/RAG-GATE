export interface AnalyticsData {
  total_requests_30_days: number;
  current_day_usage: number;
  quota_limit: number;
  provider_distribution: Record<string, number>;
  usage_history_7_days: Array<{
    date: string;
    count: number;
  }>;
}

export interface UsageDay {
  date: string;
  count: number;
}

export interface ProviderEntry {
  name: string;
  value: number;
  color: string;
}