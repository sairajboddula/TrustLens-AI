import { useState } from 'react';
import { Eye, MoreVertical, Filter, Search, X, Play } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Table } from '@/components/ui/Table';
import { Pagination } from '@/components/ui/Pagination';
import { KYCStatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input, Select } from '@/components/ui/Input';
import { formatDate, formatScore } from '@/utils/format';
import { useAdminSubmissions } from '@/hooks/useKYC';
import type { KYCSubmission, KYCStatus, SubmissionFilter } from '@/types';

interface SubmissionTableProps {
  onOverride: (submission: KYCSubmission) => void;
}

const STATUS_OPTIONS: { value: KYCStatus | ''; label: string }[] = [
  { value: '',               label: 'All Statuses'         },
  { value: 'PENDING',        label: 'Pending'              },
  { value: 'PROCESSING',     label: 'Processing'           },
  { value: 'APPROVED',       label: 'Approved'             },
  { value: 'REJECTED',       label: 'Rejected'             },
  { value: 'MANUAL_REVIEW',  label: 'Manual Review'        },
];

export function SubmissionTable({ onOverride }: SubmissionTableProps) {
  const navigate = useNavigate();

  const [filters, setFilters] = useState<SubmissionFilter>({
    page:      1,
    limit:     15,
    sort_by:   'created_at',
    sort_order:'desc',
  });
  const [search,     setSearch]     = useState('');
  const [showFilter, setShowFilter] = useState(false);

  const { data, isLoading } = useAdminSubmissions(filters);

  const applySearch = () => {
    setFilters((f) => ({ ...f, search: search || undefined, page: 1 }));
  };

  const clearFilters = () => {
    setSearch('');
    setFilters({ page: 1, limit: 15, sort_by: 'created_at', sort_order: 'desc' });
  };

  const columns = [
    {
      key:      'id',
      header:   'ID',
      accessor: (row: KYCSubmission) => (
        <span className="font-mono text-xs text-neutral-500">{row.id.slice(0, 8)}…</span>
      ),
    },
    {
      key:      'name',
      header:   'Applicant',
      accessor: (row: KYCSubmission) => (
        <div>
          <p className="font-medium text-neutral-900">
            {row.personal_info?.first_name} {row.personal_info?.last_name}
          </p>
          <p className="text-xs text-neutral-400">{row.user?.email ?? '—'}</p>
        </div>
      ),
    },
    {
      key:      'status',
      header:   'Status',
      sortable: true,
      accessor: (row: KYCSubmission) => <KYCStatusBadge status={row.status} />,
    },
    {
      key:      'confidence_score',
      header:   'Score',
      sortable: true,
      accessor: (row: KYCSubmission) =>
        row.confidence_score != null ? (
          <div className="flex items-center gap-2">
            <div className="w-16 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
              <div
                className={
                  row.confidence_score >= 0.8
                    ? 'h-full bg-success-500 rounded-full'
                    : row.confidence_score >= 0.6
                    ? 'h-full bg-warning-500 rounded-full'
                    : 'h-full bg-danger-500 rounded-full'
                }
                style={{ width: `${row.confidence_score * 100}%` }}
              />
            </div>
            <span className="text-xs font-medium">
              {Math.round(row.confidence_score * 100)}%
            </span>
          </div>
        ) : (
          <span className="text-neutral-400">—</span>
        ),
    },
    {
      key:      'doc_type',
      header:   'Document',
      accessor: (row: KYCSubmission) => (
        <span className="text-xs text-neutral-600">
          {row.identity_document?.document_type?.replace(/_/g, ' ') ?? '—'}
        </span>
      ),
    },
    {
      key:      'created_at',
      header:   'Submitted',
      sortable: true,
      accessor: (row: KYCSubmission) => (
        <span className="text-xs text-neutral-500">{formatDate(row.created_at)}</span>
      ),
    },
    {
      key:      'override',
      header:   '',
      accessor: (row: KYCSubmission) => (
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => { e.stopPropagation(); navigate(`/admin/submissions/${row.id}/review`); }}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 transition-colors"
            title="Run ID & Verification"
          >
            <Play className="h-3 w-3" />
            Review
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); navigate(`/admin/submissions/${row.id}`); }}
            className="p-1.5 rounded-lg text-neutral-400 hover:text-primary-600 hover:bg-primary-50 transition-colors"
            title="View details"
          >
            <Eye className="h-4 w-4" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onOverride(row); }}
            className="p-1.5 rounded-lg text-neutral-400 hover:text-orange-600 hover:bg-orange-50 transition-colors"
            title="Override decision"
          >
            <MoreVertical className="h-4 w-4" />
          </button>
        </div>
      ),
      className: 'text-right',
    },
  ];

  const hasActiveFilters = !!filters.status || !!filters.search || !!filters.date_from;

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
        {/* Search */}
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <div className="flex-1">
            <Input
              placeholder="Search by name or email…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && applySearch()}
              leftElement={<Search className="h-4 w-4" />}
              rightElement={
                search ? (
                  <button onClick={() => { setSearch(''); setFilters((f) => ({ ...f, search: undefined })); }}>
                    <X className="h-4 w-4" />
                  </button>
                ) : undefined
              }
            />
          </div>
          <Button variant="outline" size="sm" onClick={applySearch}>
            Search
          </Button>
        </div>

        {/* Filter toggle */}
        <Button
          variant={showFilter ? 'primary' : 'outline'}
          size="sm"
          leftIcon={<Filter className="h-4 w-4" />}
          onClick={() => setShowFilter((v) => !v)}
        >
          Filters
          {hasActiveFilters && (
            <span className="ml-1 h-1.5 w-1.5 rounded-full bg-current inline-block" />
          )}
        </Button>

        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            Clear
          </Button>
        )}
      </div>

      {/* Filter panel */}
      {showFilter && (
        <div className="bg-neutral-50 rounded-xl border border-neutral-200 p-4 grid grid-cols-2 sm:grid-cols-4 gap-4 animate-fade-in">
          <Select
            label="Status"
            value={filters.status ?? ''}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                status: (e.target.value as KYCStatus) || undefined,
                page:   1,
              }))
            }
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </Select>
          <Input
            label="From Date"
            type="date"
            value={filters.date_from ?? ''}
            onChange={(e) =>
              setFilters((f) => ({ ...f, date_from: e.target.value || undefined, page: 1 }))
            }
          />
          <Input
            label="To Date"
            type="date"
            value={filters.date_to ?? ''}
            onChange={(e) =>
              setFilters((f) => ({ ...f, date_to: e.target.value || undefined, page: 1 }))
            }
          />
          <Select
            label="Sort By"
            value={filters.sort_by ?? 'created_at'}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                sort_by: e.target.value as SubmissionFilter['sort_by'],
                page:    1,
              }))
            }
          >
            <option value="created_at">Date Submitted</option>
            <option value="updated_at">Last Updated</option>
            <option value="confidence_score">Confidence Score</option>
          </Select>
        </div>
      )}

      {/* Table */}
      <Table
        columns={columns}
        data={data?.items ?? []}
        keyExtractor={(row) => row.id}
        isLoading={isLoading}
        emptyMessage="No submissions found matching your criteria."
        onSort={(key, dir) =>
          setFilters((f) => ({
            ...f,
            sort_by:    key as SubmissionFilter['sort_by'],
            sort_order: dir,
          }))
        }
        sortKey={filters.sort_by}
        sortDir={filters.sort_order}
        onRowClick={(row) => navigate(`/admin/submissions/${row.id}`)}
      />

      {/* Pagination */}
      {data && (
        <Pagination
          page={data.page}
          totalPages={data.pages}
          total={data.total}
          limit={data.size}
          onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))}
        />
      )}
    </div>
  );
}
