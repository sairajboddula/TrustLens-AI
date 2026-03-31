import api from './api';
import type {
  KYCSubmission,
  KYCSubmitRequest,
  AdminStats,
  AdminOverrideRequest,
  SubmissionFilter,
  PaginatedResponse,
  KYCStatus,
  KYCDocumentType,
  KYCPersonalInfo,
  KYCIdentityDocument,
  KYCAddress,
} from '@/types';

const KYC   = '/kyc';
const ADMIN = '/admin';

// ─── Normalisation Helpers ────────────────────────────────────────────────────

/**
 * Map the backend's lowercase status enum values to the uppercase
 * values expected throughout the frontend UI.
 */
function normalizeStatus(raw: string): KYCStatus {
  const map: Record<string, KYCStatus> = {
    draft:        'PENDING',
    submitted:    'PENDING',
    processing:   'PROCESSING',
    under_review: 'MANUAL_REVIEW',
    approved:     'APPROVED',
    rejected:     'REJECTED',
    expired:      'REJECTED',
    cancelled:    'REJECTED',
  };
  return map[raw] ?? (raw.toUpperCase() as KYCStatus);
}

/**
 * Convert a backend KYCSubmissionSummary (list item) to the frontend
 * KYCSubmission shape expected by all components.
 */
function normalizeSummary(item: Record<string, unknown>): KYCSubmission {
  const fullName = (item.applicant_full_name as string | undefined) ?? '';
  const [firstName = '', ...rest] = fullName.split(' ');
  const lastName = rest.join(' ');

  const docType = ((item.primary_document_type as string | undefined) ?? '').toUpperCase() as KYCDocumentType;

  return {
    id:      item.id as string,
    user_id: '',
    status:  normalizeStatus(item.status as string),
    personal_info: {
      first_name:   firstName,
      last_name:    lastName,
      date_of_birth: '',
      nationality:  '',
    } as KYCPersonalInfo,
    identity_document: {
      document_type:    docType,
      document_number:  '',
      issue_date:       '',
      expiry_date:      '',
      issuing_country:  '',
    } as KYCIdentityDocument,
    address: {
      street_address: '',
      city:           '',
      state:          '',
      country:        '',
      postal_code:    '',
    } as KYCAddress,
    confidence_score: item.ai_confidence_score as number | undefined,
    created_at:       item.created_at as string,
    updated_at:       (item.updated_at as string | undefined) ?? (item.created_at as string),
  };
}

/**
 * Convert a backend KYCSubmissionResponse (full detail) to the frontend
 * KYCSubmission shape.
 */
function normalizeDetail(item: Record<string, unknown>): KYCSubmission {
  const aiVerification = item.ai_verification as Record<string, unknown> | undefined | null;
  const docType = ((item.primary_document_type as string | undefined) ?? '').toUpperCase() as KYCDocumentType;
  const user = item.user as Record<string, unknown> | undefined | null;

  // Parse applicant_address string into address object
  const addressStr = (item.applicant_address as string | undefined) ?? '';
  const addrParts  = addressStr.split(',').map((s) => s.trim());

  return {
    id:      item.id as string,
    user_id: (user?.id as string | undefined) ?? '',
    user:    user as KYCSubmission['user'],
    status:  normalizeStatus(item.status as string),
    personal_info: {
      first_name:    (item.applicant_first_name as string | undefined) ?? '',
      last_name:     (item.applicant_last_name  as string | undefined) ?? '',
      date_of_birth: (item.applicant_date_of_birth as string | undefined) ?? '',
      nationality:   (item.applicant_nationality  as string | undefined) ?? '',
      phone_number:  item.applicant_phone as string | undefined,
    } as KYCPersonalInfo,
    identity_document: {
      document_type:   docType,
      document_number: (item.primary_document_number as string | undefined) ?? '',
      issue_date:      '',
      expiry_date:     (item.primary_document_expiry as string | undefined) ?? '',
      issuing_country: (item.primary_document_issuing_country as string | undefined) ?? '',
    } as KYCIdentityDocument,
    address: {
      street_address: addrParts[0] ?? '',
      city:           addrParts[1] ?? '',
      state:          addrParts[2] ?? '',
      country:        addrParts[3] ?? '',
      postal_code:    addrParts[4] ?? '',
    } as KYCAddress,
    confidence_score: (aiVerification?.confidence_score as number | undefined) ?? undefined,
    ai_decision:      item.status as string | undefined,
    ai_reasoning:     (item.reviewer_notes as string | undefined),
    admin_override:   !!(item.reviewer_id),
    admin_note:       item.reviewer_notes as string | undefined,
    documents:        item.documents as KYCSubmission['documents'],
    created_at:       item.created_at as string,
    updated_at:       item.updated_at as string,
    reviewed_at:      item.reviewed_at as string | undefined,
  };
}

// ─── Service ──────────────────────────────────────────────────────────────────

