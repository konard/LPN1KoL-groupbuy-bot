/**
 * Admin Store
 * Zustand store for admin panel state management
 */
import { create } from 'zustand';
import { adminApi } from '../services/adminApi';

let toastIdCounter = 0;

export const useAdminStore = create((set, get) => ({
  // Auth state
  adminUser: null,
  isAuthenticated: false,
  loadingCount: 0,
  isLoading: false,
  error: null,

  // Dashboard state
  dashboardStats: null,
  analyticsData: null,

  // Data state
  users: [],
  procurements: [],
  payments: [],
  transactions: [],
  categories: [],
  messages: [],

  // Pagination
  pagination: {
    users: { count: 0, next: null, previous: null },
    procurements: { count: 0, next: null, previous: null },
    payments: { count: 0, next: null, previous: null },
    transactions: { count: 0, next: null, previous: null },
    messages: { count: 0, next: null, previous: null },
  },

  // Toast state
  toasts: [],

  // Helper to increment/decrement loading counter
  startLoading: () => set((state) => {
    const newCount = state.loadingCount + 1;
    return { loadingCount: newCount, isLoading: newCount > 0 };
  }),
  stopLoading: () => set((state) => {
    const newCount = Math.max(0, state.loadingCount - 1);
    return { loadingCount: newCount, isLoading: newCount > 0 };
  }),

  // Actions - Auth
  checkAuth: async () => {
    get().startLoading();
    try {
      const user = await adminApi.checkAuth();
      set({ adminUser: user, isAuthenticated: true });
      return true;
    } catch (error) {
      set({ adminUser: null, isAuthenticated: false });
      return false;
    } finally {
      get().stopLoading();
    }
  },

  login: async (username, password) => {
    get().startLoading();
    set({ error: null });
    try {
      const user = await adminApi.login(username, password);
      set({ adminUser: user, isAuthenticated: true });
      return true;
    } catch (error) {
      set({ error: error.message });
      get().addToast(error.message, 'error');
      return false;
    } finally {
      get().stopLoading();
    }
  },

  logout: async () => {
    try {
      await adminApi.logout();
    } catch (error) {
      // Ignore errors on logout
    }
    set({ adminUser: null, isAuthenticated: false });
  },

  // Actions - Dashboard
  loadDashboardStats: async () => {
    get().startLoading();
    try {
      const stats = await adminApi.getDashboardStats();
      set({ dashboardStats: stats });
    } catch (error) {
      set({ error: error.message });
      get().addToast('Ошибка загрузки статистики', 'error');
    } finally {
      get().stopLoading();
    }
  },

  // Actions - Analytics
  loadAnalytics: async (params = {}) => {
    get().startLoading();
    try {
      const data = await adminApi.getAnalytics(params);
      set({ analyticsData: data });
    } catch (error) {
      set({ error: error.message });
      get().addToast('Ошибка загрузки аналитики', 'error');
    } finally {
      get().stopLoading();
    }
  },

  // Actions - Users
  loadUsers: async (params = {}) => {
    get().startLoading();
    try {
      const response = await adminApi.getUsers(params);
      set({
        users: response.results || response,
        pagination: {
          ...get().pagination,
          users: {
            count: response.count || 0,
            next: response.next,
            previous: response.previous,
          },
        },
      });
    } catch (error) {
      set({ error: error.message });
      get().addToast('Ошибка загрузки пользователей', 'error');
    } finally {
      get().stopLoading();
    }
  },

  toggleUserActive: async (userId) => {
    try {
      await adminApi.toggleUserActive(userId);
      const users = get().users.map((u) =>
        u.id === userId ? { ...u, is_active: !u.is_active } : u
      );
      set({ users });
      get().addToast('Статус пользователя обновлен', 'success');
    } catch (error) {
      get().addToast('Ошибка обновления статуса', 'error');
    }
  },

  toggleUserVerified: async (userId) => {
    try {
      await adminApi.toggleUserVerified(userId);
      const users = get().users.map((u) =>
        u.id === userId ? { ...u, is_verified: !u.is_verified } : u
      );
      set({ users });
      get().addToast('Статус верификации обновлен', 'success');
    } catch (error) {
      get().addToast('Ошибка обновления статуса', 'error');
    }
  },

  updateUserBalance: async (userId, amount, description) => {
    try {
      const result = await adminApi.updateUserBalance(userId, amount, description);
      const users = get().users.map((u) =>
        u.id === userId ? { ...u, balance: result.new_balance } : u
      );
      set({ users });
      get().addToast('Баланс обновлен', 'success');
      return result;
    } catch (error) {
      get().addToast('Ошибка обновления баланса', 'error');
      throw error;
    }
  },

  // Actions - Procurements
  loadProcurements: async (params = {}) => {
    get().startLoading();
    try {
      const response = await adminApi.getProcurements(params);
      set({
        procurements: response.results || response,
        pagination: {
          ...get().pagination,
          procurements: {
            count: response.count || 0,
            next: response.next,
            previous: response.previous,
          },
        },
      });
    } catch (error) {
      set({ error: error.message });
      get().addToast('Ошибка загрузки закупок', 'error');
    } finally {
      get().stopLoading();
    }
  },

  updateProcurementStatus: async (procurementId, status) => {
    try {
      await adminApi.updateProcurementStatus(procurementId, status);
      const procurements = get().procurements.map((p) =>
        p.id === procurementId ? { ...p, status } : p
      );
      set({ procurements });
      get().addToast('Статус закупки обновлен', 'success');
    } catch (error) {
      get().addToast('Ошибка обновления статуса', 'error');
    }
  },

  toggleProcurementFeatured: async (procurementId) => {
    try {
      await adminApi.toggleProcurementFeatured(procurementId);
      const procurements = get().procurements.map((p) =>
        p.id === procurementId ? { ...p, is_featured: !p.is_featured } : p
      );
      set({ procurements });
      get().addToast('Статус "Избранное" обновлен', 'success');
    } catch (error) {
      get().addToast('Ошибка обновления статуса', 'error');
    }
  },

  // Actions - Payments
  loadPayments: async (params = {}) => {
    get().startLoading();
    try {
      const response = await adminApi.getPayments(params);
      set({
        payments: response.results || response,
        pagination: {
          ...get().pagination,
          payments: {
            count: response.count || 0,
            next: response.next,
            previous: response.previous,
          },
        },
      });
    } catch (error) {
      set({ error: error.message });
      get().addToast('Ошибка загрузки платежей', 'error');
    } finally {
      get().stopLoading();
    }
  },

  // Actions - Transactions
  loadTransactions: async (params = {}) => {
    get().startLoading();
    try {
      const response = await adminApi.getTransactions(params);
      set({
        transactions: response.results || response,
        pagination: {
          ...get().pagination,
          transactions: {
            count: response.count || 0,
            next: response.next,
            previous: response.previous,
          },
        },
      });
    } catch (error) {
      set({ error: error.message });
      get().addToast('Ошибка загрузки транзакций', 'error');
    } finally {
      get().stopLoading();
    }
  },

  // Actions - Categories
  loadCategories: async () => {
    get().startLoading();
    try {
      const response = await adminApi.getCategories();
      set({ categories: response.results || response });
    } catch (error) {
      set({ error: error.message });
      get().addToast('Ошибка загрузки категорий', 'error');
    } finally {
      get().stopLoading();
    }
  },

  // Actions - Messages
  loadMessages: async (params = {}) => {
    get().startLoading();
    try {
      const response = await adminApi.getMessages(params);
      set({
        messages: response.results || response,
        pagination: {
          ...get().pagination,
          messages: {
            count: response.count || 0,
            next: response.next,
            previous: response.previous,
          },
        },
      });
    } catch (error) {
      set({ error: error.message });
      get().addToast('Ошибка загрузки сообщений', 'error');
    } finally {
      get().stopLoading();
    }
  },

  // Actions - Toast
  addToast: (message, type = 'info') => {
    const id = ++toastIdCounter;
    const toast = { id, message, type };
    set({ toasts: [...get().toasts, toast] });
    setTimeout(() => {
      get().removeToast(id);
    }, 3000);
  },

  removeToast: (id) => {
    set({ toasts: get().toasts.filter((t) => t.id !== id) });
  },

  // Clear error
  clearError: () => set({ error: null }),
}));
