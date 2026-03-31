import { useState } from 'react';
import {
  BarChart,
  Bar,
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
import { useAdminStats } from '@/hooks/useKYC';
import { Card, CardHeader } from '@/components/ui/Card';
import { LoadingState } from '@/components/ui/Spinner';

const COLORS = {
  approved:     '#22c55e',
  rejected:     '#ef4444',
  pending:      '#f59e0b',
  manual_review:'#f97316',
  processing:   '#3b82f6',
};

export function AdminAnalyticsPage() {
  const { data: stats, isLoading } = useAdminStats();

  const statusData = stats
    ? [
        { name: 'Approved',      value: stats.approved_count,      fill: COLORS.approved      },
        { name: 'Rejected',      value: stats.rejected_count,      fill: COLORS.rejected      },
        { name: 'Pending',       value: stats.pending_count,        fill: COLORS.pending       },
        { name: 'Manual Review', value: stats.manual_review_count, fill: COLORS.manual_review },
      ].filter((d) => d.value > 0)
    : [];

  const rateData = stats
    ? [
        { name: 'Approved', value: stats.approved_count },
        { name: 'Rejected', value: stats.rejected_count },
        { name: 'In Progress', value: stats.pending_count + stats.manual_review_count },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">Analytics</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Insights and trends across all KYC submissions.
        </p>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : (
        <>
          {/* Summary metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'Total Submissions', value: stats?.total_submissions ?? 0, color: 'text-primary-700 bg-primary-50 border-primary-200' },
              { label: 'Approved',           value: stats?.approved_count      ?? 0, color: 'text-success-700 bg-success-50 border-success-200' },
              { label: 'Rejected',           value: stats?.rejected_count      ?? 0, color: 'text-danger-700  bg-danger-50  border-danger-200'  },
              { label: 'Pending Review',     value: (stats?.pending_count ?? 0) + (stats?.manual_review_count ?? 0), color: 'text-warning-700 bg-warning-50 border-warning-200' },
            ].map((m) => (
              <div key={m.label} className={`p-4 rounded-xl border text-center ${m.color}`}>
                <p className="text-2xl font-bold">{m.value}</p>
                <p className="text-xs font-medium mt-1 opacity-80">{m.label}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Status distribution bar chart */}
            <Card>
              <CardHeader title="Status Distribution" subtitle="Submission counts by current status" />
              {statusData.length ? (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={statusData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ borderRadius: '12px', border: '1px solid #e5e7eb', fontSize: '12px' }}
                    />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                      {statusData.map((entry, i) => (
                        <Cell key={i} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-48 text-neutral-400 text-sm">
                  No data available
                </div>
              )}
            </Card>

            {/* Outcome pie chart */}
            <Card>
              <CardHeader title="Outcome Breakdown" subtitle="Approved vs rejected vs in-progress" />
              {rateData.some((d) => d.value > 0) ? (
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie
                      data={rateData}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={90}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      <Cell fill={COLORS.approved} />
                      <Cell fill={COLORS.rejected} />
                      <Cell fill={COLORS.pending}  />
                    </Pie>
                    <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e5e7eb', fontSize: '12px' }} />
                    <Legend iconType="circle" iconSize={8} formatter={(v) => <span className="text-xs text-neutral-600">{v}</span>} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-48 text-neutral-400 text-sm">
                  No data available
                </div>
              )}
            </Card>
          </div>

          {/* Approval rate */}
          {stats && stats.total_submissions > 0 && (
            <Card>
              <CardHeader title="Approval Rate" subtitle="Percentage of completed applications approved" />
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-neutral-600">Overall Approval Rate</span>
                  <span className="font-bold text-neutral-900">
                    {Math.round((stats.approval_rate ?? 0) * 100)}%
                  </span>
                </div>
                <div className="h-3 bg-neutral-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-success-500 rounded-full transition-all duration-700"
                    style={{ width: `${Math.round((stats.approval_rate ?? 0) * 100)}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-neutral-400">
                  <span>0%</span>
                  <span>50%</span>
                  <span>100%</span>
                </div>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
