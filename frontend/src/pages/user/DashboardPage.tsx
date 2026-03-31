import { Link } from 'react-router-dom';
import {
  ArrowRight,
  FileText,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Plus,
} from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useKYCSubmissions, useLatestKYCSubmission } from '@/hooks/useKYC';
import { Card, StatCard } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { KYCStatusBadge } from '@/components/ui/Badge';
import { LoadingState } from '@/components/ui/Spinner';
import { formatDate, formatRelativeTime } from '@/utils/format';
import type { KYCSubmission } from '@/types';

// ─── Status summary ───────────────────────────────────────────────────────────

function StatusSummary({ submissions }: { submissions: KYCSubmission[] }) {
  const counts = submissions.reduce(
    (acc, s) => {
      if (s.status === 'APPROVED')       acc.approved++;
      else if (s.status === 'REJECTED')  acc.rejected++;
      else if (s.status === 'PENDING' || s.status === 'PROCESSING') acc.pending++;
      return acc;
    },
    { approved: 0, rejected: 0, pending: 0 },
  );

  return (
    <div className="grid grid-cols-3 gap-3">
      <div className="flex flex-col items-center p-3 bg-success-50 rounded-xl border border-success-100">
        <CheckCircle2 className="h-6 w-6 text-success-500 mb-1" />
        <p className="text-xl font-bold text-success-700">{counts.approved}</p>
        <p className="text-xs text-success-600">Approved</p>
      </div>
      <div className="flex flex-col items-center p-3 bg-warning-50 rounded-xl border border-warning-100">
        <Clock className="h-6 w-6 text-warning-500 mb-1" />
        <p className="text-xl font-bold text-warning-700">{counts.pending}</p>
        <p className="text-xs text-warning-600">Pending</p>
      </div>
      <div className="flex flex-col items-center p-3 bg-danger-50 rounded-xl border border-danger-100">
        <XCircle className="h-6 w-6 text-danger-500 mb-1" />
        <p className="text-xl font-bold text-danger-700">{counts.rejected}</p>
        <p className="text-xs text-danger-600">Rejected</p>
      </div>
    </div>
  );
}

// ─── Recent item row ──────────────────────────────────────────────────────────

function SubmissionRow({ submission }: { submission: KYCSubmission }) {
  return (
    <Link
      to={`/kyc/status?id=${submission.id}`}
      className="flex items-center gap-4 p-3 rounded-xl hover:bg-neutral-50 transition-colors group"
    >
      <div className="h-9 w-9 rounded-xl bg-neutral-100 flex items-center justify-center shrink-0">
        <FileText className="h-4.5 w-4.5 text-neutral-500" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-neutral-800 truncate">
          {submission.identity_document?.document_type?.replace(/_/g, ' ') ?? 'KYC Application'}
        </p>
        <p className="text-xs text-neutral-400">{formatRelativeTime(submission.created_at)}</p>
      </div>
      <div className="flex items-center gap-2">
        <KYCStatusBadge status={submission.status} size="sm" />
        <ArrowRight className="h-3.5 w-3.5 text-neutral-300 group-hover:text-neutral-500 transition-colors" />
      </div>
    </Link>
  );
}

// ─── Dashboard Page ───────────────────────────────────────────────────────────

