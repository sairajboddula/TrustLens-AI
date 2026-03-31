import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  FileText,
  Users,
  Shield,
  BarChart3,
  Settings,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/utils/cn';

// ─── Types ────────────────────────────────────────────────────────────────────

interface NavItem {
  to:      string;
  label:   string;
  icon:    React.ReactNode;
  badge?:  string | number;
  exact?:  boolean;
}

interface NavGroup {
  heading: string;
  items:   NavItem[];
}

// ─── Nav Config ───────────────────────────────────────────────────────────────

const adminNavGroups: NavGroup[] = [
  {
    heading: 'Overview',
    items: [
      {
        to:    '/admin/dashboard',
        label: 'Dashboard',
        icon:  <LayoutDashboard className="h-4.5 w-4.5" />,
        exact: true,
      },
      {
        to:    '/admin/submissions',
        label: 'Submissions',
        icon:  <FileText className="h-4.5 w-4.5" />,
      },
      {
        to:    '/admin/users',
        label: 'Users',
        icon:  <Users className="h-4.5 w-4.5" />,
      },
    ],
  },
  {
    heading: 'Analytics',
    items: [
      {
        to:    '/admin/analytics',
        label: 'Analytics',
        icon:  <BarChart3 className="h-4.5 w-4.5" />,
      },
    ],
  },
  {
    heading: 'System',
    items: [
      {
        to:    '/admin/settings',
        label: 'Settings',
        icon:  <Settings className="h-4.5 w-4.5" />,
      },
    ],
  },
];

// ─── Sidebar Component ────────────────────────────────────────────────────────

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const location = useLocation();

  const isActive = (item: NavItem) =>
    item.exact
      ? location.pathname === item.to
      : location.pathname === item.to || location.pathname.startsWith(item.to + '/');

  return (
    <aside
      className={cn(
        'flex flex-col w-64 bg-white border-r border-neutral-200 min-h-screen',
        className,
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 h-16 px-6 border-b border-neutral-200 shrink-0">
        <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-primary-600">
          <Shield className="h-4 w-4 text-white" strokeWidth={2.5} />
        </div>
        <span className="text-base font-bold text-neutral-900">Admin Panel</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        {adminNavGroups.map((group) => (
          <div key={group.heading}>
            <p className="px-3 mb-1 text-2xs font-semibold text-neutral-400 uppercase tracking-widest">
              {group.heading}
            </p>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const active = isActive(item);
                return (
                  <li key={item.to}>
                    <Link
                      to={item.to}
                      className={cn(
                        'group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150',
                        active
                          ? 'bg-primary-50 text-primary-700'
                          : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900',
                      )}
                    >
                      <span
                        className={cn(
                          'shrink-0 transition-colors',
                          active
                            ? 'text-primary-600'
                            : 'text-neutral-400 group-hover:text-neutral-600',
                        )}
                      >
                        {item.icon}
                      </span>
                      <span className="flex-1">{item.label}</span>
                      {item.badge != null && (
                        <span
                          className={cn(
                            'text-xs font-medium px-1.5 py-0.5 rounded-full',
                            active
                              ? 'bg-primary-100 text-primary-700'
                              : 'bg-neutral-100 text-neutral-500',
                          )}
                        >
                          {item.badge}
                        </span>
                      )}
                      {active && (
                        <ChevronRight className="h-3.5 w-3.5 text-primary-500 shrink-0" />
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="shrink-0 px-4 py-4 border-t border-neutral-100">
        <p className="text-2xs text-neutral-400 text-center">
          KYC Platform v1.0.0
        </p>
      </div>
    </aside>
  );
}
