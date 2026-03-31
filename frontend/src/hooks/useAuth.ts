import { useContext } from 'react';
import { AuthContext } from '@/contexts/AuthContext';

/**
 * Hook for consuming authentication state and actions.
 * Must be used inside <AuthProvider>.
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
