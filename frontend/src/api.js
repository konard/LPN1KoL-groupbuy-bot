const BASE = import.meta.env.VITE_BACKEND_URL || ''

function authHeaders() {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  login: (username, password) => request('POST', '/auth/login', { username, password }),
  register: (username, email, password) => request('POST', '/auth/register', { username, email, password }),
  me: () => request('GET', '/auth/me'),
  health: () => request('GET', '/health'),
}

export const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || 'ws://localhost:8001'
