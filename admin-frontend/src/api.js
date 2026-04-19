const BASE = '/api/admin'

async function request(path, options = {}) {
  const token = localStorage.getItem('admin_token')
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  login: (body) => request('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  users: (params = '') => request(`/users${params}`),
  purchases: (params = '') => request(`/purchases${params}`),
  payments: (params = '') => request(`/payments${params}`),
  health: () => request('/health'),
}
