import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ChevronRight, ChevronLeft, Check, User, CreditCard, MapPin, Upload } from 'lucide-react';
import { cn } from '@/utils/cn';
import { Button } from '@/components/ui/Button';
import { Input, Select } from '@/components/ui/Input';
import { DocumentSidesUpload } from './DocumentUpload';
import { useSubmitKYC } from '@/hooks/useKYC';
import { documentService } from '@/services/document.service';
import toast from 'react-hot-toast';
import type { KYCSubmitRequest, KYCDocumentType } from '@/types';

// ─── Schemas ──────────────────────────────────────────────────────────────────

const personalSchema = z.object({
  first_name:    z.string().min(2,  'First name must be at least 2 characters'),
  last_name:     z.string().min(2,  'Last name must be at least 2 characters'),
  date_of_birth: z.string().min(1,  'Date of birth is required'),
  nationality:   z.string().min(2,  'Nationality is required'),
  phone_number:  z.string().optional(),
});

const identitySchema = z.object({
  document_type:   z.enum(['PASSPORT', 'NATIONAL_ID', 'DRIVERS_LICENSE', 'RESIDENCE_PERMIT']),
  document_number: z.string().min(3,  'Document number is required'),
  issue_date:      z.string().min(1,  'Issue date is required'),
  expiry_date:     z.string().min(1,  'Expiry date is required'),
  issuing_country: z.string().min(2,  'Issuing country is required'),
});

const addressSchema = z.object({
  street_address: z.string().min(5,  'Street address is required'),
  city:           z.string().min(2,  'City is required'),
  state:          z.string().min(2,  'State / region is required'),
  country:        z.string().min(2,  'Country is required'),
  postal_code:    z.string().min(3,  'Postal code is required'),
});

type PersonalData  = z.infer<typeof personalSchema>;
type IdentityData  = z.infer<typeof identitySchema>;
type AddressData   = z.infer<typeof addressSchema>;

// ─── Step Config ──────────────────────────────────────────────────────────────

const STEPS = [
  { id: 1, label: 'Personal Info',      icon: User        },
  { id: 2, label: 'Identity Document',  icon: CreditCard  },
  { id: 3, label: 'Address',            icon: MapPin      },
  { id: 4, label: 'Document Upload',    icon: Upload      },
];

// ─── Progress Indicator ───────────────────────────────────────────────────────

