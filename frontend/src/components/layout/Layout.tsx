import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';
import { cn } from '@/utils/cn';

interface LayoutProps {
  className?: string;
}

export function Layout({ className }: LayoutProps) {
  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col">
      <Navbar />

      {/* Page content, offset by navbar height (h-16 = 4rem) */}
      <main className={cn('flex-1 pt-16', className)}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Outlet />
        </div>
      </main>

      <footer className="bg-white border-t border-neutral-200 py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-center text-xs text-neutral-400">
            &copy; {new Date().getFullYear()} KYC Platform. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
