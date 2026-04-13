/**
 * Admin Payments Page
 */
import React, { useEffect, useState } from 'react';
import { useAdminStore } from '../store/adminStore';
import AdminLayout from '../components/AdminLayout';
import DataTable from '../components/DataTable';
import SearchFilters from '../components/SearchFilters';

export default function PaymentsPage() {
  const {
    payments,
    transactions,
    pagination,
    loadPayments,
    loadTransactions,
    isLoading,
  } = useAdminStore();

  const [activeTab, setActiveTab] = useState('payments');
  const [filters, setFilters] = useState({
    search: '',
    status: '',
    payment_type: '',
    transaction_type: '',
  });
  const [page, setPage] = useState(1);
  const [detailModal, setDetailModal] = useState(null);

  useEffect(() => {
    if (activeTab === 'payments') {
      loadPayments({ ...filters, page });
    } else {
      loadTransactions({ ...filters, page });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, page, activeTab]);

  const handleFilterChange = (key, value) => {
    setFilters({ ...filters, [key]: value });
    setPage(1);
  };

  const handleSearch = (search) => {
    setFilters({ ...filters, search });
    setPage(1);
  };

  const handlePageChange = (direction) => {
    const paginationKey = activeTab === 'payments' ? 'payments' : 'transactions';
    if (direction === 'next' && pagination[paginationKey].next) {
      setPage(page + 1);
    } else if (direction === 'prev' && pagination[paginationKey].previous) {
      setPage(page - 1);
    }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setPage(1);
    setFilters({
      search: '',
      status: '',
      payment_type: '',
      transaction_type: '',
    });
  };

  const paymentColumns = [
    { key: 'id', label: 'ID', width: '60px' },
    {
      key: 'user_name',
      label: 'Пользователь',
    },
    {
      key: 'payment_type',
      label: 'Тип',
      render: (type) => {
        const types = {
          deposit: 'Пополнение',
          withdrawal: 'Вывод',
          procurement_payment: 'Оплата закупки',
        };
        return <span className={`admin-badge admin-badge-${type}`}>{types[type] || type}</span>;
      },
    },
    {
      key: 'amount',
      label: 'Сумма',
      render: (amount) => `${parseFloat(amount || 0).toLocaleString('ru-RU')} ₽`,
    },
    {
      key: 'status',
      label: 'Статус',
      render: (status) => {
        const statuses = {
          pending: 'Ожидает',
          waiting_for_capture: 'Подтверждение',
          succeeded: 'Успешно',
          cancelled: 'Отменен',
          refunded: 'Возврат',
        };
        return (
          <span className={`admin-badge admin-status-badge admin-status-${status}`}>
            {statuses[status] || status}
          </span>
        );
      },
    },
    {
      key: 'provider',
      label: 'Провайдер',
    },
    {
      key: 'created_at',
      label: 'Дата',
      render: (date) => new Date(date).toLocaleString('ru-RU'),
    },
    {
      key: 'paid_at',
      label: 'Оплачен',
      render: (date) => date ? new Date(date).toLocaleString('ru-RU') : '-',
    },
  ];

  const transactionColumns = [
    { key: 'id', label: 'ID', width: '60px' },
    {
      key: 'user_name',
      label: 'Пользователь',
    },
    {
      key: 'transaction_type',
      label: 'Тип',
      render: (type) => {
        const types = {
          deposit: 'Пополнение',
          withdrawal: 'Списание',
          procurement_join: 'Участие в закупке',
          procurement_refund: 'Возврат',
          transfer: 'Перевод',
          bonus: 'Бонус',
        };
        return <span className={`admin-badge admin-badge-${type}`}>{types[type] || type}</span>;
      },
    },
    {
      key: 'amount',
      label: 'Сумма',
      render: (amount) => {
        const value = parseFloat(amount || 0);
        const color = value >= 0 ? 'admin-text-success' : 'admin-text-danger';
        return (
          <span className={color}>
            {value >= 0 ? '+' : ''}{value.toLocaleString('ru-RU')} ₽
          </span>
        );
      },
    },
    {
      key: 'balance_after',
      label: 'Баланс после',
      render: (balance) => `${parseFloat(balance || 0).toLocaleString('ru-RU')} ₽`,
    },
    {
      key: 'description',
      label: 'Описание',
      render: (desc) => desc || '-',
    },
    {
      key: 'created_at',
      label: 'Дата',
      render: (date) => new Date(date).toLocaleString('ru-RU'),
    },
  ];

  const paymentFilterConfig = [
    {
      key: 'status',
      label: 'Статус',
      options: [
        { value: 'pending', label: 'Ожидает' },
        { value: 'waiting_for_capture', label: 'Подтверждение' },
        { value: 'succeeded', label: 'Успешно' },
        { value: 'cancelled', label: 'Отменен' },
        { value: 'refunded', label: 'Возврат' },
      ],
    },
    {
      key: 'payment_type',
      label: 'Тип',
      options: [
        { value: 'deposit', label: 'Пополнение' },
        { value: 'withdrawal', label: 'Вывод' },
        { value: 'procurement_payment', label: 'Оплата закупки' },
      ],
    },
  ];

  const transactionFilterConfig = [
    {
      key: 'transaction_type',
      label: 'Тип',
      options: [
        { value: 'deposit', label: 'Пополнение' },
        { value: 'withdrawal', label: 'Списание' },
        { value: 'procurement_join', label: 'Участие в закупке' },
        { value: 'procurement_refund', label: 'Возврат' },
        { value: 'transfer', label: 'Перевод' },
        { value: 'bonus', label: 'Бонус' },
      ],
    },
  ];

  return (
    <AdminLayout>
      <div className="admin-page">
        <div className="admin-page-header">
          <h1 className="admin-page-title">Финансы</h1>
        </div>

        <div className="admin-tabs">
          <button
            className={`admin-tab ${activeTab === 'payments' ? 'active' : ''}`}
            onClick={() => handleTabChange('payments')}
          >
            Платежи ({pagination.payments.count || 0})
          </button>
          <button
            className={`admin-tab ${activeTab === 'transactions' ? 'active' : ''}`}
            onClick={() => handleTabChange('transactions')}
          >
            Транзакции ({pagination.transactions.count || 0})
          </button>
        </div>

        <SearchFilters
          filters={activeTab === 'payments' ? paymentFilterConfig : transactionFilterConfig}
          values={filters}
          onChange={handleFilterChange}
          onSearch={handleSearch}
        />

        {activeTab === 'payments' ? (
          <DataTable
            columns={paymentColumns}
            data={payments}
            loading={isLoading}
            pagination={pagination.payments}
            onPageChange={handlePageChange}
            onRowClick={(p) => setDetailModal(p)}
            emptyMessage="Платежи не найдены"
          />
        ) : (
          <DataTable
            columns={transactionColumns}
            data={transactions}
            loading={isLoading}
            pagination={pagination.transactions}
            onPageChange={handlePageChange}
            emptyMessage="Транзакции не найдены"
          />
        )}

        {/* Payment Detail Modal */}
        {detailModal && (
          <div className="admin-modal-overlay" onClick={() => setDetailModal(null)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-modal-header">
                <h3>Платеж #{detailModal.id}</h3>
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
                    <label>Пользователь</label>
                    <span>{detailModal.user_name}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Тип</label>
                    <span>{detailModal.payment_type}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Сумма</label>
                    <span>{parseFloat(detailModal.amount || 0).toLocaleString('ru-RU')} ₽</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Статус</label>
                    <span className={`admin-badge admin-status-${detailModal.status}`}>
                      {detailModal.status_display || detailModal.status}
                    </span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Провайдер</label>
                    <span>{detailModal.provider}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>External ID</label>
                    <span>{detailModal.external_id || '-'}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Создан</label>
                    <span>{new Date(detailModal.created_at).toLocaleString('ru-RU')}</span>
                  </div>
                  <div className="admin-detail-item">
                    <label>Оплачен</label>
                    <span>
                      {detailModal.paid_at
                        ? new Date(detailModal.paid_at).toLocaleString('ru-RU')
                        : '-'}
                    </span>
                  </div>
                </div>
                {detailModal.description && (
                  <div className="admin-detail-description">
                    <label>Описание</label>
                    <p>{detailModal.description}</p>
                  </div>
                )}
                {detailModal.confirmation_url && (
                  <div className="admin-detail-description">
                    <label>Ссылка на оплату</label>
                    <a href={detailModal.confirmation_url} target="_blank" rel="noopener noreferrer">
                      {detailModal.confirmation_url}
                    </a>
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
