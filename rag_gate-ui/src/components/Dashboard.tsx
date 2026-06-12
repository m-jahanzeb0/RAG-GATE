import { useEffect, useState, useCallback } from 'react';
import { LogOut, RefreshCw, Cpu } from 'lucide-react';
import { fetchAnalytics, clearApiKey } from '../api/client';
import type { AnalyticsData } from '../types/analytics';
import HeroMetrics from './HeroMetrics';
import UsageChart from './UsageChart';
import ProviderChart from './ProviderChart';

interface DashboardProps {
  onLogout: () => void;
}

export default function Dashboard({ onLogout }: DashboardProps) {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');

    try {
      const result = await fetchAnalytics();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = () => loadData(true);
  const handleLogout = () => {
    clearApiKey();
    onLogout();
  };

  return (
    <div className="min-h-screen p-4 md:p-8">
      {/* Header */}
      <header className="max-w-6xl mx-auto mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-accent-blue/15 backdrop-blur-xl border border-accent-blue/20 flex items-center justify-center">
              <Cpu className="w-5 h-5 text-accent-blue" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white">RAG-Gate</h1>
              <p className="text-xs text-gray-500">AI Gateway Dashboard</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="glass-card-sm p-2.5 hover:bg-glass-heavy transition-colors disabled:opacity-40"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 text-gray-400 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={handleLogout}
              className="glass-card-sm p-2.5 hover:bg-glass-heavy transition-colors"
              title="Disconnect"
            >
              <LogOut className="w-4 h-4 text-gray-400" />
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-6xl mx-auto space-y-6">
        {loading && !data ? (
          <div className="flex items-center justify-center h-64">
            <div className="flex items-center gap-3 text-gray-400">
              <span className="w-5 h-5 border-2 border-accent-blue/30 border-t-accent-blue rounded-full animate-spin" />
              Loading dashboard...
            </div>
          </div>
        ) : error ? (
          <div className="glass-card p-8 text-center">
            <p className="text-accent-rose mb-4">{error}</p>
            <button onClick={handleRefresh} className="glass-button text-sm">
              Retry
            </button>
          </div>
        ) : data ? (
          <>
            <HeroMetrics data={data} />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <UsageChart data={data.usage_history_7_days} />
              <ProviderChart data={data.provider_distribution} />
            </div>
          </>
        ) : null}
      </main>
    </div>
  );
}