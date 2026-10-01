import axios from 'axios';

// Same-origin by default (/api is proxied by Vite in dev and nginx in prod).
// Auth lives in httpOnly cookies set by the backend, so no token ever
// touches JavaScript or localStorage.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

const NO_REFRESH = ['/auth/login/', '/auth/token/refresh/', '/auth/registration/', '/auth/google/'];

// Access tokens are short-lived (15 min). On a 401, refresh once using the
// refresh cookie and replay the request; concurrent 401s share one refresh.
let refreshing = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error;
    const url = config?.url || '';
    if (response?.status !== 401 || config._retried || NO_REFRESH.some((p) => url.includes(p))) {
      return Promise.reject(error);
    }
    config._retried = true;
    try {
      refreshing = refreshing || api.post('/auth/token/refresh/', {});
      await refreshing;
      return api(config);
    } catch (refreshError) {
      if (!url.includes('/auth/user/') && window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
      return Promise.reject(refreshError);
    } finally {
      refreshing = null;
    }
  }
);

export function errorMessage(err, fallback = 'Something went wrong.') {
  const data = err?.response?.data;
  if (!data) return err?.response ? fallback : 'Network error: cannot reach the server.';
  if (typeof data === 'string') return fallback;
  if (data.detail) return data.detail;
  const messages = Object.values(data).flat().filter((m) => typeof m === 'string');
  return messages.join(' ') || fallback;
}

export default api;
