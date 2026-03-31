import { useSearchParams, Link } from 'react-router-dom';
import { RefreshCw, ArrowLeft, FileText } from 'lucide-react';
import { useKYCSubmissionStatus, useKYCSubmission, useKYCSubmissions } from '@/hooks/useKYC';
import { KYCStatusCard } from '@/components/kyc/KYCStatusCard';
import { KYCStatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { LoadingState } from '@/components/ui/Spinner';
import { formatDate, formatRelativeTime } from '@/utils/format';

// ─── Status Detail Panel ─────────────────────────────────────────────────────

function StatusDetail({ submissionId }: { submissionId: string }) {
  const { data: submission, isLoading, refetch } = useKYCSubmission(submissionId);
  const { data: statusPoll } = useKYCSubmissionStatus(submissionId);

  // Merge polled status into submission for display
  const merged = submission
    ? {
        ...submission,
        status:           statusPoll?.status           ?? submission.status,
        confidence_score: statusPoll?.confidence_score ?? submission.confidence_score,
      }
    : null;

  if (isLoading) return <LoadingState message="Loading submission details…" />;

  if (!merged) {
    return (
      <div className="text-center py-12">
        <p className="text-neutral-500">Submission not found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-neutral-900">Submission Details</h2>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 text-sm text-neutral-500 hover:text-neutral-700 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>
      <KYCStatusCard submission={merged} />

      {/* Personal details summary */}
      <div className="bg-white rounded-xl border border-neutral-200 shadow-card p-6">
        <h3 className="text-sm font-semibold text-neutral-500 uppercase tracking-wider mb-4">
          Submitted Information
        </h3>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <InfoRow label="Full Name" value={`${merged.personal_info?.first_name} ${merged.personal_info?.last_name}`} />
          <InfoRow label="Date of Birth" value={formatDate(merged.personal_info?.date_of_birth)} />
          <InfoRow label="Nationality"   value={merged.personal_info?.nationality} />
          <InfoRow label="Document Type" value={merged.identity_document?.document_type?.replace(/_/g, ' ')} />
          <InfoRow label="Document No."  value={merged.identity_document?.document_number} />
          <InfoRow label="Expiry Date"   value={formatDate(merged.identity_document?.expiry_date)} />
          <InfoRow label="Country"        value={merged.address?.country} />
          <InfoRow label="City"           value={merged.address?.city} />
        </div>
      </div>

      {/* Actions */}
      {merged.status === 'REJECTED' && (
        <div className="flex justify-end">
          <Link to="/kyc/submit">
            <Button leftIcon={<FileText className="h-4 w-4" />}>
              Submit New Application
            </Button>
          </Link>
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <p className="text-xs text-neutral-400 mb-0.5">{label}</p>
      <p className="font-medium text-neutral-800">{value ?? '—'}</p>
    </div>
  );
}

// ─── Submissions list (sidebar) ───────────────────────────────────────────────

function SubmissionsList({
  currentId,
  onSelect,
}: {
  currentId?: string;
  onSelect: (id: string) => void;
}) {
  const { data, isLoading } = useKYCSubmissions(1, 20);

  if (isLoading) return <LoadingState message="Loading…" />;

  if (!data?.items.length) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-neutral-400">No submissions yet.</p>
      </div>
    );
  }

  return (
    <ul className="space-y-1">
      {data.items.map((s) => (
        <li key={s.id}>
          <button
            onClick={() => onSelect(s.id)}
            className={`w-full flex items-start gap-3 p-3 rounded-xl text-left transition-colors ${
              currentId === s.id
                ? 'bg-primary-50 border border-primary-200'
                : 'hover:bg-neutral-50'
            }`}
          >
            <div className="h-8 w-8 rounded-lg bg-neutral-100 flex items-center justify-center shrink-0">
              <FileText className="h-4 w-4 text-neutral-500" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-medium text-neutral-700 truncate">
                  {s.identity_document?.document_type?.replace(/_/g, ' ') ?? 'KYC Application'}
                </p>
                <KYCStatusBadge status={s.status} size="sm" />
              </div>
              <p className="text-xs text-neutral-400 mt-0.5">{formatRelativeTime(s.created_at)}</p>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function KYCStatusPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get('id') ?? undefined;

  const handleSelect = (id: string) => {
    setSearchParams({ id }, { replace: true });
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/dashboard">
          <Button variant="ghost" size="sm" leftIcon={<ArrowLeft className="h-4 w-4" />}>
            Dashboard
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">KYC Status</h1>
          <p className="text-sm text-neutral-500">
            Track your identity verification applications.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Submissions sidebar */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl border border-neutral-200 shadow-card p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-neutral-900">Your Submissions</h2>
              <Link
                to="/kyc/submit"
                className="text-xs text-primary-600 font-medium hover:underline"
              >
                + New
              </Link>
            </div>
            <SubmissionsList currentId={selectedId} onSelect={handleSelect} />
          </div>
        </div>

        {/* Detail panel */}
        <div className="lg:col-span-2">
          {selectedId ? (
            <StatusDetail submissionId={selectedId} />
          ) : (
            <div className="flex flex-col items-center justify-center h-64 bg-white rounded-xl border border-neutral-200 text-center p-6">
              <FileText className="h-10 w-10 text-neutral-300 mb-3" />
              <p className="text-sm font-medium text-neutral-500">Select a submission to view its status</p>
              <p className="text-xs text-neutral-400 mt-1">
                Or{' '}
                <Link to="/kyc/submit" className="text-primary-600 hover:underline">
                  submit a new application
                </Link>
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
