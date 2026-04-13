/**
 * Activity Log Page
 * Shows recent platform activity in a unified timeline view
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useAdminStore } from '../store/adminStore';
import { adminApi } from '../services/adminApi';
import AdminLayout from '../components/AdminLayout';

function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });
}

const EVENT_CONFIG = {
  user: { icon: '👤', color: '#2563eb', label: 'Регистрация' },
  payment: { icon: '💳', color: '#d97706', label: 'Платёж' },
  procurement: { icon: '🛒', color: '#16a34a', label: 'Закупка' },
  message: { icon: '💬', color: '#0891b2', label: 'Сообщение' },
  notification: { icon: '🔔', color: '#8b5cf6', label: 'Уведомление' },
  transaction: { icon: '💰', color: '#f59e0b', label: 'Транзакция' },
};

export default function ActivityLogPage() {
  const { addToast } = useAdminStore();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  const loadActivity = useCallback(async () => {
    setLoading(true);
    try {
      const [usersRes, paymentsRes, transactionsRes, messagesRes, notificationsRes] =
        await Promise.allSettled([
          adminApi.getUsers({ page_size: 20, ordering: '-created_at' }),
          adminApi.getPayments({ page_size: 20 }),
          adminApi.getTransactions({ page_size: 20 }),
          adminApi.getMessages({ page_size: 20 }),
          adminApi.getNotifications({ page_size: 20 }),
        ]).then(results => results.map(r => r.status === 'fulfilled' ? r.value : { results: [] }));

      const allEvents = [];

      // Users
      const users = usersRes.results || usersRes;
      if (Array.isArray(users)) {
        users.forEach((u) => {
          allEvents.push({
            type: 'user',
            date: u.created_at,
            title: `${u.first_name || ''} ${u.last_name || ''}`.trim() || `Пользователь #${u.id}`,
            detail: `Платформа: ${u.platform}, роль: ${u.role || 'buyer'}`,
            id: `user-${u.id}`,
          });
        });
      }

      // Payments
      const payments = paymentsRes.results || paymentsRes;
      if (Array.isArray(payments)) {
        payments.forEach((p) => {
          allEvents.push({
            type: 'payment',
            date: p.created_at,
            title: `${p.payment_type}: ${p.amount} ₽`,
            detail: `Статус: ${p.status}, ${p.user_name || 'Пользователь #' + p.user}`,
            id: `payment-${p.id}`,
          });
        });
      }

      // Transactions
      const transactions = transactionsRes.results || transactionsRes;
      if (Array.isArray(transactions)) {
        transactions.forEach((t) => {
          allEvents.push({
            type: 'transaction',
            date: t.created_at,
            title: `${t.transaction_type}: ${t.amount} ₽`,
            detail: t.description || (t.user_name || ''),
            id: `tx-${t.id}`,
          });
        });
      }

      // Messages
      const messages = messagesRes.results || messagesRes;
      if (Array.isArray(messages)) {
        messages.forEach((m) => {
          allEvents.push({
            type: 'message',
            date: m.created_at,
            title: `${m.user_name || 'Пользователь'} в "${m.procurement_title || '?'}"`,
            detail: m.text ? (m.text.length > 80 ? m.text.slice(0, 80) + '...' : m.text) : '(файл)',
            id: `msg-${m.id}`,
          });
        });
      }

      // Notifications
      const notifications = notificationsRes.results || notificationsRes;
      if (Array.isArray(notifications)) {
        notifications.forEach((n) => {
          allEvents.push({
            type: 'notification',
            date: n.created_at,
            title: n.title || 'Уведомление',
            detail: `${n.user_name || ''}: ${n.message || ''}`.slice(0, 100),
            id: `notif-${n.id}`,
          });
        });
      }

      // Sort by date descending
      allEvents.sort((a, b) => new Date(b.date) - new Date(a.date));
      setEvents(allEvents);
    } catch (err) {
      addToast('Ошибка загрузки активности', 'error');
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadActivity();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredEvents = filter === 'all' ? events : events.filter((e) => e.type === filter);

  // Group events by date
  const grouped = {};
  filteredEvents.forEach((e) => {
    const day = e.date ? e.date.slice(0, 10) : 'unknown';
    if (!grouped[day]) grouped[day] = [];
    grouped[day].push(e);
  });

  return (
    <AdminLayout>
      <div className="admin-page">
        <div className="admin-page-header">
          <h1 className="admin-page-title">Журнал активности</h1>
          <button
            className="admin-btn admin-btn-primary"
            onClick={loadActivity}
            disabled={loading}
          >
            Обновить
          </button>
        </div>

        {/* Filter Tabs */}
        <div className="admin-tabs" style={{ marginBottom: '1rem' }}>
          {[
            { key: 'all', label: 'Все' },
            { key: 'user', label: '👤 Пользователи' },
            { key: 'payment', label: '💳 Платежи' },
            { key: 'transaction', label: '💰 Транзакции' },
            { key: 'procurement', label: '🛒 Закупки' },
            { key: 'message', label: '💬 Сообщения' },
            { key: 'notification', label: '🔔 Уведомления' },
          ].map((tab) => (
            <button
              key={tab.key}
              className={`admin-tab${filter === tab.key ? ' active' : ''}`}
              onClick={() => setFilter(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="admin-loading">Загрузка...</div>
        ) : filteredEvents.length === 0 ? (
          <div className="admin-empty">Нет событий</div>
        ) : (
          <div className="admin-activity-timeline">
            {Object.entries(grouped).map(([day, dayEvents]) => (
              <div key={day} className="admin-activity-day">
                <div className="admin-activity-day-header">
                  {formatDate(day)}
                </div>
                {dayEvents.map((event) => {
                  const cfg = EVENT_CONFIG[event.type] || EVENT_CONFIG.user;
                  return (
                    <div key={event.id} className="admin-activity-item">
                      <div
                        className="admin-activity-icon"
                        style={{ background: cfg.color }}
                      >
                        {cfg.icon}
                      </div>
                      <div className="admin-activity-content">
                        <div className="admin-activity-title">
                          <span className="admin-activity-type-badge" style={{ background: cfg.color + '20', color: cfg.color }}>
                            {cfg.label}
                          </span>
                          {event.title}
                        </div>
                        {event.detail && (
                          <div className="admin-activity-detail">{event.detail}</div>
                        )}
                        <div className="admin-activity-time">
                          {formatDateTime(event.date)}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
