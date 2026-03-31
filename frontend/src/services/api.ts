import axios, {
  AxiosInstance,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';
import toast from 'react-hot-toast';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';

// ─── Token Helpers ───────────────────────────────────────────────────────────

const TOKEN_KEY   = 'kyc_access_token';
const REFRESH_KEY = 'kyc_refresh_token';

export const tokenStorage = {
  getAccess:       () => localStorage.getItem(TOKEN_KEY),
  getRefresh:      () => localStorage.getItem(REFRESH_KEY),
  setAccess:       (t: string) => localStorage.setItem(TOKEN_KEY, t),
  setRefresh:      (t: string) => localStorage.setItem(REFRESH_KEY, t),
  setTokens:       (access: string, refresh: string) => {
    localStorage.setItem(TOKEN_KEY,   access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clearTokens:     () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

// ─── Axios Instance ───────────────────────────────────────────────────────────

const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
});

// ─── Request Interceptor ─────────────────────────────────────────────────────

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenStorage.getAccess();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// ─── Response Interceptor ─────────────────────────────────────────────────────

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: string) => void;
  reject:  (reason?: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach((p) => {
    if (error) p.reject(error);
    else       p.resolve(token!);
  });
  failedQueue = [];
}

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error) => {
    const originalRequest = error.config;

    // 401 → attempt token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = tokenStorage.getRefresh();

      if (!refreshToken) {
        tokenStorage.clearTokens();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });
        const newAccessToken = data.data?.access_token ?? data.access_token;
        tokenStorage.setAccess(newAccessToken);
        if (data.data?.refresh_token ?? data.refresh_token) {
          tokenStorage.setRefresh(data.data?.refresh_token ?? data.refresh_token);
        }
        api.defaults.headers.common.Authorization = `Bearer ${newAccessToken}`;
        processQueue(null, newAccessToken);
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        tokenStorage.clearTokens();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // 403 Forbidden (suppress for logout — user is already logging out)
    if (error.response?.status === 403 && !originalRequest.url?.includes('/auth/logout')) {
      toast.error('You do not have permission to perform this action.');
    }

    // 500 Server Error (suppress for logout)
    if (error.response?.status >= 500 && !originalRequest.url?.includes('/auth/logout')) {
      toast.error('A server error occurred. Please try again later.');
    }

    return Promise.reject(error);
  },
);

export default api;