function StepIndicator({ current }: { current: number }) {
  return (
    <nav aria-label="Progress">
      <ol className="flex items-center">
        {STEPS.map((step, idx) => {
          const done   = step.id < current;
          const active = step.id === current;
          const Icon   = step.icon;

          return (
            <li key={step.id} className={cn('flex items-center', idx < STEPS.length - 1 && 'flex-1')}>
              {/* Circle */}
              <div className="flex flex-col items-center">
                <div
                  className={cn(
                    'h-9 w-9 rounded-full flex items-center justify-center text-sm font-medium border-2 transition-colors',
                    done   && 'bg-primary-600 border-primary-600 text-white',
                    active && 'bg-white border-primary-600 text-primary-600',
                    !done && !active && 'bg-white border-neutral-300 text-neutral-400',
                  )}
                >
                  {done ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                </div>
                <p
                  className={cn(
                    'mt-1.5 text-2xs font-medium hidden sm:block text-center whitespace-nowrap',
                    active && 'text-primary-600',
                    done   && 'text-neutral-600',
                    !done && !active && 'text-neutral-400',
                  )}
                >
                  {step.label}
                </p>
              </div>

              {/* Connector */}
              {idx < STEPS.length - 1 && (
                <div
                  className={cn(
                    'flex-1 h-0.5 mx-2 sm:mx-3 mt-0 sm:-mt-5',
                    done ? 'bg-primary-600' : 'bg-neutral-200',
                  )}
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

// ─── KYC Form ────────────────────────────────────────────────────────────────

interface KYCFormProps {
  onSuccess?: (submissionId: string) => void;
}

export function KYCForm({ onSuccess }: KYCFormProps) {
  const [step,      setStep]      = useState(1);
  const [personal,  setPersonal]  = useState<PersonalData | null>(null);
  const [identity,  setIdentity]  = useState<IdentityData | null>(null);
  const [address,   setAddress]   = useState<AddressData  | null>(null);
  const [frontFile, setFrontFile] = useState<File | null>(null);
  const [backFile,  setBackFile]  = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const submitKYC = useSubmitKYC();

  // ── Step 1 ─────────────────────────────────────────────────────────────────

  const {
    register: regPersonal,
    handleSubmit: handlePersonal,
    formState: { errors: errPersonal },
  } = useForm<PersonalData>({
    resolver: zodResolver(personalSchema),
    defaultValues: personal ?? undefined,
  });

  // ── Step 2 ─────────────────────────────────────────────────────────────────

  const {
    register: regIdentity,
    handleSubmit: handleIdentity,
    formState: { errors: errIdentity },
  } = useForm<IdentityData>({
    resolver: zodResolver(identitySchema),
    defaultValues: identity ?? undefined,
  });

  // ── Step 3 ─────────────────────────────────────────────────────────────────

  const {
    register: regAddress,
    handleSubmit: handleAddress,
    formState: { errors: errAddress },
  } = useForm<AddressData>({
    resolver: zodResolver(addressSchema),
    defaultValues: address ?? undefined,
  });

  // ── Final submit ───────────────────────────────────────────────────────────

  const handleFinalSubmit = async () => {
    if (!personal || !identity || !address) {
      toast.error('Please complete all previous steps.');
      return;
    }
    if (!frontFile) {
      toast.error('Please upload the front of your identity document.');
      return;
    }

    const payload: KYCSubmitRequest = {
      personal_info:     personal,
      identity_document: {
        ...identity,
        document_type: identity.document_type as KYCDocumentType,
      },
      address,
    };

    try {
      const submission = await submitKYC.mutateAsync(payload);

      // Upload documents
      setUploading(true);
      try {
        await documentService.uploadDocument(
          frontFile,
          submission.id,
          identity.document_type as KYCDocumentType,
          'FRONT',
        );
        if (backFile) {
          await documentService.uploadDocument(
            backFile,
            submission.id,
            identity.document_type as KYCDocumentType,
            'BACK',
          );
        }
      } catch {
        toast.error('Documents uploaded partially – submission still recorded.');
      } finally {
        setUploading(false);
      }

      onSuccess?.(submission.id);
    } catch {
      // error toast handled by mutation
    }
  };

  const isLoading = submitKYC.isPending || uploading;

  // ── Render steps ───────────────────────────────────────────────────────────

  return (
    <div className="space-y-8">
      <StepIndicator current={step} />

      <div className="bg-white rounded-2xl border border-neutral-200 shadow-card overflow-hidden">
        {/* Step 1 – Personal Info */}
        {step === 1 && (
          <form
            onSubmit={handlePersonal((data) => {
              setPersonal(data);
              setStep(2);
            })}
            className="p-6 sm:p-8 space-y-5"
          >
            <StepHeader
              step={1}
              title="Personal Information"
              subtitle="Provide your legal personal details exactly as they appear on your ID."
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="First Name"
                required
                placeholder="John"
                error={errPersonal.first_name?.message}
                {...regPersonal('first_name')}
              />
              <Input
                label="Last Name"
                required
                placeholder="Doe"
                error={errPersonal.last_name?.message}
                {...regPersonal('last_name')}
              />
              <Input
                label="Date of Birth"
                type="date"
                required
                error={errPersonal.date_of_birth?.message}
                {...regPersonal('date_of_birth')}
              />
              <Input
                label="Nationality"
                required
                placeholder="e.g. American"
                error={errPersonal.nationality?.message}
                {...regPersonal('nationality')}
              />
              <Input
                label="Phone Number"
                type="tel"
                placeholder="+1 555 123 4567"
                containerClassName="sm:col-span-2"
                error={errPersonal.phone_number?.message}
                {...regPersonal('phone_number')}
              />
            </div>
            <StepFooter onBack={undefined} />
          </form>
        )}

        {/* Step 2 – Identity Document */}
        {step === 2 && (
          <form
            onSubmit={handleIdentity((data) => {
              setIdentity(data);
              setStep(3);
            })}
            className="p-6 sm:p-8 space-y-5"
          >
            <StepHeader
              step={2}
              title="Identity Document"
              subtitle="Enter the details from your government-issued identity document."
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Select
                label="Document Type"
                required
                error={errIdentity.document_type?.message}
                containerClassName="sm:col-span-2"
                {...regIdentity('document_type')}
              >
                <option value="">Select document type…</option>
                <option value="PASSPORT">Passport</option>
                <option value="NATIONAL_ID">National ID Card</option>
                <option value="DRIVERS_LICENSE">Driver's License</option>
                <option value="RESIDENCE_PERMIT">Residence Permit</option>
              </Select>
              <Input
                label="Document Number"
                required
                placeholder="e.g. AB1234567"
                error={errIdentity.document_number?.message}
                {...regIdentity('document_number')}
              />
              <Input
                label="Issuing Country"
                required
                placeholder="e.g. United States"
                error={errIdentity.issuing_country?.message}
                {...regIdentity('issuing_country')}
              />
              <Input
                label="Issue Date"
                type="date"
                required
                error={errIdentity.issue_date?.message}
                {...regIdentity('issue_date')}
              />
              <Input
                label="Expiry Date"
                type="date"
                required
                error={errIdentity.expiry_date?.message}
                {...regIdentity('expiry_date')}
              />
            </div>
            <StepFooter onBack={() => setStep(1)} />
          </form>
        )}

        {/* Step 3 – Address */}
        {step === 3 && (
          <form
            onSubmit={handleAddress((data) => {
              setAddress(data);
              setStep(4);
            })}
            className="p-6 sm:p-8 space-y-5"
          >
            <StepHeader
              step={3}
              title="Residential Address"
              subtitle="Provide your current residential address for verification."
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Street Address"
                required
                placeholder="123 Main Street, Apt 4B"
                containerClassName="sm:col-span-2"
                error={errAddress.street_address?.message}
                {...regAddress('street_address')}
              />
              <Input
                label="City"
                required
                placeholder="New York"
                error={errAddress.city?.message}
                {...regAddress('city')}
              />
              <Input
                label="State / Province"
                required
                placeholder="New York"
                error={errAddress.state?.message}
                {...regAddress('state')}
              />
              <Input
                label="Country"
                required
                placeholder="United States"
                error={errAddress.country?.message}
                {...regAddress('country')}
              />
              <Input
                label="Postal Code"
                required
                placeholder="10001"
                error={errAddress.postal_code?.message}
                {...regAddress('postal_code')}
              />
            </div>
            <StepFooter onBack={() => setStep(2)} />
          </form>
        )}

        {/* Step 4 – Document Upload */}
        {step === 4 && (
          <div className="p-6 sm:p-8 space-y-6">
            <StepHeader
              step={4}
              title="Upload Documents"
              subtitle="Upload clear photos of your identity document. Images must be legible and unobstructed."
            />

            <DocumentSidesUpload
              label={`${identity?.document_type?.replace(/_/g, ' ') ?? 'Identity Document'} Photos`}
              frontFile={frontFile}
              backFile={backFile}
              onFrontChange={setFrontFile}
              onBackChange={setBackFile}
              disabled={isLoading}
            />

            <div className="rounded-xl bg-primary-50 border border-primary-200 p-4 text-sm text-primary-700 space-y-1">
              <p className="font-semibold">Tips for a successful upload:</p>
              <ul className="list-disc list-inside space-y-0.5 text-primary-600">
                <li>Ensure all text and numbers are clearly visible</li>
                <li>Avoid glare, shadows, or blurred images</li>
                <li>Make sure all four corners are visible</li>
                <li>Accepted formats: JPG, PNG, PDF (max 10 MB)</li>
              </ul>
            </div>

            <div className="flex items-center justify-between pt-2">
              <Button
                type="button"
                variant="outline"
                leftIcon={<ChevronLeft className="h-4 w-4" />}
                onClick={() => setStep(3)}
                disabled={isLoading}
              >
                Back
              </Button>
              <Button
                type="button"
                onClick={handleFinalSubmit}
                loading={isLoading}
                rightIcon={<Check className="h-4 w-4" />}
              >
                {isLoading ? 'Submitting…' : 'Submit Application'}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function StepHeader({
  step,
  title,
  subtitle,
}: {
  step: number;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="pb-2 border-b border-neutral-100">
      <p className="text-xs font-semibold text-primary-600 uppercase tracking-wider mb-1">
        Step {step} of {STEPS.length}
      </p>
      <h2 className="text-xl font-bold text-neutral-900">{title}</h2>
      <p className="mt-1 text-sm text-neutral-500">{subtitle}</p>
    </div>
  );
}

function StepFooter({ onBack }: { onBack?: () => void }) {
  return (
    <div className="flex items-center justify-between pt-2">
      {onBack ? (
        <Button
          type="button"
          variant="outline"
          leftIcon={<ChevronLeft className="h-4 w-4" />}
          onClick={onBack}
        >
          Back
        </Button>
      ) : (
        <div />
      )}
      <Button type="submit" rightIcon={<ChevronRight className="h-4 w-4" />}>
        Continue
      </Button>
    </div>
  );
}
