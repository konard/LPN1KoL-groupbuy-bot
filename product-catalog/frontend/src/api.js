import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({ baseURL: BASE_URL })

// Attach token from localStorage to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-refresh on 401
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const { data } = await axios.post(`${BASE_URL}/auth/refresh`, { refresh_token: refreshToken })
          localStorage.setItem('access_token', data.access_token)
          original.headers.Authorization = `Bearer ${data.access_token}`
          return api(original)
        } catch {
          localStorage.clear()
          window.location.reload()
        }
      }
    }
    return Promise.reject(err)
  }
)

// Auth
export const login = (username, password) => {
  const form = new URLSearchParams()
  form.append('username', username)
  form.append('password', password)
  return api.post('/auth/login', form, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
}

export const getMe = () => api.get('/auth/me')

// Categories
export const getCategories = () => api.get('/categories')
export const createCategory = (name) => api.post('/categories', { name })
export const updateCategory = (id, name) => api.put(`/categories/${id}`, { name })
export const deleteCategory = (id) => api.delete(`/categories/${id}`)

// Products
export const getProducts = (params) => api.get('/products', { params })
export const getProduct = (id) => api.get(`/products/${id}`)
export const createProduct = (data) => api.post('/products', data)
export const updateProduct = (id, data) => api.put(`/products/${id}`, data)
export const deleteProduct = (id) => api.delete(`/products/${id}`)

// Currency
export const convertToUsd = (amount) => api.get('/convert-usd', { params: { amount } })

// Admin
export const adminGetUsers = () => api.get('/admin/users')
export const adminCreateUser = (data) => api.post('/admin/users', data)
export const adminToggleBlock = (id) => api.patch(`/admin/users/${id}/block`)
export const adminDeleteUser = (id) => api.delete(`/admin/users/${id}`)
export const adminChangePassword = (id, new_password) =>
  api.patch(`/admin/users/${id}/password`, { new_password })
