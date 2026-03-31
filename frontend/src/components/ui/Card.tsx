import React from 'react';
import { cn } from '@/utils/cn';

// ─── Card ─────────────────────────────────────────────────────────────────────

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export function Card({ hover = false, padding = 'md', className, children, ...props }: CardProps) {
  const paddingStyles = {
    none: '',
    sm:   'p-4',
    md:   'p-6',
    lg:   'p-8',
  };

  return (
    <div
      className={cn(
        'bg-white rounded-xl border border-neutral-200 shadow-card',
        hover && 'transition-shadow duration-200 hover:shadow-card-hover cursor-pointer',
        paddingStyles[padding],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

// ─── Card Header ──────────────────────────────────────────────────────────────

export interface CardHeaderProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  title?:    React.ReactNode;
  subtitle?: React.ReactNode;
  action?:   React.ReactNode;
}

export function CardHeader({ title, subtitle, action, className, children, ...props }: CardHeaderProps) {
  return (
    <div
      className={cn('flex items-start justify-between gap-4 mb-6', className)}
      {...props}
    >
      <div>
        {title && (
          <h3 className="text-base font-semibold text-neutral-900">{title}</h3>
        )}
        {subtitle && (
          <p className="mt-0.5 text-sm text-neutral-500">{subtitle}</p>
        )}
        {children}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

// ─── Card Body ────────────────────────────────────────────────────────────────

export function CardBody({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('', className)} {...props}>
      {children}
    </div>
  );
}

// ─── Card Footer ──────────────────────────────────────────────────────────────

export function CardFooter({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'mt-6 pt-6 border-t border-neutral-100 flex items-center justify-end gap-3',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

// ─── Stat Card ────────────────────────────────────────────────────────────────

export interface StatCardProps {
  title:      string;
  value:      React.ReactNode;
  subtitle?:  string;
  icon?:      React.ReactNode;
  trend?:     { value: number; label: string };
  color?:     'blue' | 'green' | 'yellow' | 'red' | 'purple' | 'orange';
  className?: string;
}

const colorMap = {
  blue:   { bg: 'bg-primary-50',  icon: 'bg-primary-100  text-primary-600',  text: 'text-primary-600' },
  green:  { bg: 'bg-success-50',  icon: 'bg-success-100  text-success-600',  text: 'text-success-600' },
  yellow: { bg: 'bg-warning-50',  icon: 'bg-warning-100  text-warning-600',  text: 'text-warning-600' },
  red:    { bg: 'bg-danger-50',   icon: 'bg-danger-100   text-danger-600',   text: 'text-danger-600'  },
  purple: { bg: 'bg-purple-50',   icon: 'bg-purple-100   text-purple-600',   text: 'text-purple-600'  },
  orange: { bg: 'bg-orange-50',   icon: 'bg-orange-100   text-orange-600',   text: 'text-orange-600'  },
};

export function StatCard({ title, value, subtitle, icon, trend, color = 'blue', className }: StatCardProps) {
  const colors = colorMap[color];

  return (
    <div className={cn('bg-white rounded-xl border border-neutral-200 shadow-card p-6', className)}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-neutral-500">{title}</p>
          <p className="mt-1 text-2xl font-bold text-neutral-900">{value}</p>
          {subtitle && <p className="mt-0.5 text-xs text-neutral-400">{subtitle}</p>}
          {trend && (
            <p
              className={cn(
                'mt-1 text-xs font-medium',
                trend.value >= 0 ? 'text-success-600' : 'text-danger-600',
              )}
            >
              {trend.value >= 0 ? '+' : ''}{trend.value}% {trend.label}
            </p>
          )}
        </div>
        {icon && (
          <div className={cn('rounded-xl p-3', colors.icon)}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
