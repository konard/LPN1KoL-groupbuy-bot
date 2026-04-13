/**
 * GroupBuy Bot - Main Application JavaScript
 * Telegram-like interface for group purchasing platform
 */

// Configuration
const CONFIG = {
    API_URL: window.API_URL || '/api',
    WS_URL: window.WS_URL || `ws://${window.location.host}/ws`,
    POLLING_INTERVAL: 5000,
    MAX_MESSAGE_LENGTH: 4096,
    PAGE_SIZE: 20
};

// Application State
const AppState = {
    user: null,
    currentChat: null,
    procurements: [],
    messages: [],
    isLoading: false,
    wsConnection: null,
    unreadCounts: {}
};

// Utility Functions
const Utils = {
    // Format date to Telegram-like format
    formatTime(date) {
        const d = new Date(date);
        const now = new Date();
        const isToday = d.toDateString() === now.toDateString();

        if (isToday) {
            return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
        }

        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        if (d.toDateString() === yesterday.toDateString()) {
            return 'Вчера';
        }

        return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
    },

    // Format currency
    formatCurrency(amount) {
        return new Intl.NumberFormat('ru-RU', {
            style: 'currency',
            currency: 'RUB',
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
        }).format(amount);
    },

    // Get initials from name
    getInitials(firstName, lastName = '') {
        const first = firstName ? firstName.charAt(0).toUpperCase() : '';
        const last = lastName ? lastName.charAt(0).toUpperCase() : '';
        return first + last || '?';
    },

    // Generate avatar background color based on name
    getAvatarColor(name) {
        const colors = [
            '#e17076', '#faa774', '#a695e7', '#7bc862',
            '#6ec9cb', '#65aadd', '#ee7aae', '#f5a623'
        ];
        let hash = 0;
        for (let i = 0; i < name.length; i++) {
            hash = name.charCodeAt(i) + ((hash << 5) - hash);
        }
        return colors[Math.abs(hash) % colors.length];
    },

    // Escape HTML to prevent XSS
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    // Debounce function
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Show toast notification
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type} animate-slideIn`;
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
};

// API Client
const API = {
    async request(endpoint, options = {}) {
        const url = `${CONFIG.API_URL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        // Add auth token if available
        const token = localStorage.getItem('authToken');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    // User endpoints
    async getUser(userId) {
        return this.request(`/users/${userId}/`);
    },

    async getUserByPlatform(platform, platformUserId) {
        return this.request(`/users/by_platform/?platform=${platform}&platform_user_id=${platformUserId}`);
    },

    async registerUser(data) {
        return this.request('/users/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async updateUser(userId, data) {
        return this.request(`/users/${userId}/`, {
            method: 'PATCH',
            body: JSON.stringify(data)
        });
    },

    async getUserBalance(userId) {
        return this.request(`/users/${userId}/balance/`);
    },

    // Procurement endpoints
    async getProcurements(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/procurements/?${query}`);
    },

    async getProcurement(id) {
        return this.request(`/procurements/${id}/`);
    },

    async createProcurement(data) {
        return this.request('/procurements/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async joinProcurement(id, data) {
        return this.request(`/procurements/${id}/join/`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async leaveProcurement(id) {
        return this.request(`/procurements/${id}/leave/`, {
            method: 'POST'
        });
    },

    async getUserProcurements(userId) {
        return this.request(`/procurements/user/${userId}/`);
    },

    async getCategories() {
        return this.request('/procurements/categories/');
    },

    // Chat endpoints
    async getMessages(procurementId, params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/chat/messages/?procurement=${procurementId}&${query}`);
    },

    async sendMessage(data) {
        return this.request('/chat/messages/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async getNotifications(userId) {
        return this.request(`/chat/notifications/?user=${userId}`);
    },

    // Payment endpoints
    async createPayment(data) {
        return this.request('/payments/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async getPaymentStatus(paymentId) {
        return this.request(`/payments/${paymentId}/status/`);
    }
};

// WebSocket Manager
const WebSocketManager = {
    connection: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,

    connect(procurementId) {
        const token = localStorage.getItem('authToken');
        const wsUrl = `${CONFIG.WS_URL}/procurement/${procurementId}/?token=${token}`;

        this.connection = new WebSocket(wsUrl);

        this.connection.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
        };

        this.connection.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        this.connection.onclose = () => {
            console.log('WebSocket disconnected');
            this.attemptReconnect(procurementId);
        };

        this.connection.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    },

    disconnect() {
        if (this.connection) {
            this.connection.close();
            this.connection = null;
        }
    },

    send(data) {
        if (this.connection && this.connection.readyState === WebSocket.OPEN) {
            this.connection.send(JSON.stringify(data));
        }
    },

    handleMessage(data) {
        switch (data.type) {
            case 'message':
                UI.addMessage(data.message);
                break;
            case 'typing':
                UI.showTypingIndicator(data.user);
                break;
            case 'user_joined':
                UI.showSystemMessage(`${data.user.first_name} присоединился к чату`);
                break;
            case 'user_left':
                UI.showSystemMessage(`${data.user.first_name} покинул чат`);
                break;
        }
    },

    attemptReconnect(procurementId) {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => this.connect(procurementId), 2000 * this.reconnectAttempts);
        }
    },

    sendTyping() {
        this.send({ type: 'typing' });
    }
};

