/**
 * API client with:
 *  - Structured error handling for 401/403/409/429/5xx
 *  - Automatic token refresh on 401 (single retry)
 *  - AbortController registration for forced-cancel on ban
 *  - 429 → ApiError with retryAfter field so UI can show countdown
 */
import { registerFetchController } from './websocket.js';

const API_URL = '/api';

// ─── Structured Error ────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(status, code, message, retryAfter = null) {
    super(message);
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter; // seconds; set for 429 responses
  }
}

// ─── Token refresh state ─────────────────────────────────────────────────────

let _refreshPromise = null;

async function _doRefreshToken() {
  const refreshToken = localStorage.getItem('refreshToken');
  if (!refreshToken) throw new ApiError(401, 'NO_REFRESH_TOKEN', 'No refresh token available');

  const resp = await fetch(`${API_URL}/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refreshToken }),
  });

  if (!resp.ok) {
    localStorage.removeItem('authToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('wsToken');
    localStorage.removeItem('userId');
    throw new ApiError(401, 'REFRESH_FAILED', 'Session expired, please log in again');
  }

  const data = await resp.json();
  const tokens = data.data || data;
  if (tokens.accessToken) localStorage.setItem('authToken', tokens.accessToken);
  if (tokens.refreshToken) localStorage.setItem('refreshToken', tokens.refreshToken);
  return tokens.accessToken;
}

function refreshToken() {
  if (!_refreshPromise) {
    _refreshPromise = _doRefreshToken().finally(() => { _refreshPromise = null; });
  }
  return _refreshPromise;
}

// ─── Core request ─────────────────────────────────────────────────────────────

async function request(endpoint, options = {}, _isRetry = false) {
  const url = `${API_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    'Cache-Control': 'no-cache',
    ...options.headers,
  };

  const token = localStorage.getItem('authToken');
  if (token) headers['Authorization'] = `Bearer ${token}`;

  // Register AbortController so WebSocketManager can cancel on ban
  const controller = new AbortController();
  const unregister = registerFetchController(controller);

  let response;
  try {
    response = await fetch(url, {
      cache: 'no-store',
      ...options,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    unregister();
    if (err.name === 'AbortError') {
      throw new ApiError(0, 'REQUEST_ABORTED', 'Request was aborted');
    }
    throw err;
  }
  unregister();

  // ── 401: attempt token refresh once ──────────────────────────────────────
  if (response.status === 401 && !_isRetry) {
    try {
      await refreshToken();
      return request(endpoint, options, true);
    } catch (_) {
      // Refresh failed → trigger logout via store (dispatched by caller/component)
      throw new ApiError(401, 'SESSION_EXPIRED', 'Session expired, please log in again');
    }
  }

  if (!response.ok) {
    let errorBody = {};
    try { errorBody = await response.json(); } catch (_) {}

    const code = errorBody.code || `HTTP_${response.status}`;
    const message = errorBody.message || errorBody.detail || `HTTP error ${response.status}`;

    // ── 429: extract Retry-After header ───────────────────────────────────
    let retryAfter = null;
    if (response.status === 429) {
      const ra = response.headers.get('Retry-After');
      retryAfter = ra ? parseInt(ra, 10) : 60;
    }

    throw new ApiError(response.status, code, message, retryAfter);
  }

  return response.json();
}

async function requestFormData(endpoint, formData) {
  const url = `${API_URL}${endpoint}`;
  const headers = { 'Cache-Control': 'no-cache' };
  const token = localStorage.getItem('authToken');
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const controller = new AbortController();
  const unregister = registerFetchController(controller);

  let response;
  try {
    response = await fetch(url, {
      method: 'POST',
      cache: 'no-store',
      headers,
      body: formData,
      signal: controller.signal,
    });
  } catch (err) {
    unregister();
    if (err.name === 'AbortError') {
      throw new ApiError(0, 'REQUEST_ABORTED', 'Request was aborted');
    }
    throw err;
  }
  unregister();

  if (!response.ok) {
    let errorBody = {};
    try { errorBody = await response.json(); } catch (_) {}
    const code = errorBody.code || `HTTP_${response.status}`;
    const message = errorBody.message || errorBody.detail || `HTTP error ${response.status}`;
    throw new ApiError(response.status, code, message);
  }

  return response.json();
}

// ─── Public API ───────────────────────────────────────────────────────────────

export const api = {
  // Auth-service endpoints

  // Step 1: send phone number to initiate login (OTP is dispatched to registered email)
  loginUser: (data) =>
    request('/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Step 2: confirm login by submitting the OTP received by email
  confirmLogin: (data) =>
    request('/v1/auth/login/confirm', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Step 1: send phone + email to initiate registration (OTP dispatched to provided email)
  registerAuthUser: (data) =>
    request('/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Step 2: confirm registration by submitting the OTP received by email
  confirmRegistration: (data) =>
    request('/v1/auth/register/confirm', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Resend OTP code for an ongoing login or registration session (max once per 30s)
  resendOtp: (data) =>
    request('/v1/auth/resend-code', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  logoutUser: () =>
    request('/v1/auth/logout', { method: 'POST' }),

  // User endpoints
  getUser: (userId) => request(`/users/${userId}/`),

  getWsToken: (userId) => request(`/users/${userId}/ws_token/`),

  getUserByPlatform: (platform, platformUserId) =>
    request(`/users/by_platform/?platform=${platform}&platform_user_id=${platformUserId}`),

  getUserByEmail: (email) =>
    request(`/users/by_email/?email=${encodeURIComponent(email)}`),

  searchUsers: (query) =>
    request(`/users/search/?q=${encodeURIComponent(query)}`),

  getUserByPhone: (phone) =>
    request(`/users/by_phone/?phone=${encodeURIComponent(phone)}`),

  registerUser: (data) =>
    request('/users/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateUser: (userId, data) =>
    request(`/users/${userId}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  getUserBalance: (userId) => request(`/users/${userId}/balance/`),

  // Procurement endpoints
  getProcurements: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/procurements/?${query}`);
  },

  getProcurement: (id) => request(`/procurements/${id}/`),

  createProcurement: (data) =>
    request('/procurements/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  joinProcurement: (id, data) =>
    request(`/procurements/${id}/join/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  addParticipant: (id, data) =>
    request(`/procurements/${id}/add_participant/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  inviteUser: (id, email, organizerId) =>
    request(`/procurements/${id}/invite/`, {
      method: 'POST',
      body: JSON.stringify({ email, organizer_id: organizerId }),
    }),

  leaveProcurement: (id, data) =>
    request(`/procurements/${id}/leave/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getUserProcurements: (userId) => request(`/procurements/user/${userId}/`),

  getCategories: () => request('/procurements/categories/'),

  // Procurement action endpoints
  stopProcurement: (id) =>
    request(`/procurements/${id}/stop_amount/`, { method: 'POST' }),

  approveSupplier: (id, supplierId) =>
    request(`/procurements/${id}/approve_supplier/`, {
      method: 'POST',
      body: JSON.stringify({ supplier_id: supplierId }),
    }),

  closeProcurement: (id) =>
    request(`/procurements/${id}/close/`, { method: 'POST' }),

  getReceiptTable: (id) => request(`/procurements/${id}/receipt_table/`),

  getVoteResults: (id) => request(`/procurements/${id}/vote_results/`),

  castVote: (id, data) =>
    request(`/procurements/${id}/cast_vote/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getParticipants: (procurementId) =>
    request(`/procurements/${procurementId}/participants/`),

  updateParticipantStatus: (participantId, newStatus) =>
    request(`/procurements/participants/${participantId}/update_status/`, {
      method: 'POST',
      body: JSON.stringify({ status: newStatus }),
    }),

  // Chat endpoints
  getMessages: (procurementId, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return request(`/chat/messages/?procurement=${procurementId}&${query}`);
  },

  sendMessage: (data) =>
    request('/chat/messages/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getNotifications: (userId) => request(`/chat/notifications/?user_id=${userId}`),

  markNotificationRead: (notificationId) =>
    request(`/chat/notifications/${notificationId}/mark_read/`, { method: 'POST' }),

  markAllNotificationsRead: (userId) =>
    request('/chat/notifications/mark_all_read/', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    }),

  updateProcurementStatus: (id, newStatus, userId) =>
    request(`/procurements/${id}/update_status/`, {
      method: 'POST',
      body: JSON.stringify({ status: newStatus, user_id: userId }),
    }),

  // Payment endpoints
  createPayment: (data) =>
    request('/payments/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getPaymentStatus: (paymentId) => request(`/payments/${paymentId}/status/`),

  getTransactions: (userId) => request(`/payments/transactions/?user_id=${userId}`),

  // Supplier profile endpoints
  getSuppliers: () => request('/users/?role=supplier'),

  // Chat voting endpoints
  getChatVote: (procurementId) => request(`/procurements/${procurementId}/vote_results/`).catch(() => null),

  castChatVote: (procurementId, data) =>
    request(`/procurements/${procurementId}/cast_vote/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  closeChatVote: (procurementId, userId) =>
    request(`/procurements/${procurementId}/close_vote/`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    }).catch(() => ({ fallback: true })),

  getVoteCloseStatus: (procurementId) =>
    request(`/procurements/${procurementId}/vote_close_status/`).catch(() => null),

  // Media upload (chat)
  uploadChatMedia: (formData) =>
    requestFormData('/v1/chat/media/upload', formData),

  // Purchase editors (shared access)
  getPurchaseEditors: (purchaseId) =>
    request(`/v1/purchases/${purchaseId}/editors`),

  addPurchaseEditor: (purchaseId, userId) =>
    request(`/v1/purchases/${purchaseId}/editors`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    }),

  removePurchaseEditor: (purchaseId, userId) =>
    request(`/v1/purchases/${purchaseId}/editors/${userId}`, {
      method: 'DELETE',
    }),

  // v1 Voting (purchase-service)
  getVotingSession: (sessionId) =>
    request(`/v1/voting/sessions/${sessionId}`),

  getVotingResults: (sessionId, userId) => {
    const q = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
    return request(`/v1/voting/sessions/${sessionId}/results${q}`);
  },

  castVotingVote: (sessionId, data) =>
    request(`/v1/voting/sessions/${sessionId}/votes`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};
