import React, { useState } from 'react';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { cn } from '@/utils/cn';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Column<T> {
  key:        string;
  header:     React.ReactNode;
  accessor:   (row: T) => React.ReactNode;
  sortable?:  boolean;
  className?: string;
  headerClassName?: string;
  width?:     string;
}

export interface TableProps<T> {
  columns:      Column<T>[];
  data:         T[];
  keyExtractor: (row: T, index: number) => string;
  onSort?:      (key: string, direction: 'asc' | 'desc') => void;
  sortKey?:     string;
  sortDir?:     'asc' | 'desc';
  isLoading?:   boolean;
  emptyMessage?: string;
  className?:   string;
  stickyHeader?: boolean;
  onRowClick?:  (row: T) => void;
}

// ─── Table ────────────────────────────────────────────────────────────────────

export function Table<T>({
  columns,
  data,
  keyExtractor,
  onSort,
  sortKey,
  sortDir,
  isLoading    = false,
  emptyMessage = 'No data available',
  className,
  stickyHeader = false,
  onRowClick,
}: TableProps<T>) {
  const [localSortKey, setLocalSortKey] = useState<string | null>(null);
  const [localSortDir, setLocalSortDir] = useState<'asc' | 'desc'>('asc');

  const activeSortKey = sortKey ?? localSortKey;
  const activeSortDir = sortKey ? (sortDir ?? 'asc') : localSortDir;

  const handleSort = (key: string) => {
    const newDir: 'asc' | 'desc' =
      activeSortKey === key && activeSortDir === 'asc' ? 'desc' : 'asc';
    setLocalSortKey(key);
    setLocalSortDir(newDir);
    onSort?.(key, newDir);
  };

  return (
    <div className={cn('overflow-x-auto rounded-xl border border-neutral-200', className)}>
      <table className="min-w-full divide-y divide-neutral-200">
        {/* Head */}
        <thead className={cn('bg-neutral-50', stickyHeader && 'sticky top-0 z-10')}>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                style={{ width: col.width }}
                className={cn(
                  'px-4 py-3 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider whitespace-nowrap',
                  col.sortable && 'cursor-pointer select-none hover:text-neutral-700',
                  col.headerClassName,
                )}
                onClick={() => col.sortable && handleSort(col.key)}
              >
                <span className="inline-flex items-center gap-1">
                  {col.header}
                  {col.sortable && (
                    <span className="text-neutral-400">
                      {activeSortKey === col.key ? (
                        activeSortDir === 'asc' ? (
                          <ChevronUp className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5" />
                        )
                      ) : (
                        <ChevronsUpDown className="h-3.5 w-3.5" />
                      )}
                    </span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>

        {/* Body */}
        <tbody className="bg-white divide-y divide-neutral-100">
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td key={col.key} className="px-4 py-3">
                    <div className="h-4 bg-neutral-100 rounded animate-pulse" />
                  </td>
                ))}
              </tr>
            ))
          ) : data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-12 text-center text-sm text-neutral-500"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, index) => (
              <tr
                key={keyExtractor(row, index)}
                onClick={() => onRowClick?.(row)}
                className={cn(
                  'transition-colors',
                  onRowClick && 'cursor-pointer hover:bg-neutral-50',
                )}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn(
                      'px-4 py-3 text-sm text-neutral-700 whitespace-nowrap',
                      col.className,
                    )}
                  >
                    {col.accessor(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
