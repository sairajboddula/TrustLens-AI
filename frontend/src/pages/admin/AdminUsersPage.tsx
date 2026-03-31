import { useState } from 'react';
import { Search, MoreVertical, User, Shield, CheckCircle2, XCircle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import api from '@/services/api';
import { Table } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Pagination } from '@/components/ui/Pagination';
import { formatDate, formatRelativeTime, getInitials } from '@/utils/format';
import type { User as UserType, PaginatedResponse } from '@/types';

// ─── Fetch users ──────────────────────────────────────────────────────────────

async function fetchUsers(page: number, limit: number, search?: string) {
  const { data } = await api.get<PaginatedResponse<UserType>>(
    '/admin/users',
    { params: { page, size: limit, search } },
  );
  return data;
}

// ─── Role badge ───────────────────────────────────────────────────────────────

function RoleBadge({ role }: { role: UserType['role'] }) {
  const config: Record<string, { color: 'blue' | 'purple' | 'red' | 'green' | 'yellow'; label: string }> = {
    customer: { color: 'blue',   label: 'Customer'  },
    admin:    { color: 'purple', label: 'Admin'     },
    reviewer: { color: 'green',  label: 'Reviewer'  },
    analyst:  { color: 'yellow', label: 'Analyst'   },
  };
  const { color, label } = config[role] ?? { color: 'blue' as const, label: role };

  return (
    <Badge color={color} size="sm">
      {label}
    </Badge>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function AdminUsersPage() {
  const [page,   setPage]   = useState(1);
  const [search, setSearch] = useState('');
  const [query,  setQuery]  = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['admin', 'users', page, query],
    queryFn:  () => fetchUsers(page, 15, query || undefined),
    staleTime: 30_000,
  });

  const columns = [
    {
      key:      'user',
      header:   'User',
      accessor: (row: UserType) => (
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-full bg-primary-600 flex items-center justify-center text-white text-xs font-semibold shrink-0">
            {getInitials(row.full_name)}
          </div>
          <div>
            <p className="text-sm font-medium text-neutral-900">{row.full_name}</p>
            <p className="text-xs text-neutral-400">{row.email}</p>
          </div>
        </div>
      ),
    },
    {
      key:      'role',
      header:   'Role',
      accessor: (row: UserType) => <RoleBadge role={row.role} />,
    },
    {
      key:      'status',
      header:   'Status',
      accessor: (row: UserType) => (
        <div className="flex items-center gap-1.5">
          {row.status === 'active' ? (
            <>
              <CheckCircle2 className="h-3.5 w-3.5 text-success-500" />
              <span className="text-xs text-success-600 font-medium">Active</span>
            </>
          ) : (
            <>
              <XCircle className="h-3.5 w-3.5 text-neutral-400" />
              <span className="text-xs text-neutral-400 capitalize">{row.status}</span>
            </>
          )}
        </div>
      ),
    },
    {
      key:      'verified',
      header:   'Verified',
      accessor: (row: UserType) => (
        <span
          className={`text-xs font-medium ${row.is_email_verified ? 'text-success-600' : 'text-neutral-400'}`}
        >
          {row.is_email_verified ? 'Verified' : 'Unverified'}
        </span>
      ),
    },
    {
      key:      'created_at',
      header:   'Joined',
      sortable: true,
      accessor: (row: UserType) => (
        <span className="text-xs text-neutral-500">{formatRelativeTime(row.created_at)}</span>
      ),
    },
    {
      key:      'actions',
      header:   '',
      accessor: (row: UserType) => (
        <button
          className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-600 hover:bg-neutral-100 transition-colors"
          title="User actions"
        >
          <MoreVertical className="h-4 w-4" />
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Users</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Manage user accounts and permissions.
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-neutral-500 bg-neutral-100 px-3 py-1.5 rounded-lg">
          <User className="h-4 w-4" />
          <span>{data?.total ?? 0} total users</span>
        </div>
      </div>

      {/* Search */}
      <div className="flex items-center gap-3">
        <div className="flex-1 max-w-sm">
          <Input
            placeholder="Search users…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && setQuery(search)}
            leftElement={<Search className="h-4 w-4" />}
          />
        </div>
        <button
          onClick={() => setQuery(search)}
          className="px-4 py-2.5 text-sm font-medium bg-white border border-neutral-300 rounded-lg hover:bg-neutral-50 transition-colors"
        >
          Search
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-neutral-200 shadow-card">
        <Table
          columns={columns}
          data={data?.items ?? []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          emptyMessage="No users found."
        />
        {data && (
          <div className="px-4 pb-4">
            <Pagination
              page={data.page}
              totalPages={data.pages}
              total={data.total}
              limit={data.size}
              onPageChange={setPage}
            />
          </div>
        )}
      </div>
    </div>
  );
}