// UI Components
const UI = {
    // Initialize UI
    init() {
        this.bindEvents();
        this.loadTheme();
    },

    // Bind event handlers
    bindEvents() {
        // Search
        const searchInput = document.querySelector('.search-input');
        if (searchInput) {
            searchInput.addEventListener('input', Utils.debounce((e) => {
                this.handleSearch(e.target.value);
            }, 300));
        }

        // Message input
        const messageInput = document.querySelector('.message-input');
        if (messageInput) {
            messageInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });

            messageInput.addEventListener('input', () => {
                this.autoResizeTextarea(messageInput);
                WebSocketManager.sendTyping();
            });
        }

        // Send button
        const sendBtn = document.querySelector('.send-button');
        if (sendBtn) {
            sendBtn.addEventListener('click', () => this.sendMessage());
        }

        // Mobile sidebar toggle
        const menuBtn = document.querySelector('.menu-toggle');
        if (menuBtn) {
            menuBtn.addEventListener('click', () => {
                document.querySelector('.sidebar').classList.toggle('open');
            });
        }

        // Modal close handlers
        document.querySelectorAll('.modal-close, .modal-overlay').forEach(el => {
            el.addEventListener('click', (e) => {
                if (e.target === el) {
                    this.closeModal();
                }
            });
        });

        // Theme toggle
        const themeToggle = document.querySelector('.theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }
    },

    // Load theme from storage
    loadTheme() {
        const theme = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', theme);
    },

    // Toggle theme
    toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme');
        const newTheme = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    },

    // Render chat list
    renderChatList(procurements) {
        const container = document.querySelector('.chat-list');
        if (!container) return;

        container.innerHTML = procurements.map(p => `
            <div class="chat-item ${AppState.currentChat === p.id ? 'active' : ''}"
                 data-procurement-id="${p.id}">
                <div class="chat-avatar" style="background-color: ${Utils.getAvatarColor(p.title)}">
                    ${Utils.getInitials(p.title)}
                </div>
                <div class="chat-info">
                    <div class="chat-header">
                        <span class="chat-title">${Utils.escapeHtml(p.title)}</span>
                        <span class="chat-time">${Utils.formatTime(p.updated_at)}</span>
                    </div>
                    <div class="chat-message">
                        ${p.participant_count} участников • ${p.progress}%
                    </div>
                </div>
                ${AppState.unreadCounts[p.id] ? `
                    <div class="chat-badge">${AppState.unreadCounts[p.id]}</div>
                ` : ''}
            </div>
        `).join('');

        // Bind click handlers
        container.querySelectorAll('.chat-item').forEach(item => {
            item.addEventListener('click', () => {
                const id = parseInt(item.dataset.procurementId);
                this.openChat(id);
            });
        });
    },

    // Render procurement slider
    renderProcurementSlider(procurements) {
        const container = document.querySelector('.slider-container');
        if (!container) return;

        container.innerHTML = procurements.map(p => `
            <div class="procurement-card" data-procurement-id="${p.id}">
                <div class="procurement-title">${Utils.escapeHtml(p.title)}</div>
                <div class="procurement-info">${Utils.escapeHtml(p.city)}</div>
                <div class="procurement-progress">
                    <div class="procurement-progress-bar" style="width: ${p.progress}%"></div>
                </div>
                <div class="procurement-stats">
                    <span>${Utils.formatCurrency(p.current_amount)} / ${Utils.formatCurrency(p.target_amount)}</span>
                    <span>${p.days_left} дн.</span>
                </div>
            </div>
        `).join('');

        // Bind click handlers
        container.querySelectorAll('.procurement-card').forEach(card => {
            card.addEventListener('click', () => {
                const id = parseInt(card.dataset.procurementId);
                this.openProcurementDetails(id);
            });
        });
    },

    // Render messages
    renderMessages(messages) {
        const container = document.querySelector('.message-area');
        if (!container) return;

        let lastDate = null;
        let html = '';

        messages.forEach(msg => {
            const msgDate = new Date(msg.created_at).toDateString();
            if (msgDate !== lastDate) {
                html += `
                    <div class="message-date-divider">
                        <span>${this.formatMessageDate(msg.created_at)}</span>
                    </div>
                `;
                lastDate = msgDate;
            }

            const isOwn = AppState.user && msg.user && msg.user.id === AppState.user.id;

            if (msg.message_type === 'system') {
                html += `
                    <div class="message system">
                        ${Utils.escapeHtml(msg.text)}
                    </div>
                `;
            } else {
                html += `
                    <div class="message ${isOwn ? 'outgoing' : 'incoming'}" data-message-id="${msg.id}">
                        ${!isOwn && msg.user ? `<div class="message-sender">${Utils.escapeHtml(msg.user.first_name)}</div>` : ''}
                        <div class="message-text">${this.formatMessageText(msg.text)}</div>
                        <div class="message-time">${Utils.formatTime(msg.created_at)}</div>
                    </div>
                `;
            }
        });

        container.innerHTML = html;
        this.scrollToBottom();
    },

    // Add single message to chat
    addMessage(message) {
        const container = document.querySelector('.message-area');
        if (!container) return;

        const isOwn = AppState.user && message.user && message.user.id === AppState.user.id;
        const messageHtml = `
            <div class="message ${isOwn ? 'outgoing' : 'incoming'} animate-slideIn" data-message-id="${message.id}">
                ${!isOwn && message.user ? `<div class="message-sender">${Utils.escapeHtml(message.user.first_name)}</div>` : ''}
                <div class="message-text">${this.formatMessageText(message.text)}</div>
                <div class="message-time">${Utils.formatTime(message.created_at)}</div>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', messageHtml);
        this.scrollToBottom();
    },

    // Show system message
    showSystemMessage(text) {
        const container = document.querySelector('.message-area');
        if (!container) return;

        container.insertAdjacentHTML('beforeend', `
            <div class="message system animate-fadeIn">${Utils.escapeHtml(text)}</div>
        `);
        this.scrollToBottom();
    },

    // Show typing indicator
    showTypingIndicator(user) {
        const existing = document.querySelector('.typing-indicator');
        if (existing) existing.remove();

        const container = document.querySelector('.message-area');
        if (!container) return;

        container.insertAdjacentHTML('beforeend', `
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `);

        setTimeout(() => {
            const indicator = document.querySelector('.typing-indicator');
            if (indicator) indicator.remove();
        }, 3000);
    },

    // Format message text (links, mentions, etc.)
    formatMessageText(text) {
        // Escape HTML first
        let formatted = Utils.escapeHtml(text);

        // Convert URLs to links
        formatted = formatted.replace(
            /(https?:\/\/[^\s]+)/g,
            '<a href="$1" target="_blank" rel="noopener">$1</a>'
        );

        // Convert line breaks
        formatted = formatted.replace(/\n/g, '<br>');

        return formatted;
    },

    // Format message date for dividers
    formatMessageDate(date) {
        const d = new Date(date);
        const now = new Date();
        const diff = now - d;

        if (diff < 86400000) return 'Сегодня';
        if (diff < 172800000) return 'Вчера';

        return d.toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'long',
            year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
        });
    },

    // Send message
    async sendMessage() {
        const input = document.querySelector('.message-input');
        if (!input) return;

        const text = input.value.trim();
        if (!text || text.length > CONFIG.MAX_MESSAGE_LENGTH) return;

        try {
            const message = await API.sendMessage({
                procurement: AppState.currentChat,
                user: AppState.user.id,
                text: text,
                message_type: 'text'
            });

            // Send via WebSocket for real-time delivery
            WebSocketManager.send({
                type: 'message',
                message: message
            });

            input.value = '';
            this.autoResizeTextarea(input);
        } catch (error) {
            Utils.showToast('Ошибка отправки сообщения', 'error');
        }
    },

    // Open chat
    async openChat(procurementId) {
        AppState.currentChat = procurementId;

        // Update UI
        document.querySelectorAll('.chat-item').forEach(item => {
            item.classList.toggle('active', parseInt(item.dataset.procurementId) === procurementId);
        });

        // Close mobile sidebar
        document.querySelector('.sidebar')?.classList.remove('open');

        // Load messages
        try {
            const messages = await API.getMessages(procurementId);
            this.renderMessages(messages.results || messages);

            // Connect WebSocket
            WebSocketManager.disconnect();
            WebSocketManager.connect(procurementId);

            // Clear unread count
            delete AppState.unreadCounts[procurementId];
        } catch (error) {
            Utils.showToast('Ошибка загрузки сообщений', 'error');
        }
    },

    // Open procurement details modal
    async openProcurementDetails(procurementId) {
        try {
            const procurement = await API.getProcurement(procurementId);
            this.showProcurementModal(procurement);
        } catch (error) {
            Utils.showToast('Ошибка загрузки закупки', 'error');
        }
    },

    // Show procurement details modal
    showProcurementModal(procurement) {
        const modal = document.querySelector('#procurement-modal');
        if (!modal) return;

        modal.querySelector('.modal-title').textContent = procurement.title;
        modal.querySelector('.modal-body').innerHTML = `
            <div class="procurement-details">
                <div class="form-group">
                    <label class="form-label">Описание</label>
                    <p>${Utils.escapeHtml(procurement.description)}</p>
                </div>
                <div class="form-group">
                    <label class="form-label">Город</label>
                    <p>${Utils.escapeHtml(procurement.city)}</p>
                </div>
                <div class="form-group">
                    <label class="form-label">Прогресс</label>
                    <div class="procurement-progress mt-sm">
                        <div class="procurement-progress-bar" style="width: ${procurement.progress}%"></div>
                    </div>
                    <p class="mt-sm text-secondary">
                        ${Utils.formatCurrency(procurement.current_amount)} из ${Utils.formatCurrency(procurement.target_amount)}
                    </p>
                </div>
                <div class="form-group">
                    <label class="form-label">Участники</label>
                    <p>${procurement.participant_count} человек</p>
                </div>
                <div class="form-group">
                    <label class="form-label">Статус</label>
                    <span class="status-badge status-${procurement.status}">${this.getStatusText(procurement.status)}</span>
                </div>
            </div>
        `;

        this.openModal('procurement-modal');
    },

    // Get status display text
    getStatusText(status) {
        const statuses = {
            draft: 'Черновик',
            active: 'Активная',
            stopped: 'Остановлена',
            payment: 'Оплата',
            completed: 'Завершена',
            cancelled: 'Отменена'
        };
        return statuses[status] || status;
    },

    // Render user cabinet
    renderCabinet(user) {
        const container = document.querySelector('.cabinet');
        if (!container) return;

        container.innerHTML = `
            <div class="cabinet-header">
                <div class="cabinet-avatar" style="background-color: ${Utils.getAvatarColor(user.first_name)}">
                    ${Utils.getInitials(user.first_name, user.last_name)}
                </div>
                <div class="cabinet-info">
                    <h2>${Utils.escapeHtml(user.first_name)} ${Utils.escapeHtml(user.last_name || '')}</h2>
                    <div class="cabinet-role">${this.getRoleText(user.role)}</div>
                </div>
            </div>

            <div class="cabinet-balance">
                <div class="balance-label">Баланс</div>
                <div class="balance-amount">${Utils.formatCurrency(user.balance)}</div>
                <div class="balance-actions">
                    <button class="btn btn-primary btn-round" onclick="UI.openDepositModal()">
                        Пополнить
                    </button>
                    <button class="btn btn-outline btn-round" onclick="UI.openWithdrawModal()">
                        Вывести
                    </button>
                </div>
            </div>

            <div class="cabinet-menu">
                ${this.getCabinetMenuItems(user.role)}
            </div>
        `;
    },

    // Get role display text
    getRoleText(role) {
        const roles = {
            buyer: 'Покупатель',
            organizer: 'Организатор',
            supplier: 'Поставщик'
        };
        return roles[role] || role;
    },

    // Get cabinet menu items based on role
    getCabinetMenuItems(role) {
        const commonItems = `
            <div class="cabinet-menu-item" onclick="UI.navigateTo('my-requests')">
                <svg class="cabinet-menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                <span class="cabinet-menu-text">Мои запросы</span>
            </div>
            <div class="cabinet-menu-item" onclick="UI.navigateTo('my-procurements')">
                <svg class="cabinet-menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
                    <line x1="3" y1="6" x2="21" y2="6"/>
                </svg>
                <span class="cabinet-menu-text">Мои закупки</span>
            </div>
            <div class="cabinet-menu-item" onclick="UI.navigateTo('messages')">
                <svg class="cabinet-menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                    <polyline points="22,6 12,13 2,6"/>
                </svg>
                <span class="cabinet-menu-text">Сообщения</span>
            </div>
            <div class="cabinet-menu-item" onclick="UI.navigateTo('history')">
                <svg class="cabinet-menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12 6 12 12 16 14"/>
                </svg>
                <span class="cabinet-menu-text">История закупок</span>
            </div>
        `;

        let roleItems = '';

        if (role === 'organizer') {
            roleItems = `
                <div class="cabinet-menu-item" onclick="UI.openCreateProcurementModal()">
                    <svg class="cabinet-menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="16"/>
                        <line x1="8" y1="12" x2="16" y2="12"/>
                    </svg>
                    <span class="cabinet-menu-text">Создать закупку</span>
                </div>
            `;
        }

        if (role === 'supplier') {
            roleItems = `
                <div class="cabinet-menu-item" onclick="UI.navigateTo('company-profile')">
                    <svg class="cabinet-menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                    </svg>
                    <span class="cabinet-menu-text">Карточка компании</span>
                </div>
                <div class="cabinet-menu-item" onclick="UI.navigateTo('price-list')">
                    <svg class="cabinet-menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <span class="cabinet-menu-text">Прайс-листы</span>
                </div>
            `;
        }

        return roleItems + commonItems;
    },

    // Handle search
    handleSearch(query) {
        if (!query) {
            this.renderChatList(AppState.procurements);
            return;
        }

        const filtered = AppState.procurements.filter(p =>
            p.title.toLowerCase().includes(query.toLowerCase()) ||
            p.city.toLowerCase().includes(query.toLowerCase())
        );

        this.renderChatList(filtered);
    },

    // Auto resize textarea
    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    },

    // Scroll to bottom of message area
    scrollToBottom() {
        const container = document.querySelector('.message-area');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    },

    // Open modal
    openModal(modalId) {
        const modal = document.querySelector(`#${modalId}`);
        if (modal) {
            modal.closest('.modal-overlay')?.classList.add('active');
        }
    },

    // Close modal
    closeModal() {
        document.querySelectorAll('.modal-overlay.active').forEach(el => {
            el.classList.remove('active');
        });
    },

    // Navigate to section
    navigateTo(section) {
        console.log('Navigate to:', section);
        // Implementation depends on routing strategy
    },

    // Open deposit modal
    openDepositModal() {
        const modal = document.querySelector('#deposit-modal');
        if (modal) {
            this.openModal('deposit-modal');
        }
    },

    // Open withdraw modal
    openWithdrawModal() {
        const modal = document.querySelector('#withdraw-modal');
        if (modal) {
            this.openModal('withdraw-modal');
        }
    },

    // Open create procurement modal
    openCreateProcurementModal() {
        const modal = document.querySelector('#create-procurement-modal');
        if (modal) {
            this.openModal('create-procurement-modal');
        }
    }
};

