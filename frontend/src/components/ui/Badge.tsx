import React from 'react';
import { cn } from '@/utils/cn';
import type { KYCStatus } from '@/types';

// ─── Types ────────────────────────────────────────────────────────────────────

type BadgeColor =
  | 'gray'
  | 'blue'
  | 'green'
  | 'yellow'
  | 'red'
  | 'orange'
  | 'purple'
  | 'pink';

type BadgeSize = 'sm' | 'md' | 'lg';

export interface BadgeProps {
  color?:     BadgeColor;
  size?:      BadgeSize;
  dot?:       boolean;
  children:   React.ReactNode;
  className?: string;
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const colorStyles: Record<BadgeColor, string> = {
  gray:   'bg-neutral-100 text-neutral-700 ring-neutral-200/50',
  blue:   'bg-primary-100 text-primary-700 ring-primary-200/50',
  green:  'bg-success-100 text-success-700 ring-success-200/50',
  yellow: 'bg-warning-100 text-warning-700 ring-warning-200/50',
  red:    'bg-danger-100  text-danger-700  ring-danger-200/50',
  orange: 'bg-orange-100  text-orange-700  ring-orange-200/50',
  purple: 'bg-purple-100  text-purple-700  ring-purple-200/50',
  pink:   'bg-pink-100    text-pink-700    ring-pink-200/50',
};

const dotColors: Record<BadgeColor, string> = {
  gray:   'bg-neutral-500',
  blue:   'bg-primary-500',
  green:  'bg-success-500',
  yellow: 'bg-warning-500',
  red:    'bg-danger-500',
  orange: 'bg-orange-500',
  purple: 'bg-purple-500',
  pink:   'bg-pink-500',
};

const sizeStyles: Record<BadgeSize, string> = {
  sm: 'text-2xs px-2 py-0.5',
  md: 'text-xs  px-2.5 py-1',
  lg: 'text-sm  px-3 py-1.5',
};

// ─── Badge Component ──────────────────────────────────────────────────────────

export function Badge({
  color     = 'gray',
  size      = 'md',
  dot       = false,
  children,
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full font-medium ring-1',
        colorStyles[color],
        sizeStyles[size],
        className,
      )}
    >
      {dot && (
        <span
          className={cn('h-1.5 w-1.5 rounded-full shrink-0', dotColors[color])}
        />
      )}
      {children}
    </span>
  );
}

// ─── KYC Status Badge ─────────────────────────────────────────────────────────

const statusConfig: Record<KYCStatus, { color: BadgeColor; label: string }> = {
  PENDING:                { color: 'yellow', label: 'Pending'               },
  PROCESSING:             { color: 'blue',   label: 'Processing'            },
  APPROVED:               { color: 'green',  label: 'Approved'              },
  REJECTED:               { color: 'red',    label: 'Rejected'              },
  MANUAL_REVIEW:          { color: 'orange', label: 'Manual Review'         },
  RESUBMISSION_REQUIRED:  { color: 'purple', label: 'Resubmission Required' },
};

export function KYCStatusBadge({
  status,
  size = 'md',
}: {
  status: KYCStatus;
  size?: BadgeSize;
}) {
  const config = statusConfig[status] ?? { color: 'gray' as BadgeColor, label: status };
  return (
    <Badge color={config.color} size={size} dot>
      {config.label}
    </Badge>
  );
}
