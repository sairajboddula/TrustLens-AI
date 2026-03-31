import api, { tokenStorage } from './api';
import type {
  AuthTokens,
  AuthResponse,
  LoginRequest,
  RegisterRequest,
  User,
} from '@/types';

const AUTH = '/auth';

export const authService = {
  /**
   * Authenticate user and store tokens.
   */
  async login(credentials: LoginRequest): Promise<{ user: User; tokens: AuthTokens }> {
    const { data } = await api.post<AuthResponse>(`${AUTH}/login`, credentials);
    const tokens: AuthTokens = {
      access_token:  data.access_token,
      refresh_token: data.refresh_token,
      token_type:    data.token_type,
      expires_in:    data.expires_in,
    };
    tokenStorage.setTokens(tokens.access_token, tokens.refresh_token);
    return { user: data.user, tokens };
  },

  /**
   * Register a new user account and auto-login.
   */
  async register(payload: RegisterRequest): Promise<{ user: User; tokens: AuthTokens }> {
    const { data } = await api.post<AuthResponse>(`${AUTH}/register`, payload);
    const tokens: AuthTokens = {
      access_token:  data.access_token,
      refresh_token: data.refresh_token,
      token_type:    data.token_type,
      expires_in:    data.expires_in,
    };
    tokenStorage.setTokens(tokens.access_token, tokens.refresh_token);
    return { user: data.user, tokens };
  },

  /**
   * Invalidate server session and clear local tokens.
   * Always clears local tokens even if the server call fails.
   */
  async logout(): Promise<void> {
    try {
      await api.post(`${AUTH}/logout`);
    } catch {
      // Ignore server errors — user is logged out locally regardless
    } finally {
      tokenStorage.clearTokens();
    }
  },

  /**
   * Request a new access token using the stored refresh token.
   */
  async refreshToken(): Promise<AuthTokens> {
    const refreshToken = tokenStorage.getRefresh();
    const { data } = await api.post<{ access_token: string; refresh_token?: string; token_type: string; expires_in?: number }>(
      `${AUTH}/refresh`,
      { refresh_token: refreshToken },
    );
    const tokens: AuthTokens = {
      access_token:  data.access_token,
      refresh_token: data.refresh_token ?? refreshToken ?? '',
      token_type:    data.token_type,
      expires_in:    data.expires_in ?? 1800,
    };
    tokenStorage.setTokens(tokens.access_token, tokens.refresh_token);
    return tokens;
  },

  /**
   * Fetch the authenticated user's profile.
   */
  async getProfile(): Promise<User> {
    const { data } = await api.get<User>(`${AUTH}/me`);
    return data;
  },

  /**
   * Change the current user's password.
   */
  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await api.post(`${AUTH}/change-password`, {
      current_password:     currentPassword,
      new_password:         newPassword,
      confirm_new_password: newPassword,
    });
  },

  /**
   * Request a password-reset email.
   */
  async requestPasswordReset(email: string): Promise<void> {
    await api.post(`${AUTH}/forgot-password`, { email });
  },

  /**
   * Complete the password reset flow.
   */
  async resetPassword(token: string, newPassword: string): Promise<void> {
    await api.post(`${AUTH}/reset-password`, {
      token,
      new_password: newPassword,
    });
  },

  /**
   * Returns true if a valid access token is stored.
   */
  isAuthenticated(): boolean {
    return !!tokenStorage.getAccess();
  },
};
