import React, {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { jwtDecode } from 'jwt-decode';
import { authService } from '@/services/auth.service';
import { tokenStorage } from '@/services/api';
import type { User, LoginRequest, RegisterRequest, AuthTokens } from '@/types';

// ─── Types ────────────────────────────────────────────────────────────────────

interface AuthContextValue {
  user:            User | null;
  tokens:          AuthTokens | null;
  isAuthenticated: boolean;
  isLoading:       boolean;
  isAdmin:         boolean;
  login:           (creds: LoginRequest) => Promise<void>;
  register:        (payload: RegisterRequest) => Promise<void>;
  logout:          () => Promise<void>;
  refreshUser:     () => Promise<void>;
}

interface JWTPayload {
  sub:  string;
  exp:  number;
  role: string;
}

// ─── Context ──────────────────────────────────────────────────────────────────

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user,    setUser]    = useState<User | null>(null);
  const [tokens,  setTokens]  = useState<AuthTokens | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // ── Helpers ────────────────────────────────────────────────────────────────

  const isTokenExpired = (token: string): boolean => {
    try {
      const { exp } = jwtDecode<JWTPayload>(token);
      return Date.now() >= exp * 1000;
    } catch {
      return true;
    }
  };

  // ── Bootstrap: restore session on mount ────────────────────────────────────

  const refreshUser = useCallback(async () => {
    try {
      const profile = await authService.getProfile();
      setUser(profile);
    } catch {
      tokenStorage.clearTokens();
      setUser(null);
      setTokens(null);
    }
  }, []);

  useEffect(() => {
    const bootstrap = async () => {
      setIsLoading(true);
      const accessToken = tokenStorage.getAccess();

      if (!accessToken) {
        setIsLoading(false);
        return;
      }

      if (isTokenExpired(accessToken)) {
        const refreshToken = tokenStorage.getRefresh();
        if (!refreshToken || isTokenExpired(refreshToken)) {
          tokenStorage.clearTokens();
          setIsLoading(false);
          return;
        }
        try {
          const newTokens = await authService.refreshToken();
          setTokens(newTokens);
        } catch {
          tokenStorage.clearTokens();
          setIsLoading(false);
          return;
        }
      }

      await refreshUser();
      setIsLoading(false);
    };

    bootstrap();
  }, [refreshUser]);

  // ── Actions ────────────────────────────────────────────────────────────────

  const login = useCallback(async (creds: LoginRequest) => {
    const { user: u, tokens: t } = await authService.login(creds);
    setUser(u);
    setTokens(t);
  }, []);

  const register = useCallback(async (payload: RegisterRequest) => {
    const { user: u, tokens: t } = await authService.register(payload);
    setUser(u);
    setTokens(t);
  }, []);

  const logout = useCallback(async () => {
    await authService.logout();
    setUser(null);
    setTokens(null);
  }, []);

  // ── Derived values ─────────────────────────────────────────────────────────

  const isAuthenticated = !!user;
  const isAdmin         = user?.role === 'admin' || user?.role === 'reviewer' || user?.role === 'analyst';

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      tokens,
      isAuthenticated,
      isLoading,
      isAdmin,
      login,
      register,
      logout,
      refreshUser,
    }),
    [user, tokens, isAuthenticated, isLoading, isAdmin, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