// Application initialization
const App = {
    async init() {
        UI.init();

        // Check for existing session
        const userId = localStorage.getItem('userId');
        if (userId) {
            try {
                AppState.user = await API.getUser(userId);
                this.loadMainContent();
            } catch (error) {
                this.showLogin();
            }
        } else {
            this.showLogin();
        }
    },

    async loadMainContent() {
        // Show main page
        this.showMain();

        // Load procurements
        try {
            const response = await API.getProcurements({ status: 'active' });
            AppState.procurements = response.results || response;
            UI.renderChatList(AppState.procurements);
            UI.renderProcurementSlider(AppState.procurements);
        } catch (error) {
            console.error('Error loading procurements:', error);
        }

        // Load user cabinet
        if (AppState.user) {
            UI.renderCabinet(AppState.user);
        }
    },

    showLogin() {
        // Show the redesigned auth page, hide main app page
        const authPage = document.getElementById('auth-page');
        const mainPage = document.getElementById('main-page');
        if (authPage) authPage.classList.remove('hidden');
        if (mainPage) mainPage.classList.add('hidden');

        // Legacy modal fallback (kept for backward compatibility)
        const modal = document.querySelector('#login-modal');
        if (modal && !authPage) {
            UI.openModal('login-modal');
        }
    },

    showMain() {
        // Show main app page, hide auth page
        const authPage = document.getElementById('auth-page');
        const mainPage = document.getElementById('main-page');
        if (authPage) authPage.classList.add('hidden');
        if (mainPage) mainPage.classList.remove('hidden');
    },

    async register(data) {
        try {
            const user = await API.registerUser({
                ...data,
                platform: 'websocket'
            });

            AppState.user = user;
            localStorage.setItem('userId', user.id);
            UI.closeModal();
            this.showMain();
            this.loadMainContent();
        } catch (error) {
            Utils.showToast('Ошибка регистрации', 'error');
        }
    },

    logout() {
        AppState.user = null;
        AppState.currentChat = null;
        localStorage.removeItem('userId');
        localStorage.removeItem('authToken');
        WebSocketManager.disconnect();
        this.showLogin();
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

// Export for global access
window.App = App;
window.UI = UI;
window.API = API;
window.Utils = Utils;
