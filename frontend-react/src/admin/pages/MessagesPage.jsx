/**
 * Admin Messages Page
 */
import React, { useEffect, useState } from 'react';
import { useAdminStore } from '../store/adminStore';
import { adminApi } from '../services/adminApi';
import AdminLayout from '../components/AdminLayout';
import DataTable from '../components/DataTable';
import SearchFilters from '../components/SearchFilters';

export default function MessagesPage() {
  const { messages, pagination, loadMessages, isLoading, addToast } = useAdminStore();
  const [filters, setFilters] = useState({ search: '' });
  const [page, setPage] = useState(1);
  const [notificationModal, setNotificationModal] = useState(false);
  const [notificationData, setNotificationData] = useState({
    title: '',
    message: '',
    notification_type: 'system',
    user_ids: [],
  });

  useEffect(() => {
    loadMessages({ ...filters, page });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, page]);

  const handleFilterChange = (key, value) => {
    setFilters({ ...filters, [key]: value });
    setPage(1);
  };

  const handleSearch = (search) => {
    setFilters({ ...filters, search });
    setPage(1);
  };

  const handlePageChange = (direction) => {
    if (direction === 'next' && pagination.messages.next) {
      setPage(page + 1);
    } else if (direction === 'prev' && pagination.messages.previous) {
      setPage(page - 1);
    }
  };

  const handleToggleDelete = async (messageId) => {
    try {
      await adminApi.toggleMessageDelete(messageId);
      loadMessages({ ...filters, page });
      addToast('Статус сообщения обновлен', 'success');
    } catch (error) {
      addToast(error.message, 'error');
    }
  };

  const handleSendNotification = async (e) => {
    e.preventDefault();
    try {
      const result = await adminApi.sendBulkNotification(
        notificationData.user_ids,
        notificationData.notification_type,
        notificationData.title,
        notificationData.message
      );
      addToast(`Уведомление отправлено ${result.sent} пользователям`, 'success');
      setNotificationModal(false);
      setNotificationData({
        title: '',
        message: '',
        notification_type: 'system',
        user_ids: [],
      });
    } catch (error) {
      addToast(error.message, 'error');
    }
  };

  const columns = [
    { key: 'id', label: 'ID', width: '60px' },
    {
      key: 'user_name',
      label: 'Пользователь',
    },
    {
      key: 'procurement_title',
      label: 'Закупка',
    },
    {
      key: 'message_type',
      label: 'Тип',
      render: (type) => (
        <span className={`admin-badge admin-badge-${type}`}>{type}</span>
      ),
    },
    {
      key: 'text',
      label: 'Сообщение',
      render: (text) => (
        <div className="admin-text-truncate" style={{ maxWidth: '300px' }}>
          {text}
        </div>
      ),
    },
    {
      key: 'is_deleted',
      label: 'Удалено',
      width: '100px',
      render: (isDeleted, message) => (
        <button
          className={`admin-toggle ${isDeleted ? 'active-danger' : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            handleToggleDelete(message.id);
          }}
        >
          {isDeleted ? '🗑️' : '✓'}
        </button>
      ),
    },
    {
      key: 'created_at',
      label: 'Дата',
      render: (date) => new Date(date).toLocaleString('ru-RU'),
    },
  ];

  return (
    <AdminLayout>
      <div className="admin-page">
        <div className="admin-page-header">
          <h1 className="admin-page-title">Сообщения</h1>
          <button
            className="admin-btn admin-btn-primary"
            onClick={() => setNotificationModal(true)}
          >
            Отправить уведомление
          </button>
        </div>

        <SearchFilters
          filters={[]}
          values={filters}
          onChange={handleFilterChange}
          onSearch={handleSearch}
        />

        <DataTable
          columns={columns}
          data={messages}
          loading={isLoading}
          pagination={pagination.messages}
          onPageChange={handlePageChange}
          emptyMessage="Сообщения не найдены"
        />

        {/* Notification Modal */}
        {notificationModal && (
          <div className="admin-modal-overlay" onClick={() => setNotificationModal(false)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-modal-header">
                <h3>Массовое уведомление</h3>
                <button
                  className="admin-modal-close"
                  onClick={() => setNotificationModal(false)}
                >
                  ×
                </button>
              </div>
              <div className="admin-modal-body">
                <form onSubmit={handleSendNotification}>
                  <div className="admin-form-group">
                    <label>Тип уведомления</label>
                    <select
                      value={notificationData.notification_type}
                      onChange={(e) =>
                        setNotificationData({
                          ...notificationData,
                          notification_type: e.target.value,
                        })
                      }
                    >
                      <option value="system">Системное</option>
                      <option value="procurement">О закупке</option>
                      <option value="payment">О платеже</option>
                      <option value="message">Сообщение</option>
                    </select>
                  </div>
                  <div className="admin-form-group">
                    <label>Заголовок</label>
                    <input
                      type="text"
                      value={notificationData.title}
                      onChange={(e) =>
                        setNotificationData({ ...notificationData, title: e.target.value })
                      }
                      required
                    />
                  </div>
                  <div className="admin-form-group">
                    <label>Сообщение</label>
                    <textarea
                      value={notificationData.message}
                      onChange={(e) =>
                        setNotificationData({ ...notificationData, message: e.target.value })
                      }
                      rows={4}
                      required
                    />
                  </div>
                  <div className="admin-form-info">
                    <p>
                      Уведомление будет отправлено <strong>всем активным пользователям</strong>.
                    </p>
                  </div>
                  <div className="admin-modal-actions">
                    <button type="button" onClick={() => setNotificationModal(false)}>
                      Отмена
                    </button>
                    <button type="submit" className="admin-btn-primary">
                      Отправить
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
