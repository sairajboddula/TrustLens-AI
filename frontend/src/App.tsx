import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { LoadingScreen } from '@/components/ui/Spinner';
import { Layout }      from '@/components/layout/Layout';
import { AdminLayout } from '@/components/layout/AdminLayout';

// Auth pages
import { LoginPage }    from '@/pages/auth/LoginPage';
import { RegisterPage } from '@/pages/auth/RegisterPage';

// User pages
import { DashboardPage }      from '@/pages/user/DashboardPage';
import { KYCSubmitPage }      from '@/pages/user/KYCSubmitPage';
import { KYCStatusPage }      from '@/pages/user/KYCStatusPage';
import { KYCSubmissionsPage } from '@/pages/user/KYCSubmissionsPage';

// Admin pages
import { AdminDashboardPage }   from '@/pages/admin/AdminDashboardPage';
import { AdminSubmissionsPage } from '@/pages/admin/AdminSubmissionsPage';
import { AdminUsersPage }       from '@/pages/admin/AdminUsersPage';
import { AdminAnalyticsPage }   from '@/pages/admin/AdminAnalyticsPage';
import { AdminSettingsPage }    from '@/pages/admin/AdminSettingsPage';
import { AdminCaseDetailPage }  from '@/pages/admin/AdminCaseDetailPage';

// Shared pages
import { ProfilePage }  from '@/pages/shared/ProfilePage';
import { SettingsPage } from '@/pages/shared/SettingsPage';

// ─── Route Guards ─────────────────────────────────────────────────────────────

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) return <LoadingScreen message="Loading…" />;

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: window.location }} />;
  }

  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isAdmin, isLoading } = useAuth();

  if (isLoading) return <LoadingScreen message="Loading…" />;

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  if (!isAdmin) return <Navigate to="/dashboard" replace />;

  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isAdmin, isLoading } = useAuth();

  if (isLoading) return <LoadingScreen message="Loading…" />;

  if (isAuthenticated) {
    return <Navigate to={isAdmin ? '/admin/dashboard' : '/dashboard'} replace />;
  }

  return <>{children}</>;
}

// ─── App ──────────────────────────────────────────────────────────────────────

export default function App() {
  const { isAuthenticated, isAdmin, isLoading } = useAuth();

  if (isLoading) return <LoadingScreen />;

  return (
    <Routes>
      {/* Root redirect */}
      <Route
        path="/"
        element={
          isAuthenticated
            ? <Navigate to={isAdmin ? '/admin/dashboard' : '/dashboard'} replace />
            : <Navigate to="/login" replace />
        }
      />

      {/* Auth routes (redirect to dashboard if logged in) */}
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicRoute>
            <RegisterPage />
          </PublicRoute>
        }
      />

      {/* Protected user routes */}
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard"        element={<DashboardPage />}      />
        <Route path="/kyc/submit"       element={<KYCSubmitPage />}      />
        <Route path="/kyc/status"       element={<KYCStatusPage />}      />
        <Route path="/kyc/submissions"  element={<KYCSubmissionsPage />} />
        <Route path="/profile"          element={<ProfilePage />}        />
        <Route path="/settings"         element={<SettingsPage />}       />
      </Route>

      {/* Protected admin routes */}
      <Route
        element={
          <AdminRoute>
            <AdminLayout />
          </AdminRoute>
        }
      >
        <Route path="/admin/dashboard"                       element={<AdminDashboardPage />}             />
        <Route path="/admin/submissions"                     element={<AdminSubmissionsPage />}           />
        <Route path="/admin/submissions/:submissionId/review" element={<AdminCaseDetailPage />}          />
        <Route path="/admin/users"                           element={<AdminUsersPage />}                 />
        <Route path="/admin/analytics"                       element={<AdminAnalyticsPage />}             />
        <Route path="/admin/settings"                        element={<AdminSettingsPage />}              />
        <Route path="/profile"           element={<ProfilePage />}          />
        <Route path="/settings"          element={<SettingsPage />}         />
      </Route>

      {/* 404 */}
      <Route
        path="*"
        element={
          <div className="min-h-screen flex flex-col items-center justify-center bg-neutral-50 px-4">
            <p className="text-8xl font-bold text-neutral-200">404</p>
            <h1 className="mt-4 text-2xl font-bold text-neutral-800">Page not found</h1>
            <p className="mt-2 text-neutral-500 text-center max-w-sm">
              The page you're looking for doesn't exist or has been moved.
            </p>
            <a
              href="/"
              className="mt-6 px-5 py-2.5 bg-primary-600 text-white text-sm font-medium rounded-xl hover:bg-primary-700 transition-colors"
            >
              Go home
            </a>
          </div>
        }
      />
    </Routes>
  );
}
