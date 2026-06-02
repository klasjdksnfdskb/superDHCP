/**
 * superDHCP API 服务层
 * Axios 封装 + 自动 Token 管理 + 拦截器
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// ─── Token 管理 ───

function getAccessToken(): string | null {
  return localStorage.getItem('access_token');
}

function getRefreshToken(): string | null {
  return localStorage.getItem('refresh_token');
}

function setTokens(access: string, refresh: string) {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
}

function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
}

// ─── 请求拦截器 ───

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ─── 响应拦截器 (自动刷新 Token) ───

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve(token!);
  });
  failedQueue = [];
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(api(originalRequest));
            },
            reject,
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        clearTokens();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post(`${API_BASE}/auth/refresh`, {
          refresh_token: refreshToken,
        });
        setTokens(data.access_token, data.refresh_token);
        processQueue(null, data.access_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        clearTokens();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// ─── 认证 ───

export const authAPI = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  refresh: (refreshToken: string) =>
    api.post('/auth/refresh', { refresh_token: refreshToken }),
  me: () => api.get('/auth/me'),
  changePassword: (old_password: string, new_password: string) =>
    api.post('/auth/change-password', { old_password, new_password }),
};

// ─── Dashboard ───

export const dashboardAPI = {
  stats: () => api.get('/dashboard/stats'),
  activity: () => api.get('/dashboard/activity'),
};

// ─── 地址池 ───

export const poolsAPI = {
  list: () => api.get('/pools'),
  get: (id: string) => api.get(`/pools/${id}`),
  create: (data: Record<string, unknown>) => api.post('/pools', data),
  update: (id: string, data: Record<string, unknown>) => api.put(`/pools/${id}`, data),
  delete: (id: string) => api.delete(`/pools/${id}`),
  addSubnet: (poolId: string, data: Record<string, unknown>) =>
    api.post(`/pools/${poolId}/subnets`, data),
  deleteSubnet: (poolId: string, subnetId: string) =>
    api.delete(`/pools/${poolId}/subnets/${subnetId}`),
  addExclude: (subnetId: string, data: Record<string, unknown>) =>
    api.post(`/pools/subnets/${subnetId}/excludes`, data),
  deleteExclude: (excludeId: string) => api.delete(`/pools/excludes/${excludeId}`),
  addReservation: (poolId: string, data: Record<string, unknown>) =>
    api.post(`/pools/${poolId}/reservations`, data),
  deleteReservation: (reservationId: string) =>
    api.delete(`/pools/reservations/${reservationId}`),
};

// ─── 租约 ───

export const leasesAPI = {
  list: (params: Record<string, string | number | undefined>) =>
    api.get('/leases', { params }),
  get: (mac: string) => api.get(`/leases/${mac}`),
  release: (mac: string) => api.post(`/leases/${mac}/release`),
  exportCsv: (params: Record<string, string | undefined>) =>
    api.get('/leases/export', {
      params,
      responseType: 'blob',
    }),
};

// ─── 标签 ───

export const tagsAPI = {
  list: (params?: Record<string, unknown>) => api.get('/tags', { params }),
  tree: () => api.get('/tags/tree'),
  create: (data: Record<string, unknown>) => api.post('/tags', data),
  update: (id: string, data: Record<string, unknown>) => api.put(`/tags/${id}`, data),
  delete: (id: string) => api.delete(`/tags/${id}`),
  categories: () => api.get('/tags/categories'),
  createCategory: (data: Record<string, unknown>) => api.post('/tags/categories', data),
};

// ─── 用户管理 ───

export const usersAPI = {
  list: () => api.get('/users'),
  get: (id: string) => api.get(`/users/${id}`),
  create: (data: Record<string, unknown>) => api.post('/users', data),
  update: (id: string, data: Record<string, unknown>) => api.put(`/users/${id}`, data),
  delete: (id: string) => api.delete(`/users/${id}`),
  resetPassword: (id: string, new_password: string, force_change: boolean = true) =>
    api.put(`/users/${id}/password`, { new_password, force_change }),
};

export { setTokens, clearTokens, getAccessToken };
export default api;