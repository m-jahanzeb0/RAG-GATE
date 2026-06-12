import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { PieChart as PieChartIcon } from 'lucide-react';
import type { AnalyticsData } from '../types/analytics';

interface ProviderChartProps {
  data: AnalyticsData['provider_distribution'];
}

const PROVIDER_COLORS: Record<string, string> = {
  openai: '#5e9eff',
  anthropic: '#a78bfa',
  'openai-compatible': '#22d3ee',
};

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  'openai-compatible': 'OpenAI Compatible',
};

export default function ProviderChart({ data }: ProviderChartProps) {
  const entries = Object.entries(data).map(([name, value]) => ({
    name: PROVIDER_LABELS[name] || name,
    value,
    color: PROVIDER_COLORS[name] || '#6366f1',
  }));

  return (
    <div className="glass-card p-6">
      <div className="flex items-center gap-2 mb-6">
        <PieChartIcon className="w-5 h-5 text-accent-purple" />
        <h3 className="text-sm font-medium text-gray-300">Provider Distribution</h3>
      </div>

      {entries.length === 0 ? (
        <div className="flex items-center justify-center h-48 text-gray-500 text-sm">
          No provider data available yet
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4">
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={entries}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={90}
                paddingAngle={3}
                dataKey="value"
                stroke="none"
              >
                {entries.map((entry, index) => (
                  <Cell key={index} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: 'rgba(18, 18, 26, 0.95)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '12px',
                  backdropFilter: 'blur(24px)',
                  boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
                  fontSize: '13px',
                }}
                formatter={(value: number, name: string) => [value, name]}
              />
            </PieChart>
          </ResponsiveContainer>

          <div className="flex flex-wrap justify-center gap-4">
            {entries.map((entry) => (
              <div key={entry.name} className="flex items-center gap-2 text-xs text-gray-400">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: entry.color }}
                />
                <span>{entry.name}</span>
                <span className="text-gray-500">{entry.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}