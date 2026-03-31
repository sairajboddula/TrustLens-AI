import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, ArrowRight } from 'lucide-react';
import { useKYCSubmissions } from '@/hooks/useKYC';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { KYCStatusBadge } from '@/components/ui/Badge';
import { Pagination } from '@/components/ui/Pagination';
import { LoadingState } from '@/components/ui/Spinner';
import { formatDate, formatRelativeTime, formatScore } from '@/utils/format';

export function KYCSubmissionsPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useKYCSubmissions(page, 10);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">My Submissions</h1>
          <p className="mt-1 text-sm text-neutral-500">
            All your KYC verification applications.
          </p>
        </div>
        <Link to="/kyc/submit">
          <Button leftIcon={<Plus className="h-4 w-4" />}>
            New Submission
          </Button>
        </Link>
      </div>

      {/* List */}
      <Card padding="none">
        {isLoading ? (
          <div className="p-6">
            <LoadingState />
          </div>
        ) : !data?.items.length ? (
          <div className="text-center py-16 px-6">
            <p className="text-neutral-500 font-medium">No submissions found</p>
            <p className="text-sm text-neutral-400 mt-1">
              Start your identity verification by submitting a KYC application.
            </p>
            <Link to="/kyc/submit" className="mt-4 inline-block">
              <Button>Submit KYC</Button>
            </Link>
          </div>
        ) : (
          <>
            <ul className="divide-y divide-neutral-100">
              {data.items.map((submission) => (
                <li key={submission.id}>
                  <Link
                    to={`/kyc/status?id=${submission.id}`}
                    className="flex items-center gap-4 px-6 py-4 hover:bg-neutral-50 transition-colors group"
                  >
                    {/* Doc type + date */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-medium text-neutral-900">
                          {submission.identity_document?.document_type?.replace(/_/g, ' ') ?? 'KYC Application'}
                        </p>
                        <KYCStatusBadge status={submission.status} size="sm" />
                      </div>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs text-neutral-400">
                          Submitted {formatRelativeTime(submission.created_at)}
                        </span>
                        {submission.confidence_score != null && (
                          <span className="text-xs text-neutral-400">
                            Score: {Math.round(submission.confidence_score * 100)}%
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Confidence bar */}
                    {submission.confidence_score != null && (
                      <div className="hidden sm:flex items-center gap-2 w-24">
                        <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                          <div
                            className={
                              submission.confidence_score >= 0.8
                                ? 'h-full bg-success-500 rounded-full'
                                : submission.confidence_score >= 0.6
                                ? 'h-full bg-warning-500 rounded-full'
                                : 'h-full bg-danger-500 rounded-full'
                            }
                            style={{ width: `${submission.confidence_score * 100}%` }}
                          />
                        </div>
                      </div>
                    )}

                    <ArrowRight className="h-4 w-4 text-neutral-300 group-hover:text-neutral-500 transition-colors shrink-0" />
                  </Link>
                </li>
              ))}
            </ul>

            <div className="px-6 pb-4">
              <Pagination
                page={data.page}
                totalPages={data.pages}
                total={data.total}
                limit={data.size}
                onPageChange={setPage}
              />
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
