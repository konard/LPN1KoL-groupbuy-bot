/**
 * Admin Escrow Page
 * Escrow account management and dispute resolution
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useAdminStore } from '../store/adminStore';
import AdminLayout from '../components/AdminLayout';
import DataTable from '../components/DataTable';
import SearchFilters from '../components/SearchFilters';
import StatCard from '../components/StatCard';

export default function EscrowPage() {
  const { isLoading, addToast } = useAdminStore();

  const [escrows, setEscrows] = useState([]);
  const [stats, setStats] = useState({
    total_held: 0,
    active_count: 0,
    disputed_count: 0,
    released_today: 0,
  });
  const [pagination, setPagination] = useState({
    count: 0,
    next: null,
    previous: null,
  });
  const [filters, setFilters] = useState({
    search: '',
    status: '',
  });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [detailModal, setDetailModal] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null);

  const getCsrfToken = () =>
    document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/)?.[1] || '';

  const loadEscrows = useCallback(async (/* params = {} */) => {
    setLoading(true);
    // Escrow backend is not yet implemented.
    // The /api/admin/escrow/ endpoint does not exist.
    setEscrows([]);
    setPagination({ count: 0, next: null, previous: null });
    setLoading(false);
  }, []);

  const loadStats = useCallback(async () => {
    // Escrow stats endpoint is not yet implemented.
  }, []);

  useEffect(() => {
    loadEscrows({ ...filters, page });
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

  const handleViewDetail = async (escrow) => {
    // Escrow detail endpoint is not yet implemented.
    setDetailModal(escrow);
  };

  const handleForceAction = async (/* escrowId, action */) => {
    // Escrow force action endpoints are not yet implemented.
    addToast('Функция в разработке', 'info');
    setConfirmAction(null);
  };

  const columns = [
    { key: 'id', label: 'ID', width: '60px' },
    {
      key: 'procurement_title',
      label: 'Закупка',
      render: (title) => (
        <span title={title}>
          {title && title.length > 30 ? title.slice(0, 30) + '...' : title}
        </span>
      ),
    },
    {
      key: 'organizer_name',
      label: 'Организатор',
    },
    {
      key: 'total_amount',
      label: 'Сумма',
      render: (amount) => `${parseFloat(amount || 0).toLocaleString('ru-RU')} ₽`,
    },
    {
      key: 'deposits_count',
      label: 'Депозиты',
      render: (count) => count || 0,
    },
    {
      key: 'confirmations',
      label: 'Подтверждения',
      render: (_, escrow) => {
        const confirmed = escrow.confirmed_count || 0;
        const total = escrow.total_participants || 0;
        const percent = total > 0 ? Math.round((confirmed / total) * 100) : 0;
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                width: '60px',
                height: '8px',
                background: '#e2e8f0',
                borderRadius: '4px',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${percent}%`,
                  height: '100%',
                  background: percent === 100 ? '#22c55e' : '#3b82f6',
                  borderRadius: '4px',
                }}
              />
            </div>
            <span style={{ fontSize: '12px' }}>{confirmed}/{total}</span>
          </div>
        );
      },
    },
    {
      key: 'status',
      label: 'Статус',
      render: (status) => {
        const statuses = {
          active: 'Активен',
          pending_release: 'Ожидает выпуска',
          released: 'Выпущен',
          refunded: 'Возвращен',
          disputed: 'Диспут',
        };
        const statusColors = {
          active: 'pending',
          pending_release: 'waiting_for_capture',
          released: 'succeeded',
          refunded: 'cancelled',
          disputed: 'cancelled',
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
      render: (_, escrow) => (
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          <button
            className="admin-btn admin-btn-sm"
            onClick={(e) => {
              e.stopPropagation();
              handleViewDetail(escrow);
            }}
          >
            Детали
          </button>
          {(escrow.status === 'active' || escrow.status === 'disputed') && (
            <>
              <button
                className="admin-btn admin-btn-sm admin-btn-success"
                onClick={(e) => {
                  e.stopPropagation();
                  setConfirmAction({ id: escrow.id, action: 'force_release', label: 'выпустить средства' });
                }}
              >
                Выпустить
              </button>
              <button
                className="admin-btn admin-btn-sm admin-btn-danger"
                onClick={(e) => {
                  e.stopPropagation();
                  setConfirmAction({ id: escrow.id, action: 'force_refund', label: 'вернуть средства' });
                }}
              >
                Возврат
              </button>
            </>
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
        { value: 'active', label: 'Активен' },
        { value: 'pending_release', label: 'Ожидает выпуска' },
        { value: 'released', label: 'Выпущен' },
        { value: 'refunded', label: 'Возвращен' },
        { value: 'disputed', label: 'Диспут' },
      ],
    },
  ];

  return (
    <AdminLayout>
      <div className="admin-page">
        <div className="admin-page-header">
          <h1 className="admin-page-title">Эскроу-счета</h1>
        </div>

        <div className="admin-notice" style={{ background: '#fef9c3', border: '1px solid #fde047', borderRadius: '8px', padding: '12px 16px', marginBottom: '16px', color: '#713f12' }}>
          Раздел в разработке. Функциональность эскроу-счетов будет доступна в следующей версии.
        </div>

        <div className="admin-stats-grid">
          <StatCard
            label="Общая сумма на эскроу"
            value={`${parseFloat(stats.total_held || 0).toLocaleString('ru-RU')} ₽`}
            icon="💰"
            color="primary"
          />
          <StatCard
            label="Активные счета"
            value={stats.active_count}
            icon="🔒"
            color="info"
          />
          <StatCard
            label="В диспуте"
            value={stats.disputed_count}
            icon="⚠️"
            color="danger"
          />
          <StatCard
            label="Выпущено сегодня"
            value={`${parseFloat(stats.released_today || 0).toLocaleString('ru-RU')} ₽`}
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
          data={escrows}
          loading={loading || isLoading}
          pagination={pagination}
          onPageChange={handlePageChange}
          onRowClick={handleViewDetail}
          emptyMessage="Эскроу-счета не найдены"
        />

        {/* Detail Modal */}
        {detailModal && (
          <div className="admin-modal-overlay" onClick={() => setDetailModal(null)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
              <div className="admin-modal-header">
                <h3>Эскроу #{detailModal.id}</h3>
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
                    <label>Закупка</label>
                    <span>{detailModal.procurement_title}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Организатор</label>
                    <span>{detailModal.organizer_name}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Общая сумма</label>
                    <span>{parseFloat(detailModal.total_amount || 0).toLocaleString('ru-RU')} ₽</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Статус</label>
                    <span className={`admin-badge admin-status-badge admin-status-${detailModal.status}`}>
                      {detailModal.status}
                    </span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Создан</label>
                    <span>{new Date(detailModal.created_at).toLocaleString('ru-RU')}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Подтверждения</label>
                    <span>{detailModal.confirmed_count || 0} / {detailModal.total_participants || 0}</span>
                  </div>
                </div>

                {/* Confirmation progress bar */}
                <div style={{ margin: '16px 0' }}>
                  <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500, color: '#374151' }}>
                    Прогресс подтверждений
                  </label>
                  <div
                    style={{
                      width: '100%',
                      height: '24px',
                      background: '#e2e8f0',
                      borderRadius: '12px',
                      overflow: 'hidden',
                      position: 'relative',
                    }}
                  >
                    {(() => {
                      const confirmed = detailModal.confirmed_count || 0;
                      const total = detailModal.total_participants || 0;
                      const percent = total > 0 ? Math.round((confirmed / total) * 100) : 0;
                      return (
                        <>
                          <div
                            style={{
                              width: `${percent}%`,
                              height: '100%',
                              background: percent === 100 ? '#22c55e' : '#3b82f6',
                              borderRadius: '12px',
                              transition: 'width 0.3s ease',
                            }}
                          />
                          <span
                            style={{
                              position: 'absolute',
                              top: '50%',
                              left: '50%',
                              transform: 'translate(-50%, -50%)',
                              fontSize: '12px',
                              fontWeight: 600,
                              color: percent > 50 ? '#fff' : '#1e293b',
                            }}
                          >
                            {percent}%
                          </span>
                        </>
                      );
                    })()}
                  </div>
                </div>

                {/* Deposits list */}
                {detailModal.deposits && detailModal.deposits.length > 0 && (
                  <div className="admin-detail-description">
                    <label>Депозиты</label>
                    <div style={{ maxHeight: '250px', overflowY: 'auto' }}>
                      <table className="admin-table" style={{ margin: 0 }}>
                        <thead>
                          <tr>
                            <th>Участник</th>
                            <th>Сумма</th>
                            <th>Статус</th>
                            <th>Дата</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detailModal.deposits.map((deposit) => (
                            <tr key={deposit.id}>
                              <td>{deposit.user_name}</td>
                              <td>{parseFloat(deposit.amount || 0).toLocaleString('ru-RU')} ₽</td>
                              <td>
                                <span className={`admin-badge admin-status-badge admin-status-${deposit.confirmed ? 'succeeded' : 'pending'}`}>
                                  {deposit.confirmed ? 'Подтвержден' : 'Ожидает'}
                                </span>
                              </td>
                              <td>{new Date(deposit.created_at).toLocaleString('ru-RU')}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {(detailModal.status === 'active' || detailModal.status === 'disputed') && (
                  <div style={{ marginTop: '16px', display: 'flex', gap: '8px' }}>
                    <button
                      className="admin-btn admin-btn-success"
                      onClick={() => setConfirmAction({ id: detailModal.id, action: 'force_release', label: 'выпустить средства' })}
                    >
                      Принудительный выпуск
                    </button>
                    <button
                      className="admin-btn admin-btn-danger"
                      onClick={() => setConfirmAction({ id: detailModal.id, action: 'force_refund', label: 'вернуть средства' })}
                    >
                      Принудительный возврат
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Confirm Action Modal */}
        {confirmAction && (
          <div className="admin-modal-overlay" onClick={() => setConfirmAction(null)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-modal-header">
                <h3>Подтверждение действия</h3>
                <button
                  className="admin-modal-close"
                  onClick={() => setConfirmAction(null)}
                >
                  ×
                </button>
              </div>
              <div className="admin-modal-body">
                <p>
                  Вы уверены, что хотите <strong>{confirmAction.label}</strong> для эскроу #{confirmAction.id}?
                </p>
                <p className="admin-text-muted">
                  Это действие нельзя отменить.
                </p>
                <div className="admin-modal-actions">
                  <button type="button" onClick={() => setConfirmAction(null)}>
                    Отмена
                  </button>
                  <button
                    className={confirmAction.action === 'force_refund' ? 'admin-btn-danger' : 'admin-btn-primary'}
                    onClick={() => handleForceAction(confirmAction.id, confirmAction.action)}
                  >
                    Подтвердить
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
