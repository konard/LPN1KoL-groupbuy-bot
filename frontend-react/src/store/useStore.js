import { create } from 'zustand';
import { api, ApiError } from '../services/api';
import {batchProcessProcurements, generatePlatformUserId} from '../services/wasm';

function restoreUserFromToken() {
  try {
    const token = localStorage.getItem('authToken');
    const userId = localStorage.getItem('userId');
    if (!token || !userId) return null;
    const payload = JSON.parse(atob(token.split('.')[1]));
    const coreId = localStorage.getItem('coreUserId');
    return {
      id: payload.sub || userId,
      email: payload.email,
      role: payload.role,
      coreId: coreId ? parseInt(coreId, 10) : null,
    };
  } catch (_) {
    return null;
  }
}

export const useStore = create((set, get) => ({
  // User state — restored synchronously from JWT so the session survives page reloads
  user: restoreUserFromToken(),
  isLoading: false,
  error: null,

  // Theme
  theme: 'light',

  // Chat state
  currentChat: null,
  procurements: [],
  messages: [],
  unreadCounts: {},

  // Modal state
  loginModalOpen: false,
  procurementModalOpen: false,
  createProcurementModalOpen: false,
  depositModalOpen: false,
  selectedProcurement: null,

  // Toast state
  toasts: [],

  // Sidebar state (mobile)
  sidebarOpen: false,

  // Sidebar active tab
  sidebarTab: 'chats',

  // Burger menu state
  burgerMenuOpen: false,

  // Actions - User
  loadUser: async (userId) => {
    set({ isLoading: true, error: null });
    try {
      const coreUser = await api.getUser(userId);
      // Preserve auth-service identity (UUID id) while enriching with core user fields
      const currentUser = get().user;
      const user = {
        ...coreUser,
        id: currentUser?.id || userId,
        coreId: coreUser.id,
      };
      if (coreUser.id) {
        localStorage.setItem('coreUserId', String(coreUser.id));
      }
      set({ user, isLoading: false });
      // Fetch a fresh WebSocket JWT token so the WS server can authenticate.
      // Fire-and-forget: a failure here must not block the login flow.
      // Use the integer core user ID since the ws_token endpoint uses Django pk.
      api.getWsToken(coreUser.id).then(({ token }) => {
        if (token) localStorage.setItem('wsToken', token);
      }).catch(() => {});
    } catch (error) {
      set({ error: error.message, isLoading: false });
      if (error instanceof ApiError && error.status === 401) {
        localStorage.removeItem('userId');
        localStorage.removeItem('coreUserId');
        localStorage.removeItem('authToken');
        localStorage.removeItem('refreshToken');
        localStorage.removeItem('wsToken');
        set({ user: null, loginModalOpen: true });
      }
    }
  },

  // Pending OTP state: { phone, context: 'login' | 'registration' }
  otpPending: null,

  // Step 1: initiate login by phone — OTP is sent to the user's registered email
  login: async (data) => {
    set({ isLoading: true, error: null });
    try {
      await api.loginUser({ phone: data.phone });
      set({ isLoading: false, otpPending: { phone: data.phone, context: 'login' } });
    } catch (error) {
      set({ error: error.message, isLoading: false });
      get().addToast(error.message, 'error');
      throw error;
    }
  },

  // Step 2: confirm login by submitting the OTP code
  confirmLogin: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const result = await api.confirmLogin({ phone: data.phone, otp: data.otp });
      const tokens = result.data || result;
      if (tokens.accessToken) localStorage.setItem('authToken', tokens.accessToken);
      if (tokens.refreshToken) localStorage.setItem('refreshToken', tokens.refreshToken);
      const payload = JSON.parse(atob(tokens.accessToken.split('.')[1]));
      const user = { id: payload.sub, email: payload.email, role: payload.role, coreId: null };
      localStorage.setItem('userId', user.id);
      set({ user, isLoading: false, loginModalOpen: false, otpPending: null });
      // Fetch core user ID (integer) needed for core API calls — fire-and-forget
      api.getUserByEmail(payload.email).then((coreUser) => {
        if (coreUser && coreUser.id) {
          localStorage.setItem('coreUserId', String(coreUser.id));
          set((state) => ({ user: state.user ? { ...state.user, coreId: coreUser.id } : state.user }));
        }
      }).catch(() => {});
      get().loadProcurements();
      return user;
    } catch (error) {
      set({ error: error.message, isLoading: false });
      get().addToast(error.message, 'error');
      throw error;
    }
  },

  // Step 1: initiate registration with phone + email — OTP is sent to the provided email
  register: async (data) => {
    set({ isLoading: true, error: null });
    try {
      await api.registerAuthUser({
        phone: data.phone,
        email: data.email,
        firstName: data.first_name || undefined,
        lastName: data.last_name || undefined,
        role: data.role || undefined,
      });
      set({ isLoading: false, otpPending: { phone: data.phone, context: 'registration' } });
    } catch (error) {
      set({ error: error.message, isLoading: false });
      get().addToast('Ошибка регистрации: ' + error.message, 'error');
      throw error;
    }
  },

  // Resend OTP for an in-progress login or registration session
  resendOtp: async () => {
    const { otpPending } = get();
    if (!otpPending) return;
    set({ isLoading: true, error: null });
    try {
      await api.resendOtp({ phone: otpPending.phone, context: otpPending.context });
      set({ isLoading: false });
      get().addToast('Новый код отправлен на вашу почту', 'success');
    } catch (error) {
      set({ error: error.message, isLoading: false });
      get().addToast(error.message, 'error');
      throw error;
    }
  },

  // Step 2: confirm registration by submitting the OTP code
  confirmRegistration: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const result = await api.confirmRegistration({ phone: data.phone, otp: data.otp });
      const tokens = result.data || result;
      if (tokens.accessToken) localStorage.setItem('authToken', tokens.accessToken);
      if (tokens.refreshToken) localStorage.setItem('refreshToken', tokens.refreshToken);
      const payload = JSON.parse(atob(tokens.accessToken.split('.')[1]));
      const user = { id: payload.sub, email: payload.email, role: payload.role, coreId: null };
      localStorage.setItem('userId', user.id);
      set({ user, isLoading: false, loginModalOpen: false, otpPending: null });
      // Fetch core user ID (integer) needed for core API calls — fire-and-forget
      api.getUserByEmail(payload.email).then((coreUser) => {
        if (coreUser && coreUser.id) {
          localStorage.setItem('coreUserId', String(coreUser.id));
          set((state) => ({ user: state.user ? { ...state.user, coreId: coreUser.id } : state.user }));
        }
      }).catch(() => {});
      get().loadProcurements();
      return user;
    } catch (error) {
      set({ error: error.message, isLoading: false });
      get().addToast('Ошибка подтверждения: ' + error.message, 'error');
      throw error;
    }
  },

  logout: async () => {
    try {
      await api.logoutUser();
    } catch (_) {
      // Best-effort: clear local state regardless of server response
    }
    localStorage.removeItem('userId');
    localStorage.removeItem('coreUserId');
    localStorage.removeItem('authToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('wsToken');
    set({
      user: null,
      currentChat: null,
      messages: [],
      loginModalOpen: true,
    });
  },

  // Actions - Theme
  setTheme: (theme) => {
    localStorage.setItem('theme', theme);
    set({ theme });
  },

  toggleTheme: () => {
    const newTheme = get().theme === 'dark' ? 'light' : 'dark';
    get().setTheme(newTheme);
  },

  // Actions - Procurements
  // В useStore.js
  loadProcurements: async (params = { status: 'active' }) => {
    set({ isLoading: true });
    try {
      const response = await api.getProcurements(params);
      const rawProcurements = response.results || response;

      // Обрабатываем сразу в сторе
      const processedProcurements = rawProcurements.length > 0
          ? batchProcessProcurements(rawProcurements)
          : [];

      set({
        procurements: processedProcurements,
        isLoading: false
      });
    } catch (error) {
      set({ error: error.message, isLoading: false });
      get().addToast('Ошибка загрузки закупок', 'error');
    }
  },

  selectProcurement: async (procurementId) => {
    try {
      const procurement = await api.getProcurement(procurementId);
      set({ selectedProcurement: procurement, procurementModalOpen: true });
    } catch (error) {
      get().addToast('Ошибка загрузки закупки', 'error');
    }
  },

  createProcurement: async (data) => {
    set({ isLoading: true });
    try {
      // Ensure we have an integer organizer id before calling the API.
      // After login the coreId is fetched asynchronously; if the user opens
      // the modal very quickly that async call may not have finished yet.
      // Retry once so the race condition is handled transparently.
      let { user } = get();
      if (!user?.coreId && user?.email) {
        try {
          const coreUser = await api.getUserByEmail(user.email);
          if (coreUser?.id) {
            localStorage.setItem('coreUserId', String(coreUser.id));
            set((state) => ({
              user: state.user ? { ...state.user, coreId: coreUser.id } : state.user,
            }));
            user = get().user;
          }
        } catch (_) {
          // Best-effort; will fail below if coreId is still missing
        }
      }
      const organizerId = user?.coreId;
      if (!organizerId || typeof organizerId !== 'number') {
        set({ isLoading: false });
        get().addToast('Не удалось определить организатора. Попробуйте перезайти в систему.', 'error');
        throw new Error('organizer coreId is not available');
      }
      const procurement = await api.createProcurement({ ...data, organizer: organizerId });
      const procurements = [...get().procurements, procurement];
      set({ procurements, isLoading: false, createProcurementModalOpen: false });
      get().addToast('Закупка успешно создана', 'success');
      return procurement;
    } catch (error) {
      set({ isLoading: false });
      if (!error.message?.includes('organizer coreId')) {
        get().addToast('Ошибка создания закупки', 'error');
      }
      throw error;
    }
  },

  joinProcurement: async (procurementId, { amount, quantity, notes }) => {
    const { user } = get();
    if (!user) {
      get().addToast('Необходимо войти в систему', 'error');
      return;
    }
    try {
      await api.joinProcurement(procurementId, {
        user_id: user.coreId || user.id,
        amount,
        quantity: quantity || 1,
        notes: notes || '',
      });
      set({ procurementModalOpen: false });
      get().addToast('Вы присоединились к закупке', 'success');
      get().loadProcurements();
    } catch (error) {
      get().addToast(error.message || 'Ошибка при присоединении', 'error');
    }
  },

  leaveProcurement: async (procurementId) => {
    const { user } = get();
    if (!user) return;
    try {
      await api.leaveProcurement(procurementId, { user_id: user.coreId || user.id });
      get().addToast('Вы вышли из закупки', 'success');
      get().loadProcurements();
    } catch (error) {
      get().addToast(error.message || 'Ошибка при выходе из закупки', 'error');
    }
  },

  stopProcurement: async (procurementId) => {
    try {
      const result = await api.stopProcurement(procurementId);
      get().addToast('Закупка остановлена (стоп-сумма)', 'success');
      get().loadProcurements();
      return result;
    } catch (error) {
      get().addToast(error.message || 'Ошибка при остановке закупки', 'error');
    }
  },

  approveSupplier: async (procurementId, supplierId) => {
    try {
      await api.approveSupplier(procurementId, supplierId);
      get().addToast('Поставщик утверждён', 'success');
      get().loadProcurements();
    } catch (error) {
      get().addToast(error.message || 'Ошибка при утверждении поставщика', 'error');
    }
  },

  closeProcurement: async (procurementId) => {
    try {
      await api.closeProcurement(procurementId);
      get().addToast('Закупка закрыта', 'success');
      set({ procurementModalOpen: false });
      get().loadProcurements();
    } catch (error) {
      get().addToast(error.message || 'Ошибка при закрытии закупки', 'error');
    }
  },

  castVote: async (procurementId, supplierId, comment = '') => {
    const { user } = get();
    if (!user) return;
    try {
      await api.castVote(procurementId, {
        voter_id: user.coreId || user.id,
        supplier_id: supplierId,
        comment,
      });
      get().addToast('Голос учтён', 'success');
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 409) {
          // Stale conflict: reload fresh data and notify user
          get().loadProcurements();
          get().addToast('Данные устарели — загружены актуальные', 'info');
        } else if (error.status === 429) {
          get().addToast(
            `Слишком много запросов. Повторите через ${error.retryAfter ?? 60} сек.`,
            'error',
          );
        } else if (error.status === 403) {
          get().addToast('Нет доступа', 'error');
        } else {
          get().addToast(error.message || 'Ошибка при голосовании', 'error');
        }
      } else {
        get().addToast(error.message || 'Ошибка при голосовании', 'error');
      }
    }
  },

  // Actions - Chat
  setCurrentChat: (chatId) => {
    set({ currentChat: chatId });
    // Clear unread count for this chat
    const unreadCounts = { ...get().unreadCounts };
    delete unreadCounts[chatId];
    set({ unreadCounts });
  },

  loadMessages: async (procurementId) => {
    try {
      const response = await api.getMessages(procurementId);
      const messages = response.results || response;
      set({ messages });
    } catch (error) {
      get().addToast('Ошибка загрузки сообщений', 'error');
    }
  },

  addMessage: (message) => {
    const { currentChat, messages, unreadCounts } = get();
    // Deduplicate: ignore if a message with the same id already exists
    if (message.id && messages.some((m) => m.id === message.id)) return;
    const newMessages = [...messages, message];
    // If message belongs to a different chat, increment unread count
    const msgProcurement = message.procurement || message.procurement_id;
    if (msgProcurement && msgProcurement !== currentChat) {
      const newUnread = { ...unreadCounts, [msgProcurement]: (unreadCounts[msgProcurement] || 0) + 1 };
      set({ messages: newMessages, unreadCounts: newUnread });
    } else {
      set({ messages: newMessages });
    }
  },

  // Update specific fields of a message in place (for edit/delete events).
  // Only re-renders components that depend on the changed message.
  updateMessage: (messageId, patch) => {
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === messageId ? { ...m, ...patch } : m,
      ),
    }));
  },

  // Remove a message from local state (hard-remove, e.g. when admin purges)
  removeMessage: (messageId) => {
    set((state) => ({
      messages: state.messages.filter((m) => m.id !== messageId),
    }));
  },

  sendMessage: async (text, msgType = 'text', mediaUrl = '') => {
    const { user, currentChat } = get();
    if (!user || !currentChat) return;

    const resolvedType = mediaUrl ? msgType || 'file' : 'text';

    // Optimistic UI: add a temporary message immediately
    const tempId = `temp-${Date.now()}`;
    const optimisticMsg = {
      id: tempId,
      procurement: currentChat,
      user: user.coreId || user.id,
      sender_name: `${user.first_name || ''} ${user.last_name || ''}`.trim(),
      text,
      message_type: resolvedType,
      media_url: mediaUrl || undefined,
      created_at: new Date().toISOString(),
      _optimistic: true,
    };
    set({ messages: [...get().messages, optimisticMsg] });

    try {
      const message = await api.sendMessage({
        procurement: currentChat,
        user: user.coreId || user.id,
        text,
        message_type: resolvedType,
        media_url: mediaUrl || undefined,
      });
      // Replace the optimistic message with the real one from the server
      set({ messages: get().messages.map((m) => (m.id === tempId ? message : m)) });
      return message;
    } catch (error) {
      // Remove the optimistic message on failure
      set({ messages: get().messages.filter((m) => m.id !== tempId) });
      get().addToast('Ошибка отправки сообщения', 'error');
    }
  },

  // Actions - Modals
  openLoginModal: () => set({ loginModalOpen: true }),
  closeLoginModal: () => set({ loginModalOpen: false }),
  openProcurementModal: () => set({ procurementModalOpen: true }),
  closeProcurementModal: () => set({ procurementModalOpen: false, selectedProcurement: null }),
  openCreateProcurementModal: () => set({ createProcurementModalOpen: true }),
  closeCreateProcurementModal: () => set({ createProcurementModalOpen: false }),
  openDepositModal: () => set({ depositModalOpen: true }),
  closeDepositModal: () => set({ depositModalOpen: false }),

  // Actions - Sidebar
  toggleSidebar: () => set({ sidebarOpen: !get().sidebarOpen }),
  closeSidebar: () => set({ sidebarOpen: false }),
  setSidebarTab: (tab) => set({ sidebarTab: tab }),

  // Actions - Burger menu
  toggleBurgerMenu: () => set({ burgerMenuOpen: !get().burgerMenuOpen }),
  closeBurgerMenu: () => set({ burgerMenuOpen: false }),

  // Actions - Toast
  addToast: (message, type = 'info') => {
    const id = Date.now();
    const toast = { id, message, type };
    set({ toasts: [...get().toasts, toast] });
    setTimeout(() => {
      get().removeToast(id);
    }, 3000);
  },

  removeToast: (id) => {
    set({ toasts: get().toasts.filter((t) => t.id !== id) });
  },
}));
