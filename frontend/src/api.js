import axios from 'axios';

const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL}/api`, // Adjust if running in Docker vs Localhost
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Check if the error is 401 and we are not already on the login page
    if (error.response && error.response.status === 401) {
      // Don't redirect if we are hitting an auth endpoint (like check user status) to avoid loops
      // But if we are hitting a protected resource like /tickets/, we should redirect.
      const isAuthEndpoint = error.config.url.includes('/auth/user/');
      
      if (!isAuthEndpoint) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('user_role');
          window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
