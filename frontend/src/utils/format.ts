import { format, formatDistanceToNow, parseISO, isValid } from 'date-fns';
import type { KYCStatus, DocumentStatus } from '@/types';

// ─── Date Formatting ─────────────────────────────────────────────────────────

export function formatDate(dateStr: string | undefined | null, pattern = 'MMM d, yyyy'): string {
  if (!dateStr) return '—';
  try {
    const date = parseISO(dateStr);
    return isValid(date) ? format(date, pattern) : '—';
  } catch {
    return '—';
  }
}

export function formatDateTime(dateStr: string | undefined | null): string {
  return formatDate(dateStr, 'MMM d, yyyy HH:mm');
}

export function formatRelativeTime(dateStr: string | undefined | null): string {
  if (!dateStr) return '—';
  try {
    const date = parseISO(dateStr);
    return isValid(date) ? formatDistanceToNow(date, { addSuffix: true }) : '—';
  } catch {
    return '—';
  }
}

export function formatDateInput(dateStr: string | undefined | null): string {
  return formatDate(dateStr, 'yyyy-MM-dd');
}

// ─── Number Formatting ───────────────────────────────────────────────────────

export function formatPercent(value: number | undefined | null, decimals = 1): string {
  if (value == null) return '—';
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatScore(value: number | undefined | null): string {
  if (value == null) return '—';
  return `${Math.round(value * 100)}%`;
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

export function formatNumber(value: number | undefined | null): string {
  if (value == null) return '—';
  return new Intl.NumberFormat('en-US').format(value);
}

// ─── Status Formatting ───────────────────────────────────────────────────────

export const KYC_STATUS_LABELS: Record<KYCStatus, string> = {
  PENDING:                'Pending',
  PROCESSING:             'Processing',
  APPROVED:               'Approved',
  REJECTED:               'Rejected',
  MANUAL_REVIEW:          'Manual Review',
  RESUBMISSION_REQUIRED:  'Resubmission Required',
};

export const KYC_STATUS_COLORS: Record<KYCStatus, string> = {
  PENDING:                'yellow',
  PROCESSING:             'blue',
  APPROVED:               'green',
  REJECTED:               'red',
  MANUAL_REVIEW:          'orange',
  RESUBMISSION_REQUIRED:  'purple',
};

export const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  UPLOADED:   'Uploaded',
  PROCESSING: 'Processing',
  VERIFIED:   'Verified',
  REJECTED:   'Rejected',
  EXPIRED:    'Expired',
};

export function getKYCStatusLabel(status: KYCStatus): string {
  return KYC_STATUS_LABELS[status] ?? status;
}

export function getInitials(name: string): string {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export function truncate(str: string, maxLength = 50): string {
  if (str.length <= maxLength) return str;
  return `${str.slice(0, maxLength)}…`;
}

export function formatDocumentType(type: string): string {
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}
