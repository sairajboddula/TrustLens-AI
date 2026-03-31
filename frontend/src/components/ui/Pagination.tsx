import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { cn } from '@/utils/cn';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface PaginationProps {
  page:        number;
  totalPages:  number;
  total:       number;
  limit:       number;
  onPageChange: (page: number) => void;
  className?:  string;
  showInfo?:   boolean;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getPageNumbers(current: number, total: number): (number | '...')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);

  const pages: (number | '...')[] = [1];

  if (current > 3)          pages.push('...');

  const start = Math.max(2, current - 1);
  const end   = Math.min(total - 1, current + 1);
  for (let i = start; i <= end; i++) pages.push(i);

  if (current < total - 2) pages.push('...');
  pages.push(total);

  return pages;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function Pagination({
  page,
  totalPages,
  total,
  limit,
  onPageChange,
  className,
  showInfo = true,
}: PaginationProps) {
  const pageNumbers = getPageNumbers(page, totalPages);
  const from        = (page - 1) * limit + 1;
  const to          = Math.min(page * limit, total);

  if (totalPages <= 1 && !showInfo) return null;

  return (
    <div
      className={cn(
        'flex flex-col sm:flex-row items-center justify-between gap-4 py-3',
        className,
      )}
    >
      {/* Info */}
      {showInfo && (
        <p className="text-sm text-neutral-500 order-2 sm:order-1">
          Showing{' '}
          <span className="font-medium text-neutral-700">{from}</span>
          –
          <span className="font-medium text-neutral-700">{to}</span>
          {' '}of{' '}
          <span className="font-medium text-neutral-700">{total}</span>
          {' '}results
        </p>
      )}

      {/* Controls */}
      {totalPages > 1 && (
        <div className="flex items-center gap-1 order-1 sm:order-2">
          {/* First */}
          <PageButton
            onClick={() => onPageChange(1)}
            disabled={page === 1}
            aria-label="First page"
          >
            <ChevronsLeft className="h-3.5 w-3.5" />
          </PageButton>

          {/* Prev */}
          <PageButton
            onClick={() => onPageChange(page - 1)}
            disabled={page === 1}
            aria-label="Previous page"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </PageButton>

          {/* Page numbers */}
          {pageNumbers.map((p, i) =>
            p === '...' ? (
              <span key={`ellipsis-${i}`} className="px-2 text-neutral-400 text-sm select-none">
                …
              </span>
            ) : (
              <PageButton
                key={p}
                onClick={() => onPageChange(p as number)}
                active={p === page}
                aria-label={`Page ${p}`}
                aria-current={p === page ? 'page' : undefined}
              >
                {p}
              </PageButton>
            ),
          )}

          {/* Next */}
          <PageButton
            onClick={() => onPageChange(page + 1)}
            disabled={page === totalPages}
            aria-label="Next page"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </PageButton>

          {/* Last */}
          <PageButton
            onClick={() => onPageChange(totalPages)}
            disabled={page === totalPages}
            aria-label="Last page"
          >
            <ChevronsRight className="h-3.5 w-3.5" />
          </PageButton>
        </div>
      )}
    </div>
  );
}

// ─── Page Button ──────────────────────────────────────────────────────────────

interface PageButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

function PageButton({ active = false, className, children, ...props }: PageButtonProps) {
  return (
    <button
      className={cn(
        'min-w-[32px] h-8 px-2 rounded-lg text-sm font-medium transition-colors',
        'focus:outline-none focus:ring-2 focus:ring-primary-400 focus:ring-offset-1',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        active
          ? 'bg-primary-600 text-white shadow-sm'
          : 'text-neutral-600 hover:bg-neutral-100',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
