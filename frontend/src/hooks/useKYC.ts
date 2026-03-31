import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
} from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { kycService } from '@/services/kyc.service';
import type {
  KYCSubmission,
  KYCSubmitRequest,
  AdminOverrideRequest,
  SubmissionFilter,
  PaginatedResponse,
  AdminStats,
} from '@/types';

// ─── Query Keys ───────────────────────────────────────────────────────────────

export const kycKeys = {
  all:              ['kyc']                           as const,
  submissions:      (page: number, limit: number)  => ['kyc', 'submissions', page, limit] as const,
  submission:       (id: string)                   => ['kyc', 'submission', id]           as const,
  submissionStatus: (id: string)                   => ['kyc', 'status', id]               as const,
  latestSubmission:                                   ['kyc', 'latest']                    as const,
  adminSubmissions: (filters: SubmissionFilter)    => ['admin', 'kyc', filters]           as const,
  adminStats:                                         ['admin', 'stats']                   as const,
  chartData:        (days: number)                 => ['admin', 'chart', days]            as const,
};

// ─── User Hooks ───────────────────────────────────────────────────────────────

export function useKYCSubmissions(page = 1, limit = 10) {
  return useQuery<PaginatedResponse<KYCSubmission>, Error>({
    queryKey: kycKeys.submissions(page, limit),
    queryFn:  () => kycService.getSubmissions(page, limit),
    staleTime: 30_000,
  });
}

export function useKYCSubmission(
  id: string,
  options?: Omit<UseQueryOptions<KYCSubmission, Error>, 'queryKey' | 'queryFn'>,
) {
  return useQuery<KYCSubmission, Error>({
    queryKey: kycKeys.submission(id),
    queryFn:  () => kycService.getSubmission(id),
    enabled:  !!id,
    ...options,
  });
}

export function useKYCSubmissionStatus(id: string, enabled = true) {
  return useQuery({
    queryKey:       kycKeys.submissionStatus(id),
    queryFn:        () => kycService.getSubmissionStatus(id),
    enabled:        !!id && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      // Stop polling once in a terminal state
      if (status === 'APPROVED' || status === 'REJECTED') return false;
      return 5_000;
    },
    staleTime: 0,
  });
}

export function useLatestKYCSubmission() {
  return useQuery<KYCSubmission | null, Error>({
    queryKey: kycKeys.latestSubmission,
    queryFn:  () => kycService.getLatestSubmission(),
    staleTime: 60_000,
  });
}

export function useSubmitKYC() {
  const queryClient = useQueryClient();

  return useMutation<KYCSubmission, Error, KYCSubmitRequest>({
    mutationFn: (payload) => kycService.submitKYC(payload),
    onSuccess: (submission) => {
      queryClient.invalidateQueries({ queryKey: kycKeys.all });
      queryClient.setQueryData(kycKeys.submission(submission.id), submission);
      toast.success('KYC application submitted successfully!');
    },
    onError: (error) => {
      toast.error(error.message ?? 'Failed to submit KYC application.');
    },
  });
}

// ─── Admin Hooks ──────────────────────────────────────────────────────────────

export function useAdminSubmissions(filters: SubmissionFilter = {}) {
  return useQuery<PaginatedResponse<KYCSubmission>, Error>({
    queryKey: kycKeys.adminSubmissions(filters),
    queryFn:  () => kycService.adminGetSubmissions(filters),
    staleTime: 15_000,
  });
}

export function useAdminStats() {
  return useQuery<AdminStats, Error>({
    queryKey:       kycKeys.adminStats,
    queryFn:        () => kycService.getAdminStats(),
    refetchInterval: 60_000,
    staleTime:       30_000,
  });
}

export function useAdminChartData(days = 30) {
  return useQuery({
    queryKey: kycKeys.chartData(days),
    queryFn:  () => kycService.getSubmissionsChartData(days),
    staleTime: 300_000,
  });
}

export function useAdminOverride() {
  const queryClient = useQueryClient();

  return useMutation<
    KYCSubmission,
    Error,
    { id: string; override: AdminOverrideRequest }
  >({
    mutationFn: ({ id, override }) =>
      kycService.adminOverrideDecision(id, override),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'kyc'] });
      queryClient.invalidateQueries({ queryKey: kycKeys.adminStats });
      queryClient.setQueryData(kycKeys.submission(updated.id), updated);
      toast.success('Decision overridden successfully.');
    },
    onError: (error) => {
      toast.error(error.message ?? 'Failed to override decision.');
    },
  });
}
