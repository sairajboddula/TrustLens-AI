import {
  FileText,
  CheckCircle2,
  Clock,
  AlertTriangle,
  TrendingUp,
  Activity,
} from 'lucide-react';
import { StatCard } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { formatNumber } from '@/utils/format';
import type { AdminStats } from '@/types';

interface StatsCardsProps {
  stats?:     AdminStats;
  isLoading?: boolean;
}

export function StatsCards({ stats, isLoading }: StatsCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="bg-white rounded-xl border border-neutral-200 shadow-card p-6 h-28 animate-pulse"
          >
            <div className="h-4 bg-neutral-100 rounded w-24 mb-3" />
            <div className="h-8 bg-neutral-100 rounded w-16" />
          </div>
        ))}
      </div>
    );
  }

  if (!stats) return null;

  const approvalPct = stats.total_submissions > 0
    ? Math.round(stats.approval_rate * 100)
    : 0;

  const avgScore = stats.average_confidence_score != null
    ? Math.round(stats.average_confidence_score * 100)
    : 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard
        title="Total Submissions"
        value={formatNumber(stats.total_submissions)}
        subtitle={`${formatNumber(stats.submissions_today)} today`}
        icon={<FileText className="h-5 w-5" />}
        color="blue"
      />
      <StatCard
        title="Approval Rate"
        value={`${approvalPct}%`}
        subtitle={`${formatNumber(stats.approved_count)} approved`}
        icon={<CheckCircle2 className="h-5 w-5" />}
        color="green"
      />
      <StatCard
        title="Pending Review"
        value={formatNumber(stats.pending_count + stats.manual_review_count)}
        subtitle={`${formatNumber(stats.manual_review_count)} need manual review`}
        icon={<Clock className="h-5 w-5" />}
        color="yellow"
      />
      <StatCard
        title="Avg Confidence"
        value={`${avgScore}%`}
        subtitle="AI confidence score"
        icon={<Activity className="h-5 w-5" />}
        color="purple"
      />
    </div>
  );
}

// ─── Secondary stats row ─────────────────────────────────────────────────────

export function SecondaryStatsRow({ stats }: { stats?: AdminStats }) {
  if (!stats) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <MiniStat label="This Week"  value={formatNumber(stats.submissions_this_week)}  />
      <MiniStat label="This Month" value={formatNumber(stats.submissions_this_month)} />
      <MiniStat label="Rejected"   value={formatNumber(stats.rejected_count)}          />
      <MiniStat label="Processing" value={formatNumber(stats.total_submissions - stats.approved_count - stats.rejected_count)} />
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-neutral-50 rounded-lg p-3 text-center">
      <p className="text-lg font-bold text-neutral-900">{value}</p>
      <p className="text-xs text-neutral-500 mt-0.5">{label}</p>
    </div>
  );
}
