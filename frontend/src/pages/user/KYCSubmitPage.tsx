import { useNavigate } from 'react-router-dom';
import { Shield } from 'lucide-react';
import { KYCForm } from '@/components/kyc/KYCForm';

export function KYCSubmitPage() {
  const navigate = useNavigate();

  const handleSuccess = (submissionId: string) => {
    navigate(`/kyc/status?id=${submissionId}`, { replace: true });
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Page header */}
      <div className="flex items-start gap-4">
        <div className="h-12 w-12 rounded-xl bg-primary-100 flex items-center justify-center shrink-0">
          <Shield className="h-6 w-6 text-primary-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">KYC Verification</h1>
          <p className="mt-1 text-neutral-500 text-sm">
            Complete all four steps to submit your identity verification application. The process takes approximately 5 minutes.
          </p>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-700">
        <p className="font-semibold mb-1">Before you begin:</p>
        <ul className="list-disc list-inside space-y-0.5 text-blue-600">
          <li>Have your government-issued ID document ready</li>
          <li>Ensure your documents are valid and not expired</li>
          <li>All information must match your official documents exactly</li>
          <li>Your data is encrypted and processed securely</li>
        </ul>
      </div>

      {/* Form */}
      <KYCForm onSuccess={handleSuccess} />
    </div>
  );
}
