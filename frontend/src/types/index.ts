// ─── User & Auth ────────────────────────────────────────────────────────────

export type UserRole = 'customer' | 'admin' | 'reviewer' | 'analyst';

export interface User {
  id: string;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: UserRole;
  status: string;
  is_email_verified: boolean;
  phone_number?: string | null;
  date_of_birth?: string | null;
  nationality?: string | null;
  created_at: string;
  updated_at: string;
  last_login_at?: string | null;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/** Shape returned by /auth/login and /auth/register */
export interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  password: string;
  confirm_password: string;
}

// ─── KYC ────────────────────────────────────────────────────────────────────

export type KYCStatus =
  | 'PENDING'
  | 'PROCESSING'
  | 'APPROVED'
  | 'REJECTED'
  | 'MANUAL_REVIEW'
  | 'RESUBMISSION_REQUIRED';

export type KYCDocumentType =
  | 'PASSPORT'
  | 'NATIONAL_ID'
  | 'DRIVERS_LICENSE'
  | 'RESIDENCE_PERMIT';

export interface KYCPersonalInfo {
  first_name: string;
  last_name: string;
  date_of_birth: string;
  nationality: string;
  phone_number?: string;
}

export interface KYCIdentityDocument {
  document_type: KYCDocumentType;
  document_number: string;
  issue_date: string;
  expiry_date: string;
  issuing_country: string;
}

export interface KYCAddress {
  street_address: string;
  city: string;
  state: string;
  country: string;
  postal_code: string;
}

export interface KYCSubmission {
  id: string;
  user_id: string;
  user?: User;
  status: KYCStatus;
  personal_info: KYCPersonalInfo;
  identity_document: KYCIdentityDocument;
  address: KYCAddress;
  confidence_score?: number;
  ai_decision?: string;
  ai_reasoning?: string;
  admin_override?: boolean;
  admin_note?: string;
  admin_id?: string;
  documents?: Document[];
  fraud_report?: FraudReport;
  created_at: string;
  updated_at: string;
  reviewed_at?: string;
}

export interface KYCSubmitRequest {
  personal_info: KYCPersonalInfo;
  identity_document: KYCIdentityDocument;
  address: KYCAddress;
}

export interface KYCStatusEvent {
  status: KYCStatus;
  timestamp: string;
  message: string;
  actor?: string;
}

// ─── Documents ──────────────────────────────────────────────────────────────

export type DocumentStatus = 'UPLOADED' | 'PROCESSING' | 'VERIFIED' | 'REJECTED' | 'EXPIRED';

export interface Document {
  id: string;
  kyc_submission_id: string;
  document_type: KYCDocumentType;
  file_name: string;
  file_size: number;
  mime_type: string;
  side: 'FRONT' | 'BACK' | 'SELFIE';
  status: DocumentStatus;
  storage_url?: string;
  ocr_result?: OCRResult;
  created_at: string;
}

export interface OCRResult {
  id: string;
  document_id: string;
  extracted_text: string;
  confidence: number;
  fields: Record<string, OCRField>;
  raw_response?: unknown;
  created_at: string;
}

export interface OCRField {
  value: string;
  confidence: number;
  bounding_box?: number[];
}

// ─── Fraud ──────────────────────────────────────────────────────────────────

export interface FraudReport {
  id: string;
  kyc_submission_id: string;
  risk_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  flags: FraudFlag[];
  created_at: string;
}

export interface FraudFlag {
  type: string;
  description: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH';
}

// ─── Admin ───────────────────────────────────────────────────────────────────

export interface AdminStats {
  total_submissions: number;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  manual_review_count: number;
  approval_rate: number;
  average_confidence_score: number;
  submissions_today: number;
  submissions_this_week: number;
  submissions_this_month: number;
}

export interface AdminOverrideRequest {
  decision: 'APPROVED' | 'REJECTED' | 'MANUAL_REVIEW';
  reason: string;
}

export interface SubmissionFilter {
  status?: KYCStatus;
  date_from?: string;
  date_to?: string;
  search?: string;
  page?: number;
  limit?: number;
  sort_by?: 'created_at' | 'updated_at' | 'confidence_score';
  sort_order?: 'asc' | 'desc';
}

// ─── API ─────────────────────────────────────────────────────────────────────

export interface ApiResponse<T> {
  data: T;
  message: string;
  success: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface ApiError {
  message: string;
  detail?: string | Record<string, string[]>;
  status_code?: number;
}

// ─── Chart Data ──────────────────────────────────────────────────────────────

export interface SubmissionChartData {
  date: string;
  total: number;
  approved: number;
  rejected: number;
  pending: number;
}

export interface StatusDistributionData {
  name: string;
  value: number;
  color: string;
}
