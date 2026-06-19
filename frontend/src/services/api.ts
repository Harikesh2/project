import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Create axios instance
const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Custom hook to get authenticated API instance
export const useApi = () => {
  // Request interceptor to add auth token
  api.interceptors.request.use(
    async (config) => {
      try {
        // If using Clerk
        if (window.Clerk) {
          const token = await window.Clerk.session?.getToken();
          if (token) {
            config.headers.Authorization = `Bearer ${token}`;
            return config;
          }
        }

        // Fallback to demo token if Clerk is not available (for local testing without internet if needed)
        const demoToken = localStorage.getItem('demo_token');
        if (demoToken === 'demo_token_123') {
          config.headers.Authorization = `Bearer ${demoToken}`;
        }
      } catch (error) {
        console.error('Error getting auth token:', error);
      }
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor for error handling
  api.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        // Handle unauthorized access
        console.error('Unauthorized access - redirecting to login');
        localStorage.removeItem('demo_token');
        localStorage.removeItem('demo_user');
        window.location.reload();
      }
      return Promise.reject(error);
    }
  );

  return api;
};

export default api;