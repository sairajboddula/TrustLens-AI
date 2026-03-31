import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import {
  Shield,
  Menu,
  X,
  ChevronDown,
  User,
  LogOut,
  Settings,
  LayoutDashboard,
  FileText,
  Bell,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { useAuth } from '@/hooks/useAuth';
import { getInitials } from '@/utils/format';

interface NavLink {
  to:    string;
  label: string;
  icon?: React.ReactNode;
}

const userLinks: NavLink[] = [
  { to: '/dashboard',   label: 'Dashboard',   icon: <LayoutDashboard className="h-4 w-4" /> },
  { to: '/kyc/submit',  label: 'Submit KYC',  icon: <FileText        className="h-4 w-4" /> },
  { to: '/kyc/status',  label: 'KYC Status',  icon: <Shield          className="h-4 w-4" /> },
];

const adminLinks: NavLink[] = [
  { to: '/admin/dashboard',   label: 'Admin Dashboard', icon: <LayoutDashboard className="h-4 w-4" /> },
  { to: '/admin/submissions', label: 'Submissions',     icon: <FileText        className="h-4 w-4" /> },
  { to: '/admin/users',       label: 'Users',           icon: <User            className="h-4 w-4" /> },
];

export function Navbar() {
  const { user, isAdmin, logout } = useAuth();
  const navigate  = useNavigate();
  const location  = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const links = isAdmin ? adminLinks : userLinks;

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const isActive = (to: string) => location.pathname === to || location.pathname.startsWith(to + '/');

  return (
    <nav className="fixed top-0 inset-x-0 z-40 bg-white border-b border-neutral-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to={isAdmin ? '/admin/dashboard' : '/dashboard'} className="flex items-center gap-2.5 shrink-0">
            <div className="flex items-center justify-center h-8 w-8 rounded-lg bg-primary-600">
              <Shield className="h-4.5 w-4.5 text-white" strokeWidth={2.5} />
            </div>
            <span className="text-lg font-bold text-neutral-900 tracking-tight">
              {import.meta.env.VITE_APP_NAME ?? 'KYC Platform'}
            </span>
          </Link>

          {/* Desktop nav links */}
          <div className="hidden md:flex items-center gap-1">
            {links.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={cn(
                  'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isActive(link.to)
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900',
                )}
              >
                {link.icon}
                {link.label}
              </Link>
            ))}
          </div>

          {/* Right section */}
          <div className="flex items-center gap-2">
            {/* Notification bell (placeholder) */}
            <button className="hidden sm:flex h-8 w-8 items-center justify-center rounded-lg text-neutral-500 hover:bg-neutral-100 transition-colors relative">
              <Bell className="h-4.5 w-4.5" />
              <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-primary-500" />
            </button>

            {/* User dropdown */}
            <div ref={dropdownRef} className="relative">
              <button
                onClick={() => setDropdownOpen((v) => !v)}
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-neutral-100 transition-colors"
              >
                <div className="flex items-center justify-center h-7 w-7 rounded-full bg-primary-600 text-white text-xs font-semibold shrink-0">
                  {user ? getInitials(user.full_name) : '?'}
                </div>
                <span className="hidden sm:block text-sm font-medium text-neutral-700 max-w-[120px] truncate">
                  {user?.full_name ?? 'User'}
                </span>
                <ChevronDown
                  className={cn(
                    'hidden sm:block h-3.5 w-3.5 text-neutral-400 transition-transform duration-150',
                    dropdownOpen && 'rotate-180',
                  )}
                />
              </button>

              {/* Dropdown panel */}
              {dropdownOpen && (
                <div className="absolute right-0 mt-1.5 w-56 bg-white border border-neutral-200 rounded-xl shadow-modal py-1.5 z-50 animate-fade-in">
                  <div className="px-4 py-2.5 border-b border-neutral-100">
                    <p className="text-sm font-semibold text-neutral-900 truncate">{user?.full_name}</p>
                    <p className="text-xs text-neutral-500 truncate">{user?.email}</p>
                    {isAdmin && (
                      <span className="mt-1 inline-block text-2xs font-medium bg-primary-100 text-primary-700 px-2 py-0.5 rounded-full uppercase tracking-wide">
                        Admin
                      </span>
                    )}
                  </div>
                  <div className="py-1">
                    <DropdownItem
                      icon={<User className="h-4 w-4" />}
                      label="Profile"
                      onClick={() => { setDropdownOpen(false); navigate('/profile'); }}
                    />
                    <DropdownItem
                      icon={<Settings className="h-4 w-4" />}
                      label="Settings"
                      onClick={() => { setDropdownOpen(false); navigate('/settings'); }}
                    />
                  </div>
                  <div className="border-t border-neutral-100 pt-1">
                    <DropdownItem
                      icon={<LogOut className="h-4 w-4" />}
                      label="Sign out"
                      onClick={handleLogout}
                      danger
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Mobile hamburger */}
            <button
              onClick={() => setMobileOpen((v) => !v)}
              className="md:hidden h-8 w-8 flex items-center justify-center rounded-lg text-neutral-600 hover:bg-neutral-100 transition-colors"
              aria-label="Toggle menu"
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden border-t border-neutral-200 bg-white animate-slide-down">
          <div className="px-4 py-3 space-y-1">
            {links.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  isActive(link.to)
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-neutral-600 hover:bg-neutral-100',
                )}
              >
                {link.icon}
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}

// ─── Dropdown Item ────────────────────────────────────────────────────────────

function DropdownItem({
  icon,
  label,
  onClick,
  danger = false,
}: {
  icon:    React.ReactNode;
  label:   string;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors',
        danger
          ? 'text-danger-600 hover:bg-danger-50'
          : 'text-neutral-700 hover:bg-neutral-50',
      )}
    >
      {icon}
      {label}
    </button>
  );
}
