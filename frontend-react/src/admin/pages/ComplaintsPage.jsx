/**
 * Admin Complaints Page
 * Arbitration and complaint management
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useAdminStore } from '../store/adminStore';
import AdminLayout from '../components/AdminLayout';
import DataTable from '../components/DataTable';
import SearchFilters from '../components/SearchFilters';
import StatCard from '../components/StatCard';

export default function ComplaintsPage() {
  const { isLoading, addToast } = useAdminStore();

  const [complaints, setComplaints] = useState([]);
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    investigating: 0,
    resolved: 0,
    rejected: 0,
  });
  const [pagination, setPagination] = useState({
    count: 0,
    next: null,
    previous: null,
  });
  const [filters, setFilters] = useState({
    search: '',
    status: '',
    complaint_type: '',
  });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [detailModal, setDetailModal] = useState(null);
  const [resolveModal, setResolveModal] = useState(null);
  const [resolveAction, setResolveAction] = useState('');
  const [resolveComment, setResolveComment] = useState('');

  const getCsrfToken = () =>
    document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/)?.[1] || '';

  const loadComplaints = useCallback(async (/* params = {} */) => {
    setLoading(true);
    // Complaints/arbitration backend is not yet implemented.
    // The /api/admin/complaints/ endpoint does not exist.
    setComplaints([]);
    setPagination({ count: 0, next: null, previous: null });
    setLoading(false);
  }, []);

  const loadStats = useCallback(async () => {
    // Complaints stats endpoint is not yet implemented.
  }, []);

  useEffect(() => {
    loadComplaints({ ...filters, page });
    loadStats();
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
    if (direction === 'next' && pagination.next) {
      setPage(page + 1);
    } else if (direction === 'prev' && pagination.previous) {
      setPage(page - 1);
    }
  };

  const handleViewDetail = async (complaint) => {
    // Complaints detail endpoint is not yet implemented.
    setDetailModal(complaint);
  };

  const handleResolveSubmit = async (e) => {
    e.preventDefault();
    // Complaints resolve endpoint is not yet implemented.
    addToast('Функция в разработке', 'info');
    setResolveModal(null);
    setResolveAction('');
    setResolveComment('');
  };

  const columns = [
    { key: 'id', label: 'ID', width: '60px' },
    {
      key: 'complainant_name',
      label: 'Заявитель',
    },
    {
      key: 'respondent_name',
      label: 'Ответчик',
    },
    {
      key: 'complaint_type',
      label: 'Тип',
      render: (type) => {
        const types = {
          fraud: 'Мошенничество',
          poor_quality: 'Плохое качество',
          offensive: 'Оскорбления',
          other: 'Другое',
        };
        const colors = {
          fraud: 'admin-badge-danger',
          poor_quality: 'admin-badge-warning',
          offensive: 'admin-badge-info',
          other: 'admin-badge-default',
        };
        return (
          <span className={`admin-badge ${colors[type] || ''}`}>
            {types[type] || type}
          </span>
        );
      },
    },
    {
      key: 'subject',
      label: 'Тема',
      render: (subject) => (
        <span title={subject}>
          {subject && subject.length > 40 ? subject.slice(0, 40) + '...' : subject}
        </span>
      ),
    },
    {
      key: 'status',
      label: 'Статус',
      render: (status) => {
        const statuses = {
          pending: 'Ожидает',
          investigating: 'Расследование',
          resolved: 'Решена',
          rejected: 'Отклонена',
        };
        const statusColors = {
          pending: 'pending',
          investigating: 'waiting_for_capture',
          resolved: 'succeeded',
          rejected: 'cancelled',
        };
        return (
          <span className={`admin-badge admin-status-badge admin-status-${statusColors[status] || status}`}>
            {statuses[status] || status}
          </span>
        );
      },
    },
    {
      key: 'created_at',
      label: 'Дата',
      render: (date) => new Date(date).toLocaleDateString('ru-RU'),
    },
    {
      key: 'actions',
      label: 'Действия',
      render: (_, complaint) => (
        <div style={{ display: 'flex', gap: '4px' }}>
          <button
            className="admin-btn admin-btn-sm"
            onClick={(e) => {
              e.stopPropagation();
              handleViewDetail(complaint);
            }}
          >
            Детали
          </button>
          {(complaint.status === 'pending' || complaint.status === 'investigating') && (
            <button
              className="admin-btn admin-btn-sm admin-btn-primary"
              onClick={(e) => {
                e.stopPropagation();
                setResolveModal(complaint);
              }}
            >
              Решить
            </button>
          )}
        </div>
      ),
    },
  ];

  const filterConfig = [
    {
      key: 'status',
      label: 'Статус',
      options: [
        { value: 'pending', label: 'Ожидает' },
        { value: 'investigating', label: 'Расследование' },
        { value: 'resolved', label: 'Решена' },
        { value: 'rejected', label: 'Отклонена' },
      ],
    },
    {
      key: 'complaint_type',
      label: 'Тип',
      options: [
        { value: 'fraud', label: 'Мошенничество' },
        { value: 'poor_quality', label: 'Плохое качество' },
        { value: 'offensive', label: 'Оскорбления' },
        { value: 'other', label: 'Другое' },
      ],
    },
  ];

  return (
    <AdminLayout>
      <div className="admin-page">
        <div className="admin-page-header">
          <h1 className="admin-page-title">Жалобы и арбитраж</h1>
        </div>

        <div className="admin-notice" style={{ background: '#fef9c3', border: '1px solid #fde047', borderRadius: '8px', padding: '12px 16px', marginBottom: '16px', color: '#713f12' }}>
          Раздел в разработке. Функциональность жалоб и арбитража будет доступна в следующей версии.
        </div>

        <div className="admin-stats-grid">
          <StatCard
            label="Всего жалоб"
            value={stats.total}
            icon="📋"
            color="primary"
          />
          <StatCard
            label="Ожидают рассмотрения"
            value={stats.pending}
            icon="⏳"
            color="warning"
          />
          <StatCard
            label="В расследовании"
            value={stats.investigating}
            icon="🔍"
            color="info"
          />
          <StatCard
            label="Решены"
            value={stats.resolved}
            icon="✅"
            color="success"
          />
        </div>

        <SearchFilters
          filters={filterConfig}
          values={filters}
          onChange={handleFilterChange}
          onSearch={handleSearch}
        />

        <DataTable
          columns={columns}
          data={complaints}
          loading={loading || isLoading}
          pagination={pagination}
          onPageChange={handlePageChange}
          onRowClick={handleViewDetail}
          emptyMessage="Жалобы не найдены"
        />

        {/* Detail Modal */}
        {detailModal && (
          <div className="admin-modal-overlay" onClick={() => setDetailModal(null)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
              <div className="admin-modal-header">
                <h3>Жалоба #{detailModal.id}</h3>
                <button
                  className="admin-modal-close"
                  onClick={() => setDetailModal(null)}
                >
                  ×
                </button>
              </div>
              <div className="admin-modal-body">
                <div className="admin-detail-grid">
                  <div className="admin-detail-item">
                    <label>Заявитель</label>
                    <span>{detailModal.complainant_name}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Ответчик</label>
                    <span>{detailModal.respondent_name}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Тип</label>
                    <span>{detailModal.complaint_type}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Статус</label>
                    <span className={`admin-badge admin-status-badge admin-status-${detailModal.status}`}>
                      {detailModal.status}
                    </span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Дата создания</label>
                    <span>{new Date(detailModal.created_at).toLocaleString('ru-RU')}</span>
                  </div>
                  {detailModal.related_procurement && (
                    <div className="admin-detail-item">
                      <label>Связанная закупка</label>
                      <span>#{detailModal.related_procurement}</span>
                    </div>
                  )}
                </div>

                <div className="admin-detail-description">
                  <label>Тема</label>
                  <p><strong>{detailModal.subject}</strong></p>
                </div>

                <div className="admin-detail-description">
                  <label>Описание</label>
                  <p>{detailModal.description}</p>
                </div>

                {detailModal.evidence && detailModal.evidence.length > 0 && (
                  <div className="admin-detail-description">
                    <label>Доказательства</label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {detailModal.evidence.map((item, i) => (
                        <div key={i} style={{ padding: '8px', background: '#f8fafc', borderRadius: '4px' }}>
                          {item.type === 'image' ? (
                            <a href={item.url} target="_blank" rel="noopener noreferrer">
                              Изображение #{i + 1}
                            </a>
                          ) : item.type === 'text' ? (
                            <p style={{ margin: 0 }}>{item.content}</p>
                          ) : (
                            <a href={item.url} target="_blank" rel="noopener noreferrer">
                              Файл #{i + 1}
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {detailModal.chat_history && detailModal.chat_history.length > 0 && (
                  <div className="admin-detail-description">
                    <label>История переписки</label>
                    <div style={{ maxHeight: '200px', overflowY: 'auto', background: '#f8fafc', borderRadius: '4px', padding: '8px' }}>
                      {detailModal.chat_history.map((msg, i) => (
                        <div key={i} style={{ padding: '4px 0', borderBottom: '1px solid #e2e8f0' }}>
                          <strong>{msg.sender_name}:</strong> {msg.text}
                          <span className="admin-text-muted" style={{ fontSize: '11px', marginLeft: '8px' }}>
                            {new Date(msg.created_at).toLocaleString('ru-RU')}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {(detailModal.status === 'pending' || detailModal.status === 'investigating') && (
                  <div style={{ marginTop: '16px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <button
                      className="admin-btn admin-btn-primary"
                      onClick={() => setResolveModal(detailModal)}
                    >
                      Вынести решение
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Resolve Modal */}
        {resolveModal && (
          <div className="admin-modal-overlay" onClick={() => setResolveModal(null)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-modal-header">
                <h3>Решение по жалобе #{resolveModal.id}</h3>
                <button
                  className="admin-modal-close"
                  onClick={() => setResolveModal(null)}
                >
                  ×
                </button>
              </div>
              <div className="admin-modal-body">
                <form onSubmit={handleResolveSubmit}>
                  <div className="admin-form-group">
                    <label>Действие</label>
                    <select
                      value={resolveAction}
                      onChange={(e) => setResolveAction(e.target.value)}
                      required
                      style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
                    >
                      <option value="">Выберите действие</option>
                      <option value="lower_reputation">Снизить репутацию ответчика</option>
                      <option value="freeze_account">Заморозить аккаунт ответчика</option>
                      <option value="delete_user">Удалить аккаунт ответчика</option>
                      <option value="reject">Отклонить жалобу</option>
                    </select>
                  </div>
                  <div className="admin-form-group">
                    <label>Комментарий</label>
                    <textarea
                      value={resolveComment}
                      onChange={(e) => setResolveComment(e.target.value)}
                      placeholder="Обоснование решения"
                      rows={3}
                      style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
                    />
                  </div>
                  <div className="admin-modal-actions">
                    <button type="button" onClick={() => setResolveModal(null)}>
                      Отмена
                    </button>
                    <button
                      type="submit"
                      className={resolveAction === 'delete_user' ? 'admin-btn-danger' : 'admin-btn-primary'}
                    >
                      {resolveAction === 'delete_user' ? 'Удалить пользователя' : 'Применить'}
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
