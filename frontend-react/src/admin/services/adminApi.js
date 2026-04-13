/**
 * Admin API Service
 * Handles all admin-related API calls
 */

const API_URL = '/api/admin';

function getCsrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : '';
}

function buildQuery(params) {
  const filtered = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined)
  );
  return new URLSearchParams(filtered).toString();
}

// Request deduplication: prevent multiple identical GET requests from firing concurrently.
// Maps URL -> Promise so that concurrent calls to the same endpoint share one in-flight request.
const inflightRequests = new Map();

async function request(endpoint, options = {}) {
  const url = `${API_URL}${endpoint}`;
  const method = (options.method || 'GET').toUpperCase();
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  // Django requires CSRF token for state-changing requests
  if (method !== 'GET' && method !== 'HEAD') {
    headers['X-CSRFToken'] = getCsrfToken();
  }

  // Deduplicate concurrent GET requests to the same URL
  if (method === 'GET') {
    const existing = inflightRequests.get(url);
    if (existing) {
      return existing;
    }
  }

  const controller = options.signal
    ? undefined // caller provided their own signal
    : new AbortController();
  const timeoutId = controller
    ? setTimeout(() => controller.abort(), 15000)
    : null;
  const signal = options.signal || (controller ? controller.signal : undefined);

  const fetchPromise = (async () => {
    let response;
    try {
      response = await fetch(url, {
        ...options,
        method,
        headers,
        credentials: 'include', // Include cookies for session auth
        signal,
      });
    } catch (err) {
      if (err.name === 'AbortError') {
        throw new Error('Превышено время ожидания ответа от сервера');
      }
      throw err;
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
    }

    if (response.status === 401) {
      const error = await response.json().catch(() => ({}));
      // Only redirect to login when not already on the auth endpoint
      // (avoids redirect loop when login credentials are wrong)
      if (endpoint !== '/auth/') {
        window.location.href = '/admin-panel/login';
      }
      throw new Error(error.detail || 'Unauthorized');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    return response.json();
  })();

  // Track in-flight GET requests for deduplication
  if (method === 'GET') {
    inflightRequests.set(url, fetchPromise);
    fetchPromise.finally(() => {
      inflightRequests.delete(url);
    });
  }

  return fetchPromise;
}

export const adminApi = {
  // Auth
  checkAuth: () => request('/auth/'),
  login: (username, password) =>
    request('/auth/', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () =>
    request('/auth/', {
      method: 'DELETE',
    }),

  // Dashboard
  getDashboardStats: () => request('/dashboard/'),

  // Analytics
  getAnalytics: (params = {}) => {
    const query = buildQuery(params);
    return request(`/analytics/?${query}`);
  },

  // Users
  getUsers: (params = {}) => {
    const query = buildQuery(params);
    return request(`/users/?${query}`);
  },
  getUser: (id) => request(`/users/${id}/`),
  updateUser: (id, data) =>
    request(`/users/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteUser: (id) =>
    request(`/users/${id}/`, {
      method: 'DELETE',
    }),
  toggleUserActive: (id) =>
    request(`/users/${id}/toggle_active/`, { method: 'POST' }),
  toggleUserVerified: (id) =>
    request(`/users/${id}/toggle_verified/`, { method: 'POST' }),
  updateUserBalance: (id, amount, description) =>
    request(`/users/${id}/update_balance/`, {
      method: 'POST',
      body: JSON.stringify({ amount, description }),
    }),
  bulkUserAction: (ids, action) =>
    request('/users/bulk_action/', {
      method: 'POST',
      body: JSON.stringify({ ids, action }),
    }),

  // Procurements
  getProcurements: (params = {}) => {
    const query = buildQuery(params);
    return request(`/procurements/?${query}`);
  },
  getProcurement: (id) => request(`/procurements/${id}/`),
  updateProcurement: (id, data) =>
    request(`/procurements/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteProcurement: (id) =>
    request(`/procurements/${id}/`, {
      method: 'DELETE',
    }),
  updateProcurementStatus: (id, status) =>
    request(`/procurements/${id}/update_status/`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    }),
  toggleProcurementFeatured: (id) =>
    request(`/procurements/${id}/toggle_featured/`, { method: 'POST' }),
  getProcurementParticipants: (id) => request(`/procurements/${id}/participants/`),
  bulkProcurementAction: (ids, action) =>
    request('/procurements/bulk_action/', {
      method: 'POST',
      body: JSON.stringify({ ids, action }),
    }),

  // Payments
  getPayments: (params = {}) => {
    const query = buildQuery(params);
    return request(`/payments/?${query}`);
  },
  getPayment: (id) => request(`/payments/${id}/`),
  getPaymentsSummary: () => request('/payments/summary/'),

  // Transactions
  getTransactions: (params = {}) => {
    const query = buildQuery(params);
    return request(`/transactions/?${query}`);
  },
  getTransaction: (id) => request(`/transactions/${id}/`),

  // Categories
  getCategories: () => request('/categories/'),
  createCategory: (data) =>
    request('/categories/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateCategory: (id, data) =>
    request(`/categories/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteCategory: (id) =>
    request(`/categories/${id}/`, {
      method: 'DELETE',
    }),

  // Messages
  getMessages: (params = {}) => {
    const query = buildQuery(params);
    return request(`/messages/?${query}`);
  },
  toggleMessageDelete: (id) =>
    request(`/messages/${id}/toggle_delete/`, { method: 'POST' }),

  // Admin Chat
  sendAdminMessage: (userId, text) =>
    request('/chat/admin_message/', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, text }),
    }),

  // Notifications
  getNotifications: (params = {}) => {
    const query = buildQuery(params);
    return request(`/notifications/?${query}`);
  },
  sendBulkNotification: (userIds, notificationType, title, message) =>
    request('/notifications/send_bulk/', {
      method: 'POST',
      body: JSON.stringify({
        user_ids: userIds,
        notification_type: notificationType,
        title,
        message,
      }),
    }),
};