export const kycService = {
  // ─── User Endpoints ─────────────────────────────────────────────────────────

  /**
   * Submit a new KYC application.
   * Transforms the frontend nested payload into the flat backend format.
   */
  async submitKYC(payload: KYCSubmitRequest): Promise<KYCSubmission> {
    const backendPayload = {
      applicant_first_name:    payload.personal_info.first_name,
      applicant_last_name:     payload.personal_info.last_name,
      applicant_date_of_birth: payload.personal_info.date_of_birth || null,
      applicant_nationality:   payload.personal_info.nationality   || null,
      applicant_address: [
        payload.address.street_address,
        payload.address.city,
        payload.address.state,
        payload.address.country,
        payload.address.postal_code,
      ].filter(Boolean).join(', '),
      applicant_phone:              payload.personal_info.phone_number  || null,
      primary_document_type:        payload.identity_document.document_type.toLowerCase(),
      primary_document_number:      payload.identity_document.document_number || null,
      primary_document_expiry:      payload.identity_document.expiry_date || null,
    };

    const { data } = await api.post<Record<string, unknown>>(`${KYC}/submit`, backendPayload);
    return normalizeDetail(data);
  },

  /**
   * Get a paginated list of the current user's submissions.
   */
  async getSubmissions(page = 1, limit = 10): Promise<PaginatedResponse<KYCSubmission>> {
    const { data } = await api.get<{
      items: Record<string, unknown>[];
      total: number;
      page:  number;
      size:  number;
      pages: number;
    }>(`${KYC}/submissions`, { params: { page, size: limit } });

    return {
      items: data.items.map(normalizeSummary),
      total: data.total,
      page:  data.page,
      size:  data.size,
      pages: data.pages,
    };
  },

  /**
   * Get a single submission by ID.
   */
  async getSubmission(id: string): Promise<KYCSubmission> {
    const { data } = await api.get<Record<string, unknown>>(`${KYC}/submissions/${id}`);
    return normalizeDetail(data);
  },

  /**
   * Get real-time status of a submission.
   */
  async getSubmissionStatus(
    id: string,
  ): Promise<{ status: KYCSubmission['status']; confidence_score?: number }> {
    const { data } = await api.get<Record<string, unknown>>(
      `${KYC}/submissions/${id}/status`,
    );
    return {
      status:           normalizeStatus(data.status as string),
      confidence_score: data.ai_confidence_score as number | undefined,
    };
  },

  /**
   * Get the most recent submission for the current user.
   */
  async getLatestSubmission(): Promise<KYCSubmission | null> {
    try {
      const result = await kycService.getSubmissions(1, 1);
      return result.items[0] ?? null;
    } catch {
      return null;
    }
  },

  // ─── Admin Endpoints ─────────────────────────────────────────────────────────

  /**
   * Admin: list all submissions with optional filters.
   */
  async adminGetSubmissions(filters: SubmissionFilter = {}): Promise<PaginatedResponse<KYCSubmission>> {
    // Map frontend uppercase status to backend lowercase before sending
    const statusMap: Record<string, string> = {
      PENDING:       'submitted',
      PROCESSING:    'processing',
      APPROVED:      'approved',
      REJECTED:      'rejected',
      MANUAL_REVIEW: 'under_review',
    };
    const params: Record<string, unknown> = {
      ...filters,
      status: filters.status ? (statusMap[filters.status] ?? filters.status.toLowerCase()) : undefined,
    };

    const { data } = await api.get<{
      items: Record<string, unknown>[];
      total: number;
      page:  number;
      size:  number;
      pages: number;
    }>(`${ADMIN}/kyc/submissions`, { params });

    return {
      items: data.items.map(normalizeSummary),
      total: data.total,
      page:  data.page,
      size:  data.size,
      pages: data.pages,
    };
  },

  /**
   * Admin: retrieve a single submission.
   */
  async adminGetSubmission(id: string): Promise<KYCSubmission> {
    const { data } = await api.get<Record<string, unknown>>(
      `${ADMIN}/kyc/submissions/${id}`,
    );
    return normalizeDetail(data);
  },

  /**
   * Admin: override the AI decision for a submission.
   * Maps frontend { decision, reason } to backend { status, reason }.
   */
  async adminOverrideDecision(
    id: string,
    override: AdminOverrideRequest,
  ): Promise<KYCSubmission> {
    const decisionToStatus: Record<string, string> = {
      APPROVED:      'approved',
      REJECTED:      'rejected',
      MANUAL_REVIEW: 'under_review',
    };
    const backendPayload = {
      status: decisionToStatus[override.decision] ?? override.decision.toLowerCase(),
      reason: override.reason,
    };
    const { data } = await api.post<Record<string, unknown>>(
      `${ADMIN}/kyc/submissions/${id}/override`,
      backendPayload,
    );
    return normalizeDetail(data);
  },

  /**
   * Admin: get aggregate statistics.
   * Transforms the backend KYCStatsResponse to the frontend AdminStats shape.
   */
  async getAdminStats(): Promise<AdminStats> {
    const { data } = await api.get<{
      total_submissions:         number;
      by_status:                 Record<string, number>;
      by_risk_level:             Record<string, number>;
      auto_approved:             number;
      auto_rejected:             number;
      manual_review:             number;
      avg_processing_time_seconds?: number | null;
      approval_rate?:            number | null;
    }>(`${ADMIN}/stats`);

    const byStatus = data.by_status ?? {};

    // "pending" submissions = draft + submitted (awaiting processing)
    const pendingCount = (byStatus.draft ?? 0) + (byStatus.submitted ?? 0);
    // "processing" = currently being processed by AI
    const processingCount = byStatus.processing ?? 0;

    return {
      total_submissions:        data.total_submissions   ?? 0,
      pending_count:            pendingCount + processingCount,
      approved_count:           byStatus.approved        ?? 0,
      rejected_count:           byStatus.rejected        ?? 0,
      manual_review_count:      byStatus.under_review    ?? data.manual_review ?? 0,
      approval_rate:            data.approval_rate       ?? 0,
      average_confidence_score: 0,
      submissions_today:        0,
      submissions_this_week:    0,
      submissions_this_month:   0,
    };
  },

  /**
   * Admin: get chart data for submissions over time.
   */
  async getSubmissionsChartData(days = 30) {
    try {
      const { data } = await api.get<unknown>(
        `${ADMIN}/stats/submissions-over-time`,
        { params: { days } },
      );
      return data;
    } catch {
      return [];
    }
  },
};
