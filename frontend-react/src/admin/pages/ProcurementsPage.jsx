/**
 * Admin Procurements Page
 */
import React, { useEffect, useState } from 'react';
import { useAdminStore } from '../store/adminStore';
import AdminLayout from '../components/AdminLayout';
import DataTable from '../components/DataTable';
import SearchFilters from '../components/SearchFilters';

export default function ProcurementsPage() {
  const {
    procurements,
    pagination,
    loadProcurements,
    updateProcurementStatus,
    toggleProcurementFeatured,
    isLoading,
  } = useAdminStore();

  const [filters, setFilters] = useState({
    search: '',
    status: '',
    is_featured: '',
  });
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState([]);
  const [detailModal, setDetailModal] = useState(null);

  useEffect(() => {
    loadProcurements({ ...filters, page });
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
    if (direction === 'next' && pagination.procurements.next) {
      setPage(page + 1);
    } else if (direction === 'prev' && pagination.procurements.previous) {
      setPage(page - 1);
    }
  };

  const handleStatusChange = async (procurementId, newStatus) => {
    await updateProcurementStatus(procurementId, newStatus);
  };

  const statusOptions = [
    { value: 'draft', label: 'Черновик' },
    { value: 'active', label: 'Активная' },
    { value: 'stopped', label: 'Остановлена' },
    { value: 'payment', label: 'Оплата' },
    { value: 'completed', label: 'Завершена' },
    { value: 'cancelled', label: 'Отменена' },
  ];

  const columns = [
    { key: 'id', label: 'ID', width: '60px' },
    {
      key: 'title',
      label: 'Название',
      render: (title, procurement) => (
        <div>
          <strong>{title}</strong>
          {procurement.is_featured && (
            <span className="admin-badge admin-badge-featured">⭐</span>
          )}
          <div className="admin-text-muted">{procurement.city}</div>
        </div>
      ),
    },
    {
      key: 'organizer_name',
      label: 'Организатор',
    },
    {
      key: 'status',
      label: 'Статус',
      render: (status, procurement) => (
        <select
          value={status}
          onChange={(e) => handleStatusChange(procurement.id, e.target.value)}
          onClick={(e) => e.stopPropagation()}
          className={`admin-status-select admin-status-${status}`}
        >
          {statusOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: 'progress',
      label: 'Прогресс',
      render: (progress, procurement) => (
        <div className="admin-progress">
          <div className="admin-progress-bar">
            <div
              className="admin-progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="admin-progress-text">
            {parseFloat(procurement.current_amount || 0).toLocaleString('ru-RU')} /
            {parseFloat(procurement.target_amount || 0).toLocaleString('ru-RU')} ₽
          </span>
        </div>
      ),
    },
    {
      key: 'participant_count',
      label: 'Участники',
      width: '100px',
    },
    {
      key: 'deadline',
      label: 'Дедлайн',
      render: (deadline) => {
        if (!deadline) return '-';
        const date = new Date(deadline);
        const isExpired = date < new Date();
        return (
          <span className={isExpired ? 'admin-text-danger' : ''}>
            {date.toLocaleDateString('ru-RU')}
          </span>
        );
      },
    },
    {
      key: 'is_featured',
      label: 'Избранное',
      width: '100px',
      render: (isFeatured, procurement) => (
        <button
          className={`admin-toggle ${isFeatured ? 'active' : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            toggleProcurementFeatured(procurement.id);
          }}
        >
          {isFeatured ? '⭐' : '☆'}
        </button>
      ),
    },
  ];

  const filterConfig = [
    {
      key: 'status',
      label: 'Статус',
      options: statusOptions,
    },
    {
      key: 'is_featured',
      label: 'Избранное',
      options: [
        { value: 'true', label: 'Только избранные' },
        { value: 'false', label: 'Не избранные' },
      ],
    },
  ];

  return (
    <AdminLayout>
      <div className="admin-page">
        <div className="admin-page-header">
          <h1 className="admin-page-title">Закупки</h1>
          <div className="admin-page-stats">
            Всего: {pagination.procurements.count || 0}
          </div>
        </div>

        <SearchFilters
          filters={filterConfig}
          values={filters}
          onChange={handleFilterChange}
          onSearch={handleSearch}
        />

        <DataTable
          columns={columns}
          data={procurements}
          loading={isLoading}
          selectedIds={selectedIds}
          onSelect={setSelectedIds}
          pagination={pagination.procurements}
          onPageChange={handlePageChange}
          onRowClick={(p) => setDetailModal(p)}
          emptyMessage="Закупки не найдены"
        />

        {/* Detail Modal */}
        {detailModal && (
          <div className="admin-modal-overlay" onClick={() => setDetailModal(null)}>
            <div className="admin-modal admin-modal-lg" onClick={(e) => e.stopPropagation()}>
              <div className="admin-modal-header">
                <h3>{detailModal.title}</h3>
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
                    <label>ID</label>
                    <span>{detailModal.id}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Статус</label>
                    <span className={`admin-badge admin-badge-${detailModal.status}`}>
                      {detailModal.status_display || detailModal.status}
                    </span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Организатор</label>
                    <span>{detailModal.organizer_name}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Категория</label>
                    <span>{detailModal.category_name || 'Без категории'}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Город</label>
                    <span>{detailModal.city}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Дедлайн</label>
                    <span>{detailModal.deadline ? new Date(detailModal.deadline).toLocaleString('ru-RU') : '-'}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Целевая сумма</label>
                    <span>{parseFloat(detailModal.target_amount || 0).toLocaleString('ru-RU')} ₽</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Текущая сумма</label>
                    <span>{parseFloat(detailModal.current_amount || 0).toLocaleString('ru-RU')} ₽</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Участников</label>
                    <span>{detailModal.participant_count}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Создана</label>
                    <span>{new Date(detailModal.created_at).toLocaleString('ru-RU')}</span>
                  </div>
                </div>
                <div className="admin-detail-description">
                  <label>Описание</label>
                  <p>{detailModal.description}</p>
                </div>
                {detailModal.delivery_address && (
                  <div className="admin-detail-description">
                    <label>Адрес доставки</label>
                    <p>{detailModal.delivery_address}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
