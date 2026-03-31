import { useState } from 'react';
import { SubmissionTable } from '@/components/admin/SubmissionTable';
import { OverrideModal } from '@/components/admin/OverrideModal';
import type { KYCSubmission } from '@/types';

export function AdminSubmissionsPage() {
  const [selectedSubmission, setSelectedSubmission] = useState<KYCSubmission | null>(null);
  const [overrideOpen,       setOverrideOpen]       = useState(false);

  const handleOverride = (submission: KYCSubmission) => {
    setSelectedSubmission(submission);
    setOverrideOpen(true);
  };

  const handleClose = () => {
    setOverrideOpen(false);
    setSelectedSubmission(null);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">KYC Submissions</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Review, filter, and manage all KYC verification submissions.
        </p>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-neutral-200 shadow-card p-6">
        <SubmissionTable onOverride={handleOverride} />
      </div>

      {/* Override modal */}
      <OverrideModal
        open={overrideOpen}
        onClose={handleClose}
        submission={selectedSubmission}
      />
    </div>
  );
}
