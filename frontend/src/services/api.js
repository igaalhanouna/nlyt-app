import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL;

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('nlyt_token');
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
    if (error.response?.status === 401) {
      localStorage.removeItem('nlyt_token');
      localStorage.removeItem('nlyt_user');
      window.location.href = '/signin';
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  register: (data) => api.post('/api/auth/register', data),
  login: (data) => api.post('/api/auth/login', data),
  verifyEmail: (token) => api.get(`/api/auth/verify-email?token=${token}`),
  forgotPassword: (email) => api.post('/api/auth/forgot-password', { email }),
  resetPassword: (token, new_password) => api.post('/api/auth/reset-password', { token, new_password }),
  me: () => api.get('/api/auth/me'),
};

export const workspaceAPI = {
  create: (data) => api.post('/api/workspaces/', data),
  list: () => api.get('/api/workspaces/'),
  get: (id) => api.get(`/api/workspaces/${id}`),
};

export const appointmentAPI = {
  create: (data) => api.post('/api/appointments/', data),
  list: (workspace_id) => api.get('/api/appointments/', { params: { workspace_id } }),
  get: (id) => api.get(`/api/appointments/${id}`),
  update: (id, data) => api.patch(`/api/appointments/${id}`, data),
  delete: (id) => api.delete(`/api/appointments/${id}`),
  cancel: (id) => api.post(`/api/appointments/${id}/cancel`),
};

export const participantAPI = {
  add: (appointment_id, data) => api.post(`/api/participants/?appointment_id=${appointment_id}`, data),
  list: (appointment_id) => api.get(`/api/participants/?appointment_id=${appointment_id}`),
  get: (id) => api.get(`/api/participants/${id}`),
};

export const calendarAPI = {
  connectGoogle: () => api.get('/api/calendar/connect/google'),
  connectOutlook: () => api.get('/api/calendar/connect/outlook'),
  listConnections: () => api.get('/api/calendar/connections'),
  syncAppointment: (appointment_id, connection_id) => 
    api.post(`/api/calendar/sync/appointment/${appointment_id}?connection_id=${connection_id}`),
  exportICS: (appointment_id) => 
    `${API_BASE_URL}/api/calendar/export/ics/${appointment_id}`,
};

export const disputeAPI = {
  create: (data) => api.post('/api/disputes/', data),
  list: (appointment_id) => api.get('/api/disputes/', { params: { appointment_id } }),
  get: (id) => api.get(`/api/disputes/${id}`),
  updateStatus: (id, status, resolution) => 
    api.patch(`/api/disputes/${id}?status=${status}&resolution=${resolution || ''}`),
};

export const adminAPI = {
  getCasesForReview: () => api.get('/api/admin/cases/review'),
  getPendingDisputes: () => api.get('/api/admin/disputes/pending'),
  getAnalytics: () => api.get('/api/admin/analytics/overview'),
  getStripeEvents: (limit) => api.get(`/api/admin/stripe-events?limit=${limit || 50}`),
};

export default api;