import { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import { useAdminStats, useAdminChartData } from '@/hooks/useKYC';
import { StatsCards, SecondaryStatsRow } from '@/components/admin/StatsCards';
import { Card, CardHeader } from '@/components/ui/Card';
import { LoadingState } from '@/components/ui/Spinner';
import { formatDate } from '@/utils/format';

// ─── Pie Chart ────────────────────────────────────────────────────────────────

const PIE_COLORS = {
  APPROVED:      '#22c55e',
  REJECTED:      '#ef4444',
  PENDING:       '#f59e0b',
  MANUAL_REVIEW: '#f97316',
  PROCESSING:    '#3b82f6',
};

function StatusPieChart({ stats }: { stats: ReturnType<typeof useAdminStats>['data'] }) {
  if (!stats) return <LoadingState />;

  const pieData = [
    { name: 'Approved',      value: stats.approved_count,      color: PIE_COLORS.APPROVED      },
    { name: 'Rejected',      value: stats.rejected_count,      color: PIE_COLORS.REJECTED      },
    { name: 'Pending',       value: stats.pending_count,        color: PIE_COLORS.PENDING       },
    { name: 'Manual Review', value: stats.manual_review_count, color: PIE_COLORS.MANUAL_REVIEW },
  ].filter((d) => d.value > 0);

  if (!pieData.length) {
    return (
      <div className="flex items-center justify-center h-48 text-neutral-400 text-sm">
        No data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie
          data={pieData}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={100}
          paddingAngle={3}
          dataKey="value"
          labelLine={false}
        >
          {pieData.map((entry, index) => (
            <Cell key={index} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          formatter={(value: number, name: string) => [value, name]}
          contentStyle={{
            borderRadius: '12px',
            border: '1px solid #e5e7eb',
            boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
          }}
        />
        <Legend
          iconType="circle"
          iconSize={8}
          formatter={(value) => (
            <span className="text-xs text-neutral-600">{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

// ─── Line Chart ───────────────────────────────────────────────────────────────

function SubmissionsLineChart({ data }: { data: unknown }) {
  const chartData = Array.isArray(data) ? data : [];

  if (!chartData.length) {
    return (
      <div className="flex items-center justify-center h-48 text-neutral-400 text-sm">
        No chart data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          tickFormatter={(v) => formatDate(v, 'MMM d')}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            borderRadius: '12px',
            border: '1px solid #e5e7eb',
            boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
            fontSize: '12px',
          }}
          labelFormatter={(v) => formatDate(v, 'MMM d, yyyy')}
        />
        <Line
          type="monotone"
          dataKey="total"
          name="Total"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: '#3b82f6' }}
        />
        <Line
          type="monotone"
          dataKey="approved"
          name="Approved"
          stroke="#22c55e"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: '#22c55e' }}
        />
        <Line
          type="monotone"
          dataKey="rejected"
          name="Rejected"
          stroke="#ef4444"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: '#ef4444' }}
        />
        <Legend
          iconType="circle"
          iconSize={8}
          formatter={(value) => (
            <span className="text-xs text-neutral-600">{value}</span>
          )}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const TIME_RANGES = [
  { label: '7d',  days: 7  },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
];

export function AdminDashboardPage() {
  const [chartDays, setChartDays] = useState(30);

  const { data: stats,     isLoading: statsLoading     } = useAdminStats();
  const { data: chartData, isLoading: chartDataLoading } = useAdminChartData(chartDays);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">Admin Dashboard</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Overview of KYC platform activity and submission statistics.
        </p>
      </div>

      {/* Stats cards */}
      <StatsCards stats={stats} isLoading={statsLoading} />

      {/* Secondary stats */}
      <SecondaryStatsRow stats={stats} />

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Line chart */}
        <Card className="lg:col-span-2">
          <CardHeader
            title="Submissions Over Time"
            subtitle="Daily submission volume and outcomes"
            action={
              <div className="flex gap-1">
                {TIME_RANGES.map((r) => (
                  <button
                    key={r.days}
                    onClick={() => setChartDays(r.days)}
                    className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-colors ${
                      chartDays === r.days
                        ? 'bg-primary-600 text-white'
                        : 'text-neutral-500 hover:bg-neutral-100'
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            }
          />
          {chartDataLoading ? (
            <LoadingState />
          ) : (
            <SubmissionsLineChart data={chartData} />
          )}
        </Card>

        {/* Pie chart */}
        <Card>
          <CardHeader
            title="Status Distribution"
            subtitle="Current breakdown by status"
          />
          {statsLoading ? (
            <LoadingState />
          ) : (
            <StatusPieChart stats={stats} />
          )}
        </Card>
      </div>

      {/* Recent activity placeholder */}
      <Card>
        <CardHeader
          title="Quick Actions"
          subtitle="Common admin tasks"
        />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { label: 'Review Pending Submissions',  href: '/admin/submissions?status=MANUAL_REVIEW', color: 'bg-orange-50 border-orange-200 text-orange-700' },
            { label: 'View All Submissions',         href: '/admin/submissions',                      color: 'bg-primary-50 border-primary-200 text-primary-700' },
            { label: 'Manage Users',                 href: '/admin/users',                            color: 'bg-neutral-50 border-neutral-200 text-neutral-700' },
          ].map((action) => (
            <a
              key={action.label}
              href={action.href}
              className={`flex items-center justify-center p-4 rounded-xl border text-sm font-medium hover:opacity-80 transition-opacity ${action.color}`}
            >
              {action.label}
            </a>
          ))}
        </div>
      </Card>
    </div>
  );
}
