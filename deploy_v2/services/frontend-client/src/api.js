const BASE = import.meta.env.VITE_BACKEND_URL || ''

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

function authHeaders() {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(method, path, body, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...authHeaders() }
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: opts.signal,
  })

  if (res.status === 401) {
    localStorage.removeItem('token')
    window.dispatchEvent(new Event('auth:logout'))
    throw new ApiError('Session expired, please log in again', 401)
  }

  if (!res.ok) {
    let detail = res.statusText
    try {
      const json = await res.json()
      detail = json.detail || json.message || detail
    } catch {}
    throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail), res.status, detail)
  }

  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // ── Auth ────────────────────────────────────────────────────────────────────
  // Step 1: send phone + password → receives email_hint, sends OTP to email
  login: (phone, password) => request('POST', '/auth/login', { phone, password }),
  // Step 2: verify OTP code → receives access_token
  verifyCode: (phone, code) => request('POST', '/auth/verify-code', { phone, code }),
  register: (username, phone, email, password) =>
    request('POST', '/auth/register', { username, phone, email, password }),
  me: () => request('GET', '/auth/me'),
  changePassword: (current_password, new_password) =>
    request('POST', '/auth/change-password', { current_password, new_password }),

  // ── Procurements ────────────────────────────────────────────────────────────
  listProcurements: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request('GET', `/procurements${qs ? '?' + qs : ''}`)
  },
  getProcurement: (id) => request('GET', `/procurements/${id}`),
  createProcurement: (data) => request('POST', '/procurements', data),
  updateProcurement: (id, data) => request('PATCH', `/procurements/${id}`, data),
  deleteProcurement: (id) => request('DELETE', `/procurements/${id}`),
  listParticipants: (id) => request('GET', `/procurements/${id}/participants`),
  joinProcurement: (id, quantity) => request('POST', `/procurements/${id}/join`, { quantity }),
  leaveProcurement: (id) => request('DELETE', `/procurements/${id}/leave`),
  getReceipt: (id) => request('GET', `/procurements/${id}/receipt`),
  setStopAmount: (id, stop_at_amount) => request('POST', `/procurements/${id}/stop-amount`, { stop_at_amount }),
  approveSupplier: (id, supplier_name, price_per_unit) =>
    request('POST', `/procurements/${id}/approve-supplier`, { supplier_name, price_per_unit }),
  closeProcurement: (id, status = 'completed') =>
    request('POST', `/procurements/${id}/close`, { status }),
  toggleFeatured: (id) => request('POST', `/procurements/${id}/toggle-featured`),
  searchProcurements: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request('GET', `/search/procurements${qs ? '?' + qs : ''}`)
  },

  // ── Votes ───────────────────────────────────────────────────────────────────
  castVote: (procId, option) => request('POST', `/procurements/${procId}/votes`, { option }),
  voteResults: (procId) => request('GET', `/procurements/${procId}/votes`),

  // ── Invitations ─────────────────────────────────────────────────────────────
  inviteUser: (procId, invitee_id) => request('POST', `/procurements/${procId}/invitations`, { invitee_id }),
  myInvitations: () => request('GET', '/invitations'),
  respondInvitation: (invId, accept) =>
    request('POST', `/invitations/${invId}/respond?accept=${accept ? 'true' : 'false'}`),

  // ── Categories ──────────────────────────────────────────────────────────────
  listCategories: () => request('GET', '/categories'),
  createCategory: (data) => request('POST', '/categories', data),
  deleteCategory: (id) => request('DELETE', `/categories/${id}`),

  // ── Payments ────────────────────────────────────────────────────────────────
  listPayments: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request('GET', `/payments${qs ? '?' + qs : ''}`)
  },
  getPayment: (id) => request('GET', `/payments/${id}`),
  createPayment: (data) => request('POST', '/payments', data),

  // ── Chat ────────────────────────────────────────────────────────────────────
  getRoomHistory: (room, limit = 50) => request('GET', `/chat/${room}/messages?limit=${limit}`),
  sendChatMessage: (room, text) => request('POST', `/chat/${room}/messages`, { text }),
  markRoomRead: (room) => request('POST', `/chat/${room}/mark-read`),
  roomUnreadCount: (room) => request('GET', `/chat/${room}/unread-count`),

  // ── Notifications ───────────────────────────────────────────────────────────
  listNotifications: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request('GET', `/notifications${qs ? '?' + qs : ''}`)
  },
  unreadNotificationCount: () => request('GET', '/notifications/unread-count'),
  markNotificationRead: (id) => request('POST', `/notifications/${id}/read`),
  markAllNotificationsRead: () => request('POST', '/notifications/mark-all-read'),

  // ── Reviews ─────────────────────────────────────────────────────────────────
  createReview: (data) => request('POST', '/reviews', data),
  userReviews: (userId) => request('GET', `/users/${userId}/reviews`),
  userRating: (userId) => request('GET', `/users/${userId}/rating`),

  // ── Complaints ──────────────────────────────────────────────────────────────
  createComplaint: (data) => request('POST', '/complaints', data),
  listComplaints: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request('GET', `/complaints${qs ? '?' + qs : ''}`)
  },
  updateComplaint: (id, data) => request('PATCH', `/complaints/${id}`, data),

  // ── Admin ───────────────────────────────────────────────────────────────────
  listUsers: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request('GET', `/users${qs ? '?' + qs : ''}`)
  },
  getUser: (id) => request('GET', `/users/${id}`),
  updateUser: (id, data) => request('PATCH', `/users/${id}`, data),
  deleteUser: (id) => request('DELETE', `/users/${id}`),
  searchUsers: (q, limit = 20) => request('GET', `/users/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  getBalance: (userId) => request('GET', `/users/${userId}/balance`),
  updateBalance: (userId, amount, reason = '') =>
    request('POST', `/users/${userId}/balance`, { amount, reason }),
  adminStats: () => request('GET', '/admin/stats'),
  adminAnalytics: () => request('GET', '/admin/analytics'),
  adminBroadcast: (data) => request('POST', '/admin/broadcast', data),
  adminActivityLog: (limit = 100) => request('GET', `/admin/activity-log?limit=${limit}`),
  sendNotification: (data) => request('POST', '/notifications', data),

  // ── Health ──────────────────────────────────────────────────────────────────
  health: () => request('GET', '/health'),
}

export const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || 'ws://localhost:8001'
export { ApiError }
