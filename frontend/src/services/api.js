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
      const url = error.config?.url || '';
      const isAuthRoute = url.includes('/api/auth/login') || url.includes('/api/auth/register');
      if (!isAuthRoute) {
        localStorage.removeItem('nlyt_token');
        localStorage.removeItem('nlyt_user');
        window.location.href = '/signin';
      }
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
  checkActivation: (id) => api.post(`/api/appointments/${id}/check-activation`),
  retryGuarantee: (id) => api.post(`/api/appointments/${id}/retry-organizer-guarantee`),
};

export const participantAPI = {
  add: (appointment_id, data) => api.post(`/api/participants/?appointment_id=${appointment_id}`, data),
  list: (appointment_id) => api.get(`/api/participants/?appointment_id=${appointment_id}`),
  get: (id) => api.get(`/api/participants/${id}`),
};

export const invitationAPI = {
  resend: (token) => api.post(`/api/invitations/${token}/resend`),
};

export const calendarAPI = {
  connectGoogle: () => {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return api.get(`/api/calendar/connect/google?timezone=${encodeURIComponent(tz)}`);
  },
  disconnectGoogle: () => api.delete('/api/calendar/connections/google'),
  connectOutlook: () => {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return api.get(`/api/calendar/connect/outlook?timezone=${encodeURIComponent(tz)}`);
  },
  disconnectOutlook: () => api.delete('/api/calendar/connections/outlook'),
  listConnections: () => api.get('/api/calendar/connections'),
  syncAppointment: (appointment_id, provider = 'google') => api.post(`/api/calendar/sync/appointment/${appointment_id}?provider=${provider}`),
  unsyncAppointment: (appointment_id) => api.delete(`/api/calendar/sync/appointment/${appointment_id}`),
  getSyncStatus: (appointment_id) => api.get(`/api/calendar/sync/status/${appointment_id}`),
  getAutoSyncSettings: () => api.get('/api/calendar/auto-sync/settings'),
  updateAutoSyncSettings: (data) => api.put('/api/calendar/auto-sync/settings', data),
  exportICS: (appointment_id) =>
    `${API_BASE_URL}/api/calendar/export/ics/${appointment_id}`,
};

export const attendanceAPI = {
  evaluate: (appointment_id) => api.post(`/api/attendance/evaluate/${appointment_id}`),
  reevaluate: (appointment_id) => api.post(`/api/attendance/reevaluate/${appointment_id}`),
  get: (appointment_id) => api.get(`/api/attendance/${appointment_id}`),
  reclassify: (record_id, data) => api.put(`/api/attendance/reclassify/${record_id}`, data),
  pendingReviews: () => api.get('/api/attendance/pending-reviews/list'),
};

export const checkinAPI = {
  manual: (data) => api.post('/api/checkin/manual', data),
  verifyQR: (data) => api.post('/api/checkin/qr/verify', data),
  gps: (data) => api.post('/api/checkin/gps', data),
  getQR: (appointment_id, invitation_token) => api.get(`/api/checkin/qr/${appointment_id}?invitation_token=${invitation_token}`),
  getStatus: (appointment_id, invitation_token) => api.get(`/api/checkin/status/${appointment_id}?invitation_token=${invitation_token}`),
  getEvidence: (appointment_id) => api.get(`/api/checkin/evidence/${appointment_id}`),
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

export const modificationAPI = {
  create: (data) => api.post('/api/modifications/', data),
  getForAppointment: (appointmentId) => api.get(`/api/modifications/appointment/${appointmentId}`),
  getActive: (appointmentId) => api.get(`/api/modifications/active/${appointmentId}`),
  respond: (proposalId, data) => api.post(`/api/modifications/${proposalId}/respond`, data),
  cancel: (proposalId) => api.post(`/api/modifications/${proposalId}/cancel`),
};

export const videoEvidenceAPI = {
  ingest: (appointmentId, data) => api.post(`/api/video-evidence/${appointmentId}/ingest`, data),
  ingestFile: (appointmentId, formData) => api.post(`/api/video-evidence/${appointmentId}/ingest-file`, formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  get: (appointmentId) => api.get(`/api/video-evidence/${appointmentId}`),
  getLogs: (appointmentId) => api.get(`/api/video-evidence/${appointmentId}/logs`),
  getLog: (appointmentId, logId) => api.get(`/api/video-evidence/${appointmentId}/log/${logId}`),
  createMeeting: (appointmentId, data) => api.post(`/api/video-evidence/${appointmentId}/create-meeting`, data || {}),
  fetchAttendance: (appointmentId) => api.post(`/api/video-evidence/${appointmentId}/fetch-attendance`),
  providerStatus: () => api.get(`/api/video-evidence/provider-status`),
  connectZoom: (data) => api.post('/api/video-evidence/connect/zoom', data || {}),
  disconnectZoom: () => api.delete('/api/video-evidence/connect/zoom'),
  connectTeams: (data) => api.post('/api/video-evidence/connect/teams', data || {}),
  disconnectTeams: () => api.delete('/api/video-evidence/connect/teams'),
};

export const proofAPI = {
  getSessions: (appointmentId) => api.get(`/api/proof/${appointmentId}/sessions`),
  validate: (appointmentId, sessionId, finalStatus) => api.post(`/api/proof/${appointmentId}/validate`, { session_id: sessionId, final_status: finalStatus }),
};

export const walletAPI = {
  get: () => api.get('/api/wallet'),
  getTransactions: (limit = 50, skip = 0) => api.get(`/api/wallet/transactions?limit=${limit}&skip=${skip}`),
  getDistributions: (limit = 50, skip = 0) => api.get(`/api/wallet/distributions?limit=${limit}&skip=${skip}`),
  getDistribution: (id) => api.get(`/api/wallet/distributions/${id}`),
  contestDistribution: (id, reason) => api.post(`/api/wallet/distributions/${id}/contest`, { reason }),
};

export const connectAPI = {
  onboard: () => api.post('/api/connect/onboard'),
  getStatus: () => api.get('/api/connect/status'),
  getDashboard: () => api.post('/api/connect/dashboard'),
};

export default api;