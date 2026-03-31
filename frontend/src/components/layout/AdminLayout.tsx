import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { Navbar } from './Navbar';
import { cn } from '@/utils/cn';

export function AdminLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col">
      {/* Top bar (mobile only shows hamburger) */}
      <Navbar />

      <div className="flex flex-1 pt-16">
        {/* Sidebar – desktop always visible, mobile overlay */}
        {/* Desktop sidebar */}
        <div className="hidden lg:flex shrink-0">
          <Sidebar />
        </div>

        {/* Mobile sidebar overlay */}
        {sidebarOpen && (
          <div className="lg:hidden fixed inset-0 z-50 flex">
            {/* Backdrop */}
            <div
              className="absolute inset-0 bg-black/40 backdrop-blur-sm"
              onClick={() => setSidebarOpen(false)}
            />
            {/* Drawer */}
            <div className="relative z-10 animate-slide-up">
              <Sidebar />
            </div>
            {/* Close button */}
            <button
              onClick={() => setSidebarOpen(false)}
              className="absolute top-4 right-4 z-20 p-2 rounded-lg bg-white text-neutral-600 shadow"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        )}

        {/* Main content */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Mobile sidebar toggle */}
          <div className="lg:hidden flex items-center px-4 py-3 border-b border-neutral-200 bg-white">
            <button
              onClick={() => setSidebarOpen(true)}
              className="flex items-center gap-2 text-sm text-neutral-600 font-medium"
            >
              <Menu className="h-5 w-5" />
              <span>Menu</span>
            </button>
          </div>

          <main className="flex-1 p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
