/**
 * WorkflowPanel
 *
 * Renders the 5-step admin verification workflow as a visual stepper.
 * Each step shows its status, score, and expandable detail summary.
 * Matches the banking operations dashboard style.
 */

import React, { useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  ChevronDown,
  ChevronRight,
  FileSearch,
  ShieldCheck,
  Building2,
  Fingerprint,
  FileText,
} from 'lucide-react';
import { WorkflowStep } from '@/services/admin.service';

// ─── Step metadata ─────────────────────────────────────────────────────────

const STEP_META: Record<string, { label: string; description: string; Icon: React.ElementType }> = {
  customer_document_analysis: {
    label: 'Customer Document Analysis',
    description: 'Analyses document type, quality, completeness and tampering indicators.',
    Icon: FileSearch,
  },
  customer_compliance_review: {
    label: 'Customer Compliance Review',
    description: 'Screens applicant against sanctions, PEP lists and high-risk country rules.',
    Icon: ShieldCheck,
  },
  government_identity_validation: {
    label: 'Government Identity Validation',
    description: 'Validates extracted identity details against government records.',
    Icon: Building2,
  },
  identity_verification: {
    label: 'Identity Verification',
    description: 'Consolidates all checks into a final identity confidence score.',
    Icon: Fingerprint,
  },
  final_report_generation: {
    label: 'Final Report Generation',
    description: 'Generates a comprehensive structured KYC report for admin review.',
    Icon: FileText,
  },
};

const ADMIN_STEP_ORDER = [
  'customer_document_analysis',
  'customer_compliance_review',
  'government_identity_validation',
  'identity_verification',
  'final_report_generation',
];

// ─── Status helpers ─────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: WorkflowStep['status'] }) {
  if (status === 'completed')
    return <CheckCircle2 className="w-5 h-5 text-emerald-500" />;
  if (status === 'failed')
    return <XCircle className="w-5 h-5 text-red-500" />;
  if (status === 'in_progress')
    return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
  return <Clock className="w-5 h-5 text-neutral-400" />;
}

function statusBadge(status: WorkflowStep['status']) {
  const base = 'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium';
  switch (status) {
    case 'completed':  return `${base} bg-emerald-50 text-emerald-700`;
    case 'failed':     return `${base} bg-red-50 text-red-700`;
    case 'in_progress': return `${base} bg-blue-50 text-blue-700`;
    case 'skipped':    return `${base} bg-neutral-100 text-neutral-500`;
    default:           return `${base} bg-neutral-100 text-neutral-500`;
  }
}

function statusLabel(status: WorkflowStep['status']) {
  switch (status) {
    case 'in_progress': return 'In Progress';
    case 'completed':   return 'Completed';
    case 'failed':      return 'Failed';
    case 'skipped':     return 'Skipped';
    default:            return 'Pending';
  }
}

// ─── Single step row ──────────────────────────────────────────────────────

