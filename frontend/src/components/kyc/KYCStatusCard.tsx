import { CheckCircle2, XCircle, Clock, AlertTriangle, RefreshCw, Info } from 'lucide-react';
import { cn } from '@/utils/cn';
import { Card } from '@/components/ui/Card';
import { KYCStatusBadge } from '@/components/ui/Badge';
import { formatDateTime, formatRelativeTime, formatScore } from '@/utils/format';
import type { KYCSubmission } from '@/types';

// ─── Status Icon ─────────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: KYCSubmission['status'] }) {
  const config = {
    APPROVED:               { icon: CheckCircle2, color: 'text-success-500' },
    REJECTED:               { icon: XCircle,      color: 'text-danger-500'  },
    PENDING:                { icon: Clock,         color: 'text-warning-500' },
    PROCESSING:             { icon: RefreshCw,     color: 'text-primary-500 animate-spin' },
    MANUAL_REVIEW:          { icon: AlertTriangle, color: 'text-orange-500'  },
    RESUBMISSION_REQUIRED:  { icon: AlertTriangle, color: 'text-purple-500'  },
  }[status] ?? { icon: Info, color: 'text-neutral-500' };

  const Icon = config.icon;
  return <Icon className={cn('h-8 w-8', config.color)} />;
}

// ─── Confidence Bar ───────────────────────────────────────────────────────────

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80 ? 'bg-success-500' :
    pct >= 60 ? 'bg-warning-500' :
                'bg-danger-500';

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-neutral-600">Confidence Score</span>
        <span className="font-semibold text-neutral-900">{pct}%</span>
      </div>
      <div className="h-2.5 bg-neutral-100 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-700', color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-neutral-400">
        {pct >= 80 ? 'High confidence – likely authentic'  :
         pct >= 60 ? 'Medium confidence – manual review may be needed' :
                     'Low confidence – review recommended'}
      </p>
    </div>
  );
}

// ─── Timeline Event ───────────────────────────────────────────────────────────

interface TimelineEvent {
  status:    string;
  label:     string;
  timestamp: string;
  active:    boolean;
  done:      boolean;
}

function buildTimeline(submission: KYCSubmission): TimelineEvent[] {
  const steps: Array<{ status: string; label: string }> = [
    { status: 'PENDING',    label: 'Submitted'        },
    { status: 'PROCESSING', label: 'AI Processing'    },
    ...(submission.status === 'MANUAL_REVIEW'
      ? [{ status: 'MANUAL_REVIEW', label: 'Manual Review' }]
      : []),
    {
      status: submission.status === 'REJECTED' ? 'REJECTED' : 'APPROVED',
      label:  submission.status === 'REJECTED' ? 'Rejected'  : 'Approved',
    },
  ];

  const ORDER = ['PENDING', 'PROCESSING', 'MANUAL_REVIEW', 'APPROVED', 'REJECTED'];
  const currentIdx = ORDER.indexOf(submission.status);

  return steps.map((step, i) => ({
    ...step,
    timestamp: i === 0 ? submission.created_at : i === steps.length - 1 ? (submission.reviewed_at ?? '') : '',
    active: step.status === submission.status,
    done:   ORDER.indexOf(step.status) < currentIdx,
  }));
}

// ─── Main Card ────────────────────────────────────────────────────────────────

export interface KYCStatusCardProps {
  submission: KYCSubmission;
  className?: string;
}

export function KYCStatusCard({ submission, className }: KYCStatusCardProps) {
  const timeline = buildTimeline(submission);

  return (
    <Card className={cn('', className)}>
      {/* Header */}
      <div className="flex items-start gap-4 mb-6">
        <div className="p-3 bg-neutral-50 rounded-xl">
          <StatusIcon status={submission.status} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h3 className="text-lg font-semibold text-neutral-900">KYC Application</h3>
            <KYCStatusBadge status={submission.status} />
            {submission.admin_override && (
              <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-medium">
                Admin Override
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-neutral-500">
            Submitted {formatRelativeTime(submission.created_at)}
          </p>
          <p className="text-xs text-neutral-400 font-mono mt-0.5">
            ID: {submission.id}
          </p>
        </div>
      </div>

      {/* Confidence Score */}
      {submission.confidence_score != null && (
        <div className="mb-6 p-4 bg-neutral-50 rounded-xl">
          <ConfidenceBar score={submission.confidence_score} />
        </div>
      )}

      {/* AI Decision */}
      {submission.ai_reasoning && (
        <div className="mb-6 p-4 rounded-xl border border-neutral-200 bg-white">
          <p className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">
            AI Analysis
          </p>
          <p className="text-sm text-neutral-700 leading-relaxed">{submission.ai_reasoning}</p>
        </div>
      )}

      {/* Admin note */}
      {submission.admin_note && (
        <div className="mb-6 p-4 rounded-xl border border-orange-200 bg-orange-50">
          <p className="text-xs font-semibold text-orange-600 uppercase tracking-wider mb-2">
            Admin Note
          </p>
          <p className="text-sm text-orange-800">{submission.admin_note}</p>
        </div>
      )}

      {/* Timeline */}
      <div>
        <p className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-4">
          Status Timeline
        </p>
        <ol className="relative space-y-4">
          {timeline.map((event, idx) => (
            <li key={idx} className="flex items-start gap-3">
              {/* Indicator */}
              <div className="relative flex flex-col items-center">
                <div
                  className={cn(
                    'h-5 w-5 rounded-full border-2 flex items-center justify-center shrink-0',
                    event.done   && 'border-success-500 bg-success-500',
                    event.active && 'border-primary-500 bg-primary-500',
                    !event.done && !event.active && 'border-neutral-300 bg-white',
                  )}
                >
                  {(event.done || event.active) && (
                    <div className="h-2 w-2 rounded-full bg-white" />
                  )}
                </div>
                {idx < timeline.length - 1 && (
                  <div
                    className={cn(
                      'w-0.5 h-6 mt-1',
                      event.done ? 'bg-success-300' : 'bg-neutral-200',
                    )}
                  />
                )}
              </div>

              {/* Content */}
              <div className="pb-1">
                <p
                  className={cn(
                    'text-sm font-medium',
                    event.active && 'text-primary-700',
                    event.done   && 'text-neutral-600',
                    !event.done && !event.active && 'text-neutral-400',
                  )}
                >
                  {event.label}
                </p>
                {event.timestamp && (
                  <p className="text-xs text-neutral-400 mt-0.5">
                    {formatDateTime(event.timestamp)}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ol>
      </div>
    </Card>
  );
}
