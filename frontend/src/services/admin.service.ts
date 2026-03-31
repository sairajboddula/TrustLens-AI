/**
 * Admin Workflow Service
 *
 * API calls for the extended admin review workflow:
 *  - start / poll workflow
 *  - get final report
 *  - approve / reject / manual-review
 *  - save notes
 *  - get timeline
 */

import api from './api';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface WorkflowStep {
  id: string;
  step_name: string;
  step_order: number;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';
  summary: string | null;
  score: number | null;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  details: Record<string, unknown> | null;
}

export interface WorkflowStatusResponse {
  submission_id: string;
  workflow_status: 'pending' | 'running' | 'completed' | 'completed_with_errors' | 'failed';
  progress_pct: number;
  steps: WorkflowStep[];
  final_recommendation: string | null;
  report_available: boolean;
}

export interface FinalReport {
  submission_id: string;
  report: Record<string, unknown> | null;
  final_confidence_score: number | null;
  recommended_action: string | null;
  fraud_detected: boolean;
  compliance_passed: boolean;
  government_validated: boolean;
  identity_verified: boolean;
  document_quality_score: number | null;
  generated_at: string | null;
}

export interface TimelineEvent {
  id: string;
  event_type: string;
  event_title: string;
  event_detail: string | null;
  actor: string | null;
  occurred_at: string;
}

// ─── API calls ────────────────────────────────────────────────────────────────

export const adminWorkflowService = {
  /**
   * Kick off the full verification pipeline for a submission.
   * Returns immediately; poll /status for progress.
   */
  async startWorkflow(submissionId: string) {
    const res = await api.post(`/admin/workflow/${submissionId}/start`);
    return res.data as { message: string; submission_id: string; status: string };
  },

  /** Poll current step statuses and progress. */
  async getWorkflowStatus(submissionId: string) {
    const res = await api.get(`/admin/workflow/${submissionId}/status`);
    return res.data as WorkflowStatusResponse;
  },

  /** Retrieve the generated KYC final report. */
  async getFinalReport(submissionId: string) {
    const res = await api.get(`/admin/workflow/${submissionId}/report`);
    return res.data as FinalReport;
  },

  /** Approve a KYC case. */
  async approveCase(submissionId: string, notes?: string) {
    const res = await api.post(`/admin/workflow/${submissionId}/approve`, { notes });
    return res.data;
  },

  /** Reject a KYC case. */
  async rejectCase(submissionId: string, notes?: string) {
    const res = await api.post(`/admin/workflow/${submissionId}/reject`, { notes });
    return res.data;
  },

  /** Mark a KYC case for manual review. */
  async manualReviewCase(submissionId: string, notes?: string) {
    const res = await api.post(`/admin/workflow/${submissionId}/manual-review`, { notes });
    return res.data;
  },

  /** Save admin notes without changing case status. */
  async saveNotes(submissionId: string, notes: string) {
    const res = await api.post(`/admin/workflow/${submissionId}/notes`, { notes });
    return res.data;
  },

  /** Fetch ordered timeline events for the case. */
  async getTimeline(submissionId: string) {
    const res = await api.get(`/admin/workflow/${submissionId}/timeline`);
    return res.data as TimelineEvent[];
  },

  /** Fetch full submission details (existing admin endpoint). */
  async getSubmission(submissionId: string) {
    const res = await api.get(`/admin/kyc/submissions/${submissionId}`);
    return res.data;
  },
};

export default adminWorkflowService;