function StepRow({ step, index, isLast }: { step: WorkflowStep | null; stepName: string; index: number; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const meta = STEP_META[step?.step_name ?? ''] ?? STEP_META[ADMIN_STEP_ORDER[index]];
  const { label, description, Icon } = meta;

  const current = step ?? {
    id: '',
    step_name: ADMIN_STEP_ORDER[index],
    step_order: index + 2,
    status: 'pending' as const,
    summary: null,
    score: null,
    started_at: null,
    completed_at: null,
    duration_ms: null,
    details: null,
  };

  return (
    <div className="relative">
      {/* Connector line */}
      {!isLast && (
        <div
          className={`absolute left-5 top-10 w-0.5 h-full -z-0 ${
            current.status === 'completed' ? 'bg-emerald-300' : 'bg-neutral-200'
          }`}
        />
      )}

      <div className={`relative flex gap-4 pb-4 ${isLast ? '' : 'pb-6'}`}>
        {/* Icon bubble */}
        <div
          className={`flex-shrink-0 z-10 w-10 h-10 rounded-full flex items-center justify-center border-2 ${
            current.status === 'completed'
              ? 'bg-emerald-50 border-emerald-400'
              : current.status === 'in_progress'
              ? 'bg-blue-50 border-blue-400'
              : current.status === 'failed'
              ? 'bg-red-50 border-red-400'
              : 'bg-white border-neutral-200'
          }`}
        >
          <Icon
            className={`w-4 h-4 ${
              current.status === 'completed' ? 'text-emerald-600' :
              current.status === 'in_progress' ? 'text-blue-600' :
              current.status === 'failed' ? 'text-red-600' : 'text-neutral-400'
            }`}
          />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium text-neutral-900 text-sm">{label}</span>
                <span className={statusBadge(current.status)}>{statusLabel(current.status)}</span>
                {current.status === 'in_progress' && (
                  <span className="text-xs text-blue-600 animate-pulse">Processing…</span>
                )}
              </div>
              <p className="text-xs text-neutral-500 mt-0.5">{description}</p>
            </div>

            <div className="flex items-center gap-3 flex-shrink-0">
              {/* Score badge */}
              {current.score !== null && (
                <span className="text-xs font-mono font-semibold text-neutral-700 bg-neutral-100 px-2 py-0.5 rounded">
                  {(current.score * 100).toFixed(0)}%
                </span>
              )}
              {/* Status icon */}
              <StatusIcon status={current.status} />
              {/* Expand toggle */}
              {(current.summary || current.details) && (
                <button
                  onClick={() => setExpanded(!expanded)}
                  className="text-neutral-400 hover:text-neutral-600 transition-colors"
                >
                  {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                </button>
              )}
            </div>
          </div>

          {/* Summary line */}
          {current.summary && !expanded && (
            <p className="mt-1 text-xs text-neutral-600 line-clamp-1">{current.summary}</p>
          )}

          {/* Expanded detail */}
          {expanded && (
            <div className="mt-2 bg-neutral-50 rounded-lg border border-neutral-200 p-3 text-xs text-neutral-700 space-y-1">
              {current.summary && (
                <p className="font-medium text-neutral-800">{current.summary}</p>
              )}
              {current.started_at && (
                <p>Started: {new Date(current.started_at).toLocaleTimeString()}</p>
              )}
              {current.completed_at && (
                <p>Completed: {new Date(current.completed_at).toLocaleTimeString()}</p>
              )}
              {current.duration_ms !== null && (
                <p>Duration: {(current.duration_ms / 1000).toFixed(2)}s</p>
              )}
              {current.details && Object.keys(current.details).length > 0 && (
                <details className="mt-1">
                  <summary className="cursor-pointer text-blue-600 hover:underline">
                    View raw details
                  </summary>
                  <pre className="mt-1 overflow-auto text-[10px] bg-white p-2 rounded border border-neutral-200 max-h-48">
                    {JSON.stringify(current.details, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Progress bar ──────────────────────────────────────────────────────────

function ProgressBar({ pct, status }: { pct: number; status: string }) {
  return (
    <div className="mb-4">
      <div className="flex justify-between text-xs text-neutral-500 mb-1">
        <span>Verification Progress</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 bg-neutral-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${
            status === 'completed'
              ? 'bg-emerald-500'
              : status === 'completed_with_errors'
              ? 'bg-amber-500'
              : 'bg-blue-500'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────

interface WorkflowPanelProps {
  steps: WorkflowStep[];
  progressPct: number;
  workflowStatus: string;
  finalRecommendation: string | null;
  reportAvailable: boolean;
}

export function WorkflowPanel({
  steps,
  progressPct,
  workflowStatus,
  finalRecommendation,
  reportAvailable,
}: WorkflowPanelProps) {
  // Index steps by name for quick lookup
  const stepByName = Object.fromEntries(steps.map((s) => [s.step_name, s]));

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-neutral-800">Verification Workflow</h3>
        {workflowStatus === 'running' && (
          <span className="inline-flex items-center gap-1.5 text-xs text-blue-600 bg-blue-50 px-2.5 py-1 rounded-full font-medium">
            <Loader2 className="w-3 h-3 animate-spin" />
            Running
          </span>
        )}
        {(workflowStatus === 'completed' || workflowStatus === 'completed_with_errors') && (
          <span className="inline-flex items-center gap-1.5 text-xs text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full font-medium">
            <CheckCircle2 className="w-3 h-3" />
            Complete
          </span>
        )}
      </div>

      <ProgressBar pct={progressPct} status={workflowStatus} />

      <div className="space-y-0">
        {ADMIN_STEP_ORDER.map((stepName, idx) => (
          <StepRow
            key={stepName}
            step={stepByName[stepName] ?? null}
            stepName={stepName}
            index={idx}
            isLast={idx === ADMIN_STEP_ORDER.length - 1}
          />
        ))}
      </div>

      {/* Recommendation banner */}
      {reportAvailable && finalRecommendation && (
        <div
          className={`mt-4 px-4 py-3 rounded-xl text-sm font-medium flex items-center gap-2 ${
            finalRecommendation === 'approve'
              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
              : finalRecommendation === 'reject'
              ? 'bg-red-50 text-red-800 border border-red-200'
              : 'bg-amber-50 text-amber-800 border border-amber-200'
          }`}
        >
          {finalRecommendation === 'approve' && <CheckCircle2 className="w-4 h-4" />}
          {finalRecommendation === 'reject' && <XCircle className="w-4 h-4" />}
          {finalRecommendation === 'manual_review' && <Clock className="w-4 h-4" />}
          AI Recommendation:{' '}
          <span className="capitalize">{finalRecommendation.replace('_', ' ')}</span>
        </div>
      )}
    </div>
  );
}
