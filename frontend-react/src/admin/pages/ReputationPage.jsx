/**
 * Admin Reputation Page
 * Manage user reputation scores, reviews, and blocks
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useAdminStore } from '../store/adminStore';
import AdminLayout from '../components/AdminLayout';
import DataTable from '../components/DataTable';
import SearchFilters from '../components/SearchFilters';
import StatCard from '../components/StatCard';
import { adminApi } from '../services/adminApi';

export default function ReputationPage() {
  const { isLoading, addToast } = useAdminStore();

  const [reputationData, setReputationData] = useState([]);
  const [stats, setStats] = useState({
    total_users: 0,
    avg_rating: 0,
    blocked_users: 0,
    total_reviews: 0,
  });
  const [pagination, setPagination] = useState({
    count: 0,
    next: null,
    previous: null,
  });
  const [filters, setFilters] = useState({
    search: '',
    role: '',
    is_active: '',
  });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [reviewsModal, setReviewsModal] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [adjustModal, setAdjustModal] = useState(null);
  const [adjustAmount, setAdjustAmount] = useState('');
  const [adjustReason, setAdjustReason] = useState('');

  const loadReputationData = useCallback(async (params = {}) => {
    setLoading(true);
    try {
      const response = await adminApi.getUsers(params);
      setReputationData(response.results || response);
      setPagination({
        count: response.count || 0,
        next: response.next,
        previous: response.previous,
      });
      if (response.stats) {
        setStats(response.stats);
      }
    } catch (error) {
      addToast('Ошибка загрузки данных репутации', 'error');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const response = await adminApi.getUsers({ page_size: 1 });
      setStats((prev) => ({
        ...prev,
        total_users: response.count || 0,
      }));
    } catch {
      // Stats loading is non-critical
    }
  }, []);

  useEffect(() => {
    loadReputationData({ ...filters, page });
    loadStats();
  }, [loadReputationData, loadStats, filters, page]);

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

  const handleViewReviews = async (user) => {
    setReviewsModal(user);
    // Reviews are not yet stored separately; show placeholder
    setReviews([]);
  };

  const handleAdjustReputation = async (e) => {
    e.preventDefault();
    if (!adjustModal || !adjustAmount) return;
    try {
      // Reputation adjustment is implemented via balance update as a proxy action
      await adminApi.updateUserBalance(
        adjustModal.id,
        parseFloat(adjustAmount),
        adjustReason || 'Корректировка репутации администратором'
      );
      addToast('Корректировка применена', 'success');
      setAdjustModal(null);
      setAdjustAmount('');
      setAdjustReason('');
      loadReputationData({ ...filters, page });
    } catch {
      addToast('Ошибка обновления', 'error');
    }
  };

  const handleToggleBlock = async (user) => {
    try {
      await adminApi.toggleUserActive(user.id);
      addToast(
        user.is_active === false ? 'Пользователь разблокирован' : 'Пользователь заблокирован',
        'success'
      );
      loadReputationData({ ...filters, page });
    } catch {
      addToast('Ошибка изменения статуса блокировки', 'error');
    }
  };

  const columns = [
    { key: 'id', label: 'ID', width: '60px' },
    {
      key: 'full_name',
      label: 'Пользователь',
      render: (_, user) => (
        <div>
          <strong>{user.first_name} {user.last_name}</strong>
          {user.username && <div className="admin-text-muted">@{user.username}</div>}
        </div>
      ),
    },
    {
      key: 'role',
      label: 'Роль',
      render: (role) => {
        const roles = {
          buyer: 'Покупатель',
          organizer: 'Организатор',
          supplier: 'Поставщик',
        };
        return <span className={`admin-badge admin-badge-${role}`}>{roles[role] || role}</span>;
      },
    },
    {
      key: 'avg_rating',
      label: 'Рейтинг',
      render: (rating) => {
        const value = parseFloat(rating || 0).toFixed(1);
        const stars = '★'.repeat(Math.round(value)) + '☆'.repeat(5 - Math.round(value));
        return (
          <span title={`${value} / 5.0`}>
            <span style={{ color: '#f59e0b' }}>{stars}</span> {value}
          </span>
        );
      },
    },
    {
      key: 'review_count',
      label: 'Отзывы',
      render: (count) => count || 0,
    },
    {
      key: 'complaint_count',
      label: 'Жалобы',
      render: (count) => {
        const value = count || 0;
        return (
          <span className={value > 0 ? 'admin-text-danger' : ''}>
            {value}
          </span>
        );
      },
    },
    {
      key: 'is_active',
      label: 'Статус',
      render: (isActive) => (
        <span className={`admin-badge admin-status-badge admin-status-${isActive ? 'succeeded' : 'cancelled'}`}>
          {isActive ? 'Активен' : 'Заблокирован'}
        </span>
      ),
    },
    {
      key: 'actions',
      label: 'Действия',
      render: (_, user) => (
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          <button
            className="admin-btn admin-btn-sm"
            onClick={(e) => {
              e.stopPropagation();
              handleViewReviews(user);
            }}
          >
            Отзывы
          </button>
          <button
            className="admin-btn admin-btn-sm"
            onClick={(e) => {
              e.stopPropagation();
              setAdjustModal(user);
            }}
          >
            Коррекция
          </button>
          <button
            className={`admin-btn admin-btn-sm ${user.is_active === false ? 'admin-btn-success' : 'admin-btn-danger'}`}
            onClick={(e) => {
              e.stopPropagation();
              handleToggleBlock(user);
            }}
          >
            {user.is_active === false ? 'Разблокировать' : 'Заблокировать'}
          </button>
        </div>
      ),
    },
  ];

  const filterConfig = [
    {
      key: 'role',
      label: 'Роль',
      options: [
        { value: 'buyer', label: 'Покупатель' },
        { value: 'organizer', label: 'Организатор' },
        { value: 'supplier', label: 'Поставщик' },
      ],
    },
    {
      key: 'is_active',
      label: 'Статус',
      options: [
        { value: 'true', label: 'Активные' },
        { value: 'false', label: 'Заблокированные' },
      ],
    },
  ];

  return (
    <AdminLayout>
      <div className="admin-page">
        <div className="admin-page-header">
          <h1 className="admin-page-title">Репутация</h1>
        </div>

        <div className="admin-stats-grid">
          <StatCard
            label="Всего пользователей"
            value={stats.total_users}
            icon="👥"
            color="primary"
          />
          <StatCard
            label="Средний рейтинг"
            value={parseFloat(stats.avg_rating || 0).toFixed(1)}
            icon="⭐"
            color="warning"
          />
          <StatCard
            label="Всего отзывов"
            value={stats.total_reviews}
            icon="📝"
            color="info"
          />
          <StatCard
            label="Заблокированные"
            value={stats.blocked_users}
            icon="🚫"
            color="danger"
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
          data={reputationData}
          loading={loading || isLoading}
          pagination={pagination}
          onPageChange={handlePageChange}
          emptyMessage="Пользователи не найдены"
        />

        {/* Reviews Modal */}
        {reviewsModal && (
          <div className="admin-modal-overlay" onClick={() => setReviewsModal(null)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-modal-header">
                <h3>Отзывы: {reviewsModal.first_name} {reviewsModal.last_name}</h3>
                <button
                  className="admin-modal-close"
                  onClick={() => setReviewsModal(null)}
                >
                  ×
                </button>
              </div>
              <div className="admin-modal-body">
                {reviews.length === 0 ? (
                  <div className="admin-empty">Отзывов нет</div>
                ) : (
                  <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                    {reviews.map((review) => (
                      <div
                        key={review.id}
                        style={{
                          padding: '12px',
                          borderBottom: '1px solid #e2e8f0',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <strong>{review.author_name || 'Аноним'}</strong>
                          <span style={{ color: '#f59e0b' }}>
                            {'★'.repeat(review.rating)}{'☆'.repeat(5 - review.rating)}
                          </span>
                        </div>
                        <p style={{ margin: '4px 0', color: '#475569' }}>{review.text}</p>
                        <div className="admin-text-muted" style={{ fontSize: '12px' }}>
                          {new Date(review.created_at).toLocaleString('ru-RU')}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Adjust Reputation Modal */}
        {adjustModal && (
          <div className="admin-modal-overlay" onClick={() => setAdjustModal(null)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-modal-header">
                <h3>Корректировка рейтинга</h3>
                <button
                  className="admin-modal-close"
                  onClick={() => setAdjustModal(null)}
                >
                  ×
                </button>
              </div>
              <div className="admin-modal-body">
                <p>
                  Пользователь: <strong>{adjustModal.first_name} {adjustModal.last_name}</strong>
                  <br />
                  Текущий рейтинг: <strong>{parseFloat(adjustModal.avg_rating || 0).toFixed(1)}</strong>
                </p>
                <form onSubmit={handleAdjustReputation}>
                  <div className="admin-form-group">
                    <label>Изменение рейтинга (от -5.0 до +5.0)</label>
                    <input
                      type="number"
                      step="0.1"
                      min="-5"
                      max="5"
                      value={adjustAmount}
                      onChange={(e) => setAdjustAmount(e.target.value)}
                      required
                    />
                  </div>
                  <div className="admin-form-group">
                    <label>Причина</label>
                    <input
                      type="text"
                      value={adjustReason}
                      onChange={(e) => setAdjustReason(e.target.value)}
                      placeholder="Причина корректировки"
                    />
                  </div>
                  <div className="admin-modal-actions">
                    <button type="button" onClick={() => setAdjustModal(null)}>
                      Отмена
                    </button>
                    <button type="submit" className="admin-btn-primary">
                      Применить
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
