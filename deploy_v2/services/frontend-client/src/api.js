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
  login: (username, password) => request('POST', '/auth/login', { username, password }),
  register: (username, email, password) => request('POST', '/auth/register', { username, email, password }),
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

  // ── Admin ───────────────────────────────────────────────────────────────────
  listUsers: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request('GET', `/users${qs ? '?' + qs : ''}`)
  },
  getUser: (id) => request('GET', `/users/${id}`),
  updateUser: (id, data) => request('PATCH', `/users/${id}`, data),
  deleteUser: (id) => request('DELETE', `/users/${id}`),
  adminStats: () => request('GET', '/admin/stats'),

  // ── Health ──────────────────────────────────────────────────────────────────
  health: () => request('GET', '/health'),
}

export const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || 'ws://localhost:8001'
export { ApiError }