export function DashboardPage() {
  const { user } = useAuth();
  const { data: submissionsData, isLoading } = useKYCSubmissions(1, 5);
  const { data: latestSubmission } = useLatestKYCSubmission();

  const submissions = submissionsData?.items ?? [];
  const firstName   = user?.full_name.split(' ')[0] ?? 'there';

  const hasSubmissions = submissions.length > 0;
  const latestStatus   = latestSubmission?.status;

  const statusAlerts = {
    APPROVED: {
      bg:   'bg-success-50 border-success-200',
      icon: <CheckCircle2 className="h-5 w-5 text-success-600" />,
      text: 'Your KYC verification is complete and approved.',
      color: 'text-success-700',
    },
    REJECTED: {
      bg:   'bg-danger-50 border-danger-200',
      icon: <XCircle className="h-5 w-5 text-danger-600" />,
      text: 'Your recent KYC submission was rejected. Please review the feedback and resubmit.',
      color: 'text-danger-700',
    },
    MANUAL_REVIEW: {
      bg:   'bg-orange-50 border-orange-200',
      icon: <AlertTriangle className="h-5 w-5 text-orange-600" />,
      text: "Your submission is under manual review. We'll notify you once it's complete.",
      color: 'text-orange-700',
    },
    PENDING: {
      bg:   'bg-warning-50 border-warning-200',
      icon: <Clock className="h-5 w-5 text-warning-600" />,
      text: 'Your KYC submission is awaiting processing.',
      color: 'text-warning-700',
    },
    PROCESSING: {
      bg:   'bg-primary-50 border-primary-200',
      icon: <Clock className="h-5 w-5 text-primary-600 animate-spin" />,
      text: 'Your KYC submission is currently being processed by our AI.',
      color: 'text-primary-700',
    },
  };

  const alert = latestStatus ? statusAlerts[latestStatus as keyof typeof statusAlerts] : null;

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">
          Welcome back, {firstName}!
        </h1>
        <p className="mt-1 text-neutral-500">
          {hasSubmissions
            ? 'Track your KYC applications and verification status below.'
            : 'Get started by submitting your KYC application.'}
        </p>
      </div>

      {/* Status alert */}
      {alert && (
        <div className={`flex items-start gap-3 p-4 rounded-xl border ${alert.bg}`}>
          <span className="shrink-0 mt-0.5">{alert.icon}</span>
          <div className="flex-1">
            <p className={`text-sm font-medium ${alert.color}`}>{alert.text}</p>
            {latestStatus && (
              <Link
                to="/kyc/status"
                className={`text-xs underline mt-1 block ${alert.color} opacity-80 hover:opacity-100`}
              >
                View details →
              </Link>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: quick actions + recent */}
        <div className="lg:col-span-2 space-y-6">
          {/* Quick actions */}
          <Card>
            <h2 className="text-base font-semibold text-neutral-900 mb-4">Quick Actions</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Link
                to="/kyc/submit"
                className="flex items-center gap-3 p-4 rounded-xl border-2 border-dashed border-primary-200 hover:border-primary-400 hover:bg-primary-50 transition-colors group"
              >
                <div className="h-10 w-10 rounded-xl bg-primary-100 flex items-center justify-center group-hover:bg-primary-200 transition-colors">
                  <Plus className="h-5 w-5 text-primary-600" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-neutral-900">Submit KYC</p>
                  <p className="text-xs text-neutral-400">Start verification</p>
                </div>
              </Link>
              <Link
                to="/kyc/status"
                className="flex items-center gap-3 p-4 rounded-xl border border-neutral-200 hover:bg-neutral-50 transition-colors group"
              >
                <div className="h-10 w-10 rounded-xl bg-neutral-100 flex items-center justify-center">
                  <Clock className="h-5 w-5 text-neutral-500" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-neutral-900">Track Status</p>
                  <p className="text-xs text-neutral-400">Check progress</p>
                </div>
              </Link>
            </div>
          </Card>

          {/* Recent submissions */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-neutral-900">Recent Submissions</h2>
              <Link to="/kyc/submissions" className="text-sm text-primary-600 hover:underline font-medium">
                View all
              </Link>
            </div>

            {isLoading ? (
              <LoadingState message="Loading submissions…" />
            ) : !hasSubmissions ? (
              <div className="text-center py-10">
                <FileText className="h-10 w-10 text-neutral-300 mx-auto mb-3" />
                <p className="text-sm font-medium text-neutral-500">No submissions yet</p>
                <p className="text-xs text-neutral-400 mt-1">Submit your first KYC application to get started.</p>
                <Link to="/kyc/submit">
                  <Button size="sm" className="mt-4">
                    Submit KYC
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="divide-y divide-neutral-100">
                {submissions.map((s) => (
                  <SubmissionRow key={s.id} submission={s} />
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right: summary stats */}
        <div className="space-y-6">
          {hasSubmissions && (
            <Card>
              <h2 className="text-base font-semibold text-neutral-900 mb-4">Your Activity</h2>
              <StatusSummary submissions={submissions} />
              <div className="mt-4 pt-4 border-t border-neutral-100 text-center">
                <p className="text-2xl font-bold text-neutral-900">{submissions.length}</p>
                <p className="text-xs text-neutral-400">Total Applications</p>
              </div>
            </Card>
          )}

          {/* Info card */}
          <Card className="bg-primary-50 border-primary-200">
            <h3 className="text-sm font-semibold text-primary-800 mb-2">Need Help?</h3>
            <p className="text-xs text-primary-600 leading-relaxed">
              Ensure your documents are clear and not expired. AI verification typically completes within 2 minutes.
            </p>
            <a
              href="#"
              className="mt-3 text-xs text-primary-700 font-medium hover:underline block"
            >
              View KYC guide →
            </a>
          </Card>
        </div>
      </div>
    </div>
  );
}
