import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { BarChart3 } from 'lucide-react';
import type { UsageDay } from '../types/analytics';

interface UsageChartProps {
  data: UsageDay[];
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export default function UsageChart({ data }: UsageChartProps) {
  return (
    <div className="glass-card p-6">
      <div className="flex items-center gap-2 mb-6">
        <BarChart3 className="w-5 h-5 text-accent-cyan" />
        <h3 className="text-sm font-medium text-gray-300">Usage History (7 Days)</h3>
      </div>

      {data.length === 0 ? (
        <div className="flex items-center justify-center h-48 text-gray-500 text-sm">
          No usage data available yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={data} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              tick={{ fill: '#9ca3af', fontSize: 11 }}
              axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#9ca3af', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              allowDecimals={false}
            />
            <Tooltip
              contentStyle={{
                background: 'rgba(18, 18, 26, 0.95)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '12px',
                backdropFilter: 'blur(24px)',
                boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
              }}
              labelFormatter={formatDate}
              formatter={(value: number) => [value, 'Requests']}
              cursor={{ fill: 'rgba(255,255,255,0.03)' }}
            />
            <Bar
              dataKey="count"
              radius={[6, 6, 0, 0]}
              maxBarSize={40}
              fill="url(#barGradient)"
            />
            <defs>
              <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#5e9eff" stopOpacity={0.9} />
                <stop offset="100%" stopColor="#a78bfa" stopOpacity={0.6} />
              </linearGradient>
            </defs>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}