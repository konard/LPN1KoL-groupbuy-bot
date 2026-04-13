/**
 * Admin Chat Page
 * Two-way messaging with users via system notifications.
 * Shows admin-sent messages and user's notification history.
 */
import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useAdminStore } from '../store/adminStore';
import { adminApi } from '../services/adminApi';
import AdminLayout from '../components/AdminLayout';

function getInitials(name) {
  if (!name) return '?';
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

function formatTime(dateStr) {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
  });
}

export default function AdminChatPage() {
  const { users, loadUsers, addToast } = useAdminStore();
  const [selectedUser, setSelectedUser] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [userOnlineStatus, setUserOnlineStatus] = useState({});
  const messagesEndRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    loadUsers({ page_size: 100 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadMessages = useCallback(async (userId) => {
    if (!userId) return;
    setLoadingMessages(true);
    try {
      // Load notifications for this user (admin messages appear as system notifications)
      const notifResponse = await adminApi.getNotifications({ user: userId, page_size: 50 });
      const notifications = notifResponse.results || notifResponse;

      // Load user's chat messages
      const msgResponse = await adminApi.getMessages({ user: userId, page_size: 50 });
      const chatMessages = msgResponse.results || msgResponse;

      // Combine notifications and messages into unified timeline
      const combined = [];

      if (Array.isArray(notifications)) {
        notifications.forEach((n) => {
          combined.push({
            id: `notif-${n.id}`,
            type: 'notification',
            text: n.message || n.title || '',
            title: n.title || '',
            isAdmin: n.notification_type === 'admin_message',
            created_at: n.created_at,
            is_read: n.is_read,
          });
        });
      }

      if (Array.isArray(chatMessages)) {
        chatMessages.forEach((m) => {
          combined.push({
            id: `msg-${m.id}`,
            type: 'message',
            text: m.text || '',
            isAdmin: false,
            created_at: m.created_at,
            procurement_title: m.procurement_title,
          });
        });
      }

      // Sort by date ascending (oldest first)
      combined.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
      setMessages(combined);
    } catch (err) {
      addToast('Ошибка загрузки сообщений', 'error');
    } finally {
      setLoadingMessages(false);
    }
  }, [addToast]);

  const loadMessagesRef = useRef(loadMessages);
  loadMessagesRef.current = loadMessages;

  useEffect(() => {
    if (!selectedUser) return;
    let cancelled = false;
    const userId = selectedUser.id;

    const load = () => {
      if (!cancelled) loadMessagesRef.current(userId);
    };

    load();

    // Poll for new messages every 30 seconds, only when the tab is visible
    const POLL_INTERVAL = 30_000;

    const startPolling = () => {
      if (!pollRef.current) {
        pollRef.current = setInterval(() => {
          if (!document.hidden) {
            load();
          }
        }, POLL_INTERVAL);
      }
    };

    const stopPolling = () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        load();
        startPolling();
      }
    };

    startPolling();
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      cancelled = true;
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [selectedUser]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSelectUser = (user) => {
    setSelectedUser(user);
    setMessages([]);
    setInputText('');
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!inputText.trim() || !selectedUser || sending) return;
    setSending(true);
    try {
      await adminApi.sendAdminMessage(selectedUser.id, inputText.trim());
      setInputText('');
      await loadMessages(selectedUser.id);
      addToast('Сообщение отправлено', 'success');
    } catch (err) {
      addToast('Ошибка отправки сообщения', 'error');
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  const filteredUsers = users.filter((u) => {
    const q = searchQuery.toLowerCase();
    const name = `${u.first_name || ''} ${u.last_name || ''}`.toLowerCase();
    const email = (u.email || '').toLowerCase();
    const platform = (u.platform || '').toLowerCase();
    return name.includes(q) || email.includes(q) || platform.includes(q);
  });

  const getUserName = (user) =>
    user.first_name || user.last_name
      ? `${user.first_name || ''} ${user.last_name || ''}`.trim()
      : user.email || `Пользователь #${user.id}`;

  // Group messages by date for display
  let lastDate = '';

  return (
    <AdminLayout>
      <div className="admin-page">
        <div className="admin-page-header">
          <h1 className="admin-page-title">Чат с пользователями</h1>
        </div>

        <div className="admin-chat-layout">
          {/* User List */}
          <div className="admin-chat-users">
            <div className="admin-chat-users-header">
              <input
                type="text"
                placeholder="Поиск по имени, email, платформе..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="admin-search-input"
                style={{ width: '100%', marginTop: '0.5rem' }}
              />
            </div>
            {filteredUsers.length === 0 ? (
              <div style={{ padding: '1rem', color: 'var(--admin-text-muted)', fontSize: '0.875rem' }}>
                Пользователи не найдены
              </div>
            ) : (
              filteredUsers.map((user) => (
                <div
                  key={user.id}
                  className={`admin-chat-user-item${selectedUser?.id === user.id ? ' active' : ''}`}
                  onClick={() => handleSelectUser(user)}
                >
                  <div className="admin-chat-avatar">
                    {getInitials(getUserName(user))}
                  </div>
                  <div className="admin-chat-user-info">
                    <div className="admin-chat-user-name">
                      {getUserName(user)}
                    </div>
                    <div className="admin-chat-user-role">
                      {user.platform && <span style={{
                        display: 'inline-block',
                        padding: '0 0.375rem',
                        borderRadius: '0.25rem',
                        fontSize: '0.6875rem',
                        background: 'rgba(37, 99, 235, 0.1)',
                        color: 'var(--admin-primary)',
                        marginRight: '0.375rem',
                      }}>{user.platform}</span>}
                      {user.role || 'user'}
                      {user.is_verified && <span title="Верифицирован" style={{ marginLeft: '0.25rem' }}>&#10003;</span>}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Chat Window */}
          <div className="admin-chat-window">
            {!selectedUser ? (
              <div className="admin-chat-empty">
                Выберите пользователя, чтобы начать переписку
              </div>
            ) : (
              <>
                <div className="admin-chat-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div className="admin-chat-avatar" style={{ width: 32, height: 32, fontSize: '0.75rem' }}>
                      {getInitials(getUserName(selectedUser))}
                    </div>
                    <div>
                      {getUserName(selectedUser)}
                      <span style={{ fontWeight: 400, color: 'var(--admin-text-muted)', fontSize: '0.8125rem', marginLeft: '0.5rem' }}>
                        {selectedUser.platform} | {selectedUser.role}
                        {selectedUser.balance !== undefined && ` | Баланс: ${selectedUser.balance} ₽`}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="admin-chat-messages">
                  {loadingMessages && messages.length === 0 ? (
                    <div style={{ color: 'var(--admin-text-muted)', textAlign: 'center', padding: '2rem' }}>
                      Загрузка...
                    </div>
                  ) : messages.length === 0 ? (
                    <div style={{ color: 'var(--admin-text-muted)', textAlign: 'center', padding: '2rem' }}>
                      Нет сообщений. Напишите пользователю.
                    </div>
                  ) : (
                    messages.map((msg) => {
                      const msgDate = msg.created_at ? msg.created_at.slice(0, 10) : '';
                      let showDateSeparator = false;
                      if (msgDate !== lastDate) {
                        lastDate = msgDate;
                        showDateSeparator = true;
                      }

                      return (
                        <React.Fragment key={msg.id}>
                          {showDateSeparator && (
                            <div style={{
                              textAlign: 'center',
                              color: 'var(--admin-text-muted)',
                              fontSize: '0.75rem',
                              margin: '0.5rem 0',
                            }}>
                              {formatDate(msg.created_at)}
                            </div>
                          )}
                          <div className={`admin-chat-msg ${msg.isAdmin ? 'sent' : 'received'}`}>
                            {msg.type === 'notification' && msg.title && (
                              <div style={{ fontWeight: 600, fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                                {msg.title}
                              </div>
                            )}
                            {msg.text}
                            {msg.procurement_title && (
                              <div style={{ fontSize: '0.7rem', opacity: 0.7, marginTop: '0.25rem' }}>
                                в "{msg.procurement_title}"
                              </div>
                            )}
                            <div className="admin-chat-msg-meta">
                              {msg.type === 'notification' && !msg.isAdmin && (
                                <span style={{ marginRight: '0.5rem' }}>
                                  {msg.is_read ? '(прочитано)' : '(не прочитано)'}
                                </span>
                              )}
                              {formatTime(msg.created_at)}
                            </div>
                          </div>
                        </React.Fragment>
                      );
                    })
                  )}
                  <div ref={messagesEndRef} />
                </div>

                <form className="admin-chat-input-area" onSubmit={handleSend}>
                  <textarea
                    className="admin-chat-input"
                    placeholder="Напишите сообщение..."
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    rows={1}
                  />
                  <button
                    type="submit"
                    className="admin-chat-send-btn"
                    disabled={!inputText.trim() || sending}
                    title="Отправить"
                  >
                    {sending ? '...' : '➤'}
                  </button>
                </form>
              </>
            )}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
