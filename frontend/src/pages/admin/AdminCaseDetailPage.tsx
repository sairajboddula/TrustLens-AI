/**
 * AdminCaseDetailPage
 *
 * Full admin review page for a single KYC case.
 *
 * Layout (banking operations dashboard style):
 *  ┌───────────────────────────────────────────────────────────────┐
 *  │ Header: case info + Run ID & Verification button              │
 *  ├─────────────────────┬────────────────────┬────────────────────┤
 *  │ LEFT                │ CENTER             │ RIGHT              │
 *  │ Timeline / Journey  │ Workflow Steps     │ Final Report       │
 *  │ Log                 │ (stepper)          │ Viewer             │
 *  └─────────────────────┴────────────────────┴────────────────────┘
 *  Footer: Approve / Reject / Manual Review buttons + notes
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Clock,
  Play,
  Loader2,
  User,
  FileText,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react';

import adminWorkflowService, {
  FinalReport,
  TimelineEvent,
  WorkflowStatusResponse,
} from '@/services/admin.service';
import { WorkflowPanel } from '@/components/admin/WorkflowPanel';
import { TimelineLog } from '@/components/admin/TimelineLog';
import { FinalReportViewer } from '@/components/admin/FinalReportViewer';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusBadge(status: string) {
  const base = 'inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium';
  switch (status) {
    case 'approved':     return `${base} bg-emerald-50 text-emerald-700`;
    case 'rejected':     return `${base} bg-red-50 text-red-700`;
    case 'under_review': return `${base} bg-amber-50 text-amber-700`;
    case 'processing':   return `${base} bg-blue-50 text-blue-700`;
    default:             return `${base} bg-neutral-100 text-neutral-500`;
  }
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function AdminCaseDetailPage() {
  const { submissionId } = useParams<{ submissionId: string }>();
  const navigate = useNavigate();

  // Data state
  const [submission, setSubmission] = useState<any>(null);
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatusResponse | null>(null);
  const [finalReport, setFinalReport] = useState<FinalReport | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);

  // UI state
  const [loading, setLoading] = useState(true);
  const [workflowRunning, setWorkflowRunning] = useState(false);
  const [adminNotes, setAdminNotes] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const [activeTab, setActiveTab] = useState<'report' | 'raw'>('report');
  const [decisionLoading, setDecisionLoading] = useState<string | null>(null);

  // Polling ref
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const fetchTimeline = useCallback(async () => {
    if (!submissionId) return;
    try {
      const events = await adminWorkflowService.getTimeline(submissionId);
      setTimeline(events);
    } catch {}
  }, [submissionId]);

  const fetchReport = useCallback(async () => {
    if (!submissionId) return;
    try {
      const report = await adminWorkflowService.getFinalReport(submissionId);
      setFinalReport(report);
    } catch {}
  }, [submissionId]);

  const pollStatus = useCallback(async () => {
    if (!submissionId) return;
    try {
      const status = await adminWorkflowService.getWorkflowStatus(submissionId);
      setWorkflowStatus(status);

      if (status.report_available) {
        await fetchReport();
      }

      await fetchTimeline();

      const stillRunning = status.workflow_status === 'running';
      if (stillRunning) {
        pollRef.current = setTimeout(pollStatus, 2000);
      } else {
        setWorkflowRunning(false);
        stopPolling();
      }
    } catch (err) {
      setWorkflowRunning(false);
      stopPolling();
    }
  }, [submissionId, fetchReport, fetchTimeline, stopPolling]);

  // Initial load
  useEffect(() => {
    if (!submissionId) return;

    const load = async () => {
      setLoading(true);
      try {
        const [sub, wfStatus, events] = await Promise.all([
          adminWorkflowService.getSubmission(submissionId),
          adminWorkflowService.getWorkflowStatus(submissionId).catch(() => null),
          adminWorkflowService.getTimeline(submissionId).catch(() => []),
        ]);
        setSubmission(sub);
        if (wfStatus) {
          setWorkflowStatus(wfStatus);
          if (wfStatus.report_available) await fetchReport();
          if (wfStatus.workflow_status === 'running') {
            setWorkflowRunning(true);
            pollRef.current = setTimeout(pollStatus, 2000);
          }
        }
        setTimeline(events as TimelineEvent[]);
        if (sub?.reviewer_notes) setAdminNotes(sub.reviewer_notes);
      } catch (err) {
        toast.error('Failed to load case details.');
      } finally {
        setLoading(false);
      }
    };

    load();
    return () => stopPolling();
  }, [submissionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRunWorkflow = async () => {
    if (!submissionId) return;
    setWorkflowRunning(true);
    try {
      await adminWorkflowService.startWorkflow(submissionId);
      toast.success('Verification pipeline started.');
      // Start polling immediately
      pollRef.current = setTimeout(pollStatus, 1000);
    } catch (err: any) {
      setWorkflowRunning(false);
      toast.error(err?.response?.data?.detail || 'Failed to start workflow.');
    }
  };

  const handleDecision = async (type: 'approve' | 'reject' | 'manual_review') => {
    if (!submissionId) return;
    setDecisionLoading(type);
    try {
      const notes = adminNotes.trim() || undefined;
      if (type === 'approve') await adminWorkflowService.approveCase(submissionId, notes);
      else if (type === 'reject') await adminWorkflowService.rejectCase(submissionId, notes);
      else await adminWorkflowService.manualReviewCase(submissionId, notes);

      toast.success(`Case ${type.replace('_', ' ')} successfully.`);
      // Refresh submission
      const sub = await adminWorkflowService.getSubmission(submissionId);
      setSubmission(sub);
      await fetchTimeline();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Decision failed.');
    } finally {
      setDecisionLoading(null);
    }
  };

  const handleSaveNotes = async () => {
    if (!submissionId || !adminNotes.trim()) return;
    setSavingNotes(true);
    try {
      await adminWorkflowService.saveNotes(submissionId, adminNotes);
      toast.success('Notes saved.');
      await fetchTimeline();
    } catch {
      toast.error('Failed to save notes.');
    } finally {
      setSavingNotes(false);
    }
  };

  // ─── Render ─────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    );
  }

  if (!submission) {
    return (
      <div className="p-6 text-center text-neutral-500">
        Case not found.
        <button onClick={() => navigate(-1)} className="ml-2 text-blue-600 underline">
          Go back
        </button>
      </div>
    );
  }

  const caseStatus = submission.status ?? 'unknown';
  const isTerminal = ['approved', 'rejected'].includes(caseStatus);

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* ─── Header ─────────────────────────────────────────────────────────── */}
      <div className="bg-white border-b border-neutral-200 px-6 py-4">
        <div className="max-w-screen-2xl mx-auto">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate('/admin/submissions')}
                className="p-1.5 rounded-lg hover:bg-neutral-100 transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-neutral-600" />
              </button>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-lg font-bold text-neutral-900">
                    {submission.applicant_first_name} {submission.applicant_last_name}
                  </h1>
                  <span className={statusBadge(caseStatus)}>{caseStatus.replace('_', ' ').toUpperCase()}</span>
                </div>
                <p className="text-xs text-neutral-500">
                  {submission.reference_number} · Submitted {
                    submission.submitted_at
                      ? new Date(submission.submitted_at).toLocaleDateString()
                      : 'N/A'
                  }
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Manual refresh */}
              <button
                onClick={async () => { await pollStatus(); toast.success('Refreshed'); }}
                className="p-2 rounded-lg border border-neutral-200 hover:bg-neutral-50 transition-colors"
                title="Refresh status"
              >
                <RefreshCw className="w-4 h-4 text-neutral-500" />
              </button>

              {/* ★ Primary action: Run ID & Verification */}
              <button
                onClick={handleRunWorkflow}
                disabled={workflowRunning}
                className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                  workflowRunning
                    ? 'bg-blue-400 text-white cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700 text-white shadow-sm hover:shadow-md'
                }`}
              >
                {workflowRunning ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Running…
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Run ID &amp; Verification
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ─── Main 3-column layout ───────────────────────────────────────────── */}
      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-5 grid grid-cols-1 lg:grid-cols-[280px_1fr_380px] gap-5">
        {/* LEFT – Timeline */}
        <div>
          <TimelineLog events={timeline} />
        </div>

        {/* CENTER – Workflow panel */}
        <div className="space-y-5">
          <WorkflowPanel
            steps={workflowStatus?.steps ?? []}
            progressPct={workflowStatus?.progress_pct ?? 0}
            workflowStatus={workflowStatus?.workflow_status ?? 'pending'}
            finalRecommendation={workflowStatus?.final_recommendation ?? null}
            reportAvailable={workflowStatus?.report_available ?? false}
          />

          {/* Case metadata card */}
          <div className="bg-white rounded-2xl border border-neutral-200 p-5">
            <h3 className="font-semibold text-neutral-800 mb-4 flex items-center gap-2">
              <User className="w-4 h-4 text-neutral-500" />
              Applicant Details
            </h3>
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              {[
                ['Full Name', `${submission.applicant_first_name} ${submission.applicant_last_name}`],
                ['Date of Birth', submission.applicant_date_of_birth ? new Date(submission.applicant_date_of_birth).toLocaleDateString() : '—'],
                ['Nationality', submission.applicant_nationality ?? '—'],
                ['Document Type', submission.primary_document_type ?? '—'],
                ['Document Number', submission.primary_document_number ?? '—'],
                ['Risk Level', submission.risk_level ?? '—'],
                ['AI Confidence', submission.ai_confidence_score != null ? `${(submission.ai_confidence_score * 100).toFixed(0)}%` : '—'],
                ['Email', submission.applicant_email ?? '—'],
              ].map(([label, value]) => (
                <div key={label}>
                  <p className="text-xs text-neutral-400">{label}</p>
                  <p className="text-neutral-800 font-medium">{value}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Admin notes */}
          <div className="bg-white rounded-2xl border border-neutral-200 p-5">
            <h3 className="font-semibold text-neutral-800 mb-3">Admin Notes</h3>
            <textarea
              value={adminNotes}
              onChange={(e) => setAdminNotes(e.target.value)}
              placeholder="Add notes, observations, or reasons for your decision…"
              rows={4}
              className="w-full text-sm border border-neutral-200 rounded-xl px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              onClick={handleSaveNotes}
              disabled={savingNotes || !adminNotes.trim()}
              className="mt-2 text-sm px-4 py-1.5 rounded-lg bg-neutral-100 hover:bg-neutral-200 text-neutral-700 transition-colors disabled:opacity-50"
            >
              {savingNotes ? 'Saving…' : 'Save Notes'}
            </button>
          </div>

          {/* Decision buttons */}
          <div className="bg-white rounded-2xl border border-neutral-200 p-5">
            <h3 className="font-semibold text-neutral-800 mb-4">Admin Decision</h3>
            {isTerminal ? (
              <div className={`px-4 py-3 rounded-xl text-sm font-medium flex items-center gap-2 ${
                caseStatus === 'approved' ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-800'
              }`}>
                {caseStatus === 'approved' ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                Case has been {caseStatus}
                {submission.reviewed_at && (
                  <span className="ml-auto text-xs opacity-70">
                    {new Date(submission.reviewed_at).toLocaleString()}
                  </span>
                )}
              </div>
            ) : (
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => handleDecision('approve')}
                  disabled={!!decisionLoading}
                  className="flex-1 min-w-[120px] inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-xl transition-all disabled:opacity-50 shadow-sm"
                >
                  {decisionLoading === 'approve' ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                  Approve
                </button>
                <button
                  onClick={() => handleDecision('reject')}
                  disabled={!!decisionLoading}
                  className="flex-1 min-w-[120px] inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-red-600 hover:bg-red-700 text-white text-sm font-semibold rounded-xl transition-all disabled:opacity-50 shadow-sm"
                >
                  {decisionLoading === 'reject' ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                  Reject
                </button>
                <button
                  onClick={() => handleDecision('manual_review')}
                  disabled={!!decisionLoading}
                  className="flex-1 min-w-[120px] inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-white text-sm font-semibold rounded-xl transition-all disabled:opacity-50 shadow-sm"
                >
                  {decisionLoading === 'manual_review' ? <Loader2 className="w-4 h-4 animate-spin" /> : <AlertTriangle className="w-4 h-4" />}
                  Manual Review
                </button>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT – Final Report */}
        <div>
          <div className="bg-white rounded-2xl border border-neutral-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-neutral-800 flex items-center gap-2">
                <FileText className="w-4 h-4 text-neutral-500" />
                Final Report
              </h3>
              {finalReport && (
                <div className="flex border border-neutral-200 rounded-lg overflow-hidden text-xs">
                  <button
                    onClick={() => setActiveTab('report')}
                    className={`px-3 py-1.5 font-medium transition-colors ${
                      activeTab === 'report' ? 'bg-neutral-900 text-white' : 'hover:bg-neutral-50 text-neutral-600'
                    }`}
                  >
                    Structured
                  </button>
                  <button
                    onClick={() => setActiveTab('raw')}
                    className={`px-3 py-1.5 font-medium transition-colors ${
                      activeTab === 'raw' ? 'bg-neutral-900 text-white' : 'hover:bg-neutral-50 text-neutral-600'
                    }`}
                  >
                    Raw JSON
                  </button>
                </div>
              )}
            </div>

            {!workflowStatus?.report_available && !finalReport ? (
              <div className="text-center py-10 text-neutral-400">
                <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
                <p className="text-sm">Report will appear here after running the verification workflow.</p>
                {!workflowRunning && (
                  <button
                    onClick={handleRunWorkflow}
                    className="mt-3 text-sm text-blue-600 hover:underline inline-flex items-center gap-1"
                  >
                    <Play className="w-3.5 h-3.5" />
                    Run ID &amp; Verification
                  </button>
                )}
              </div>
            ) : workflowRunning && !finalReport ? (
              <div className="text-center py-10 text-neutral-400">
                <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin text-blue-500" />
                <p className="text-sm">Generating report…</p>
              </div>
            ) : finalReport ? (
              activeTab === 'report' ? (
                <FinalReportViewer report={finalReport} />
              ) : (
                <pre className="text-[10px] overflow-auto max-h-[70vh] bg-neutral-50 p-3 rounded-lg border border-neutral-200">
                  {JSON.stringify(finalReport, null, 2)}
                </pre>
              )
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
