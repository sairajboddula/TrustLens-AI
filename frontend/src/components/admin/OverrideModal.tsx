import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AlertTriangle } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Select, Textarea } from '@/components/ui/Input';
import { KYCStatusBadge } from '@/components/ui/Badge';
import { useAdminOverride } from '@/hooks/useKYC';
import type { KYCSubmission, AdminOverrideRequest } from '@/types';

// ─── Schema ───────────────────────────────────────────────────────────────────

const schema = z.object({
  decision: z.enum(['APPROVED', 'REJECTED', 'MANUAL_REVIEW'], {
    required_error: 'Please select a decision.',
  }),
  reason: z.string().min(10, 'Reason must be at least 10 characters.'),
});

type FormData = z.infer<typeof schema>;

// ─── Props ────────────────────────────────────────────────────────────────────

interface OverrideModalProps {
  open:       boolean;
  onClose:    () => void;
  submission: KYCSubmission | null;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function OverrideModal({ open, onClose, submission }: OverrideModalProps) {
  const override = useAdminOverride();

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { decision: 'APPROVED', reason: '' },
  });

  const selectedDecision = watch('decision');

  // Reset form whenever modal opens with a new submission
  useEffect(() => {
    if (open) reset({ decision: 'APPROVED', reason: '' });
  }, [open, reset]);

  const onSubmit = async (data: FormData) => {
    if (!submission) return;

    await override.mutateAsync({
      id:       submission.id,
      override: data as AdminOverrideRequest,
    });

    onClose();
  };

  const decisionColors = {
    APPROVED:      'text-success-700 bg-success-50 border-success-200',
    REJECTED:      'text-danger-700  bg-danger-50  border-danger-200',
    MANUAL_REVIEW: 'text-orange-700  bg-orange-50  border-orange-200',
  } as const;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Override AI Decision"
      description="Manually set the outcome for this KYC submission. All overrides are logged."
      size="md"
    >
      {submission && (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          {/* Current status banner */}
          <div className="flex items-center gap-3 p-4 bg-neutral-50 rounded-xl border border-neutral-200">
            <div>
              <p className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-1">
                Current Status
              </p>
              <KYCStatusBadge status={submission.status} size="lg" />
            </div>
            <div className="ml-auto text-right">
              <p className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-1">
                Applicant
              </p>
              <p className="text-sm font-medium text-neutral-800">
                {submission.personal_info?.first_name} {submission.personal_info?.last_name}
              </p>
            </div>
          </div>

          {/* Warning */}
          <div className="flex items-start gap-3 p-3 bg-warning-50 border border-warning-200 rounded-xl">
            <AlertTriangle className="h-4 w-4 text-warning-600 shrink-0 mt-0.5" />
            <p className="text-xs text-warning-700">
              This action will override the AI decision and is irreversible. Ensure you have reviewed all documents before proceeding.
            </p>
          </div>

          {/* Decision */}
          <Select
            label="New Decision"
            required
            error={errors.decision?.message}
            {...register('decision')}
          >
            <option value="APPROVED">Approve</option>
            <option value="REJECTED">Reject</option>
            <option value="MANUAL_REVIEW">Send to Manual Review</option>
          </Select>

          {/* Decision preview badge */}
          {selectedDecision && (
            <div
              className={`px-3 py-2 rounded-lg border text-sm font-medium ${decisionColors[selectedDecision as keyof typeof decisionColors]}`}
            >
              Decision will be set to: <strong>{selectedDecision.replace(/_/g, ' ')}</strong>
            </div>
          )}

          {/* Reason */}
          <Textarea
            label="Reason / Notes"
            required
            rows={4}
            placeholder="Provide a clear reason for this override decision…"
            error={errors.reason?.message}
            helperText="This note will be visible to the applicant and auditors."
            {...register('reason')}
          />

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-2 border-t border-neutral-100">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={override.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant={selectedDecision === 'REJECTED' ? 'danger' : 'primary'}
              loading={override.isPending}
            >
              Confirm Override
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
