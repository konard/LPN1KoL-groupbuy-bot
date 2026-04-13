/**
 * Admin Users Page
 */
import React, { useEffect, useState } from 'react';
import { useAdminStore } from '../store/adminStore';
import AdminLayout from '../components/AdminLayout';
import DataTable from '../components/DataTable';
import SearchFilters from '../components/SearchFilters';

export default function UsersPage() {
  const {
    users,
    pagination,
    loadUsers,
    toggleUserActive,
    toggleUserVerified,
    updateUserBalance,
    isLoading,
  } = useAdminStore();

  const [filters, setFilters] = useState({
    search: '',
    role: '',
    platform: '',
    is_active: '',
    is_verified: '',
  });
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState([]);
  const [balanceModal, setBalanceModal] = useState(null);
  const [balanceAmount, setBalanceAmount] = useState('');
  const [balanceDescription, setBalanceDescription] = useState('');

  useEffect(() => {
    loadUsers({ ...filters, page });
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
    if (direction === 'next' && pagination.users.next) {
      setPage(page + 1);
    } else if (direction === 'prev' && pagination.users.previous) {
      setPage(page - 1);
    }
  };

  const handleBalanceSubmit = async (e) => {
    e.preventDefault();
    if (!balanceModal || !balanceAmount) return;

    try {
      await updateUserBalance(
        balanceModal.id,
        parseFloat(balanceAmount),
        balanceDescription || 'Корректировка баланса администратором'
      );
      setBalanceModal(null);
      setBalanceAmount('');
      setBalanceDescription('');
    } catch (error) {
      // Error handled in store
    }
  };

  const columns = [
    { key: 'id', label: 'ID', width: '60px' },
    {
      key: 'full_name',
      label: 'Имя',
      render: (_, user) => (
        <div>
          <strong>{user.first_name} {user.last_name}</strong>
          {user.username && <div className="admin-text-muted">@{user.username}</div>}
        </div>
      ),
    },
    {
      key: 'platform',
      label: 'Платформа',
      render: (platform) => (
        <span className={`admin-badge admin-badge-${platform}`}>{platform}</span>
      ),
    },
    {
      key: 'role',
      label: 'Роль',
      render: (role) => (
        <span className={`admin-badge admin-badge-${role}`}>{role}</span>
      ),
    },
    {
      key: 'balance',
      label: 'Баланс',
      render: (balance) => `${parseFloat(balance || 0).toLocaleString('ru-RU')} ₽`,
    },
    {
      key: 'is_active',
      label: 'Активен',
      render: (isActive, user) => (
        <button
          className={`admin-toggle ${isActive ? 'active' : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            toggleUserActive(user.id);
          }}
        >
          {isActive ? '✓' : '✗'}
        </button>
      ),
    },
    {
      key: 'is_verified',
      label: 'Верифицирован',
      render: (isVerified, user) => (
        <button
          className={`admin-toggle ${isVerified ? 'active' : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            toggleUserVerified(user.id);
          }}
        >
          {isVerified ? '✓' : '✗'}
        </button>
      ),
    },
    {
      key: 'created_at',
      label: 'Дата регистрации',
      render: (date) => new Date(date).toLocaleDateString('ru-RU'),
    },
    {
      key: 'actions',
      label: 'Действия',
      render: (_, user) => (
        <button
          className="admin-btn admin-btn-sm"
          onClick={(e) => {
            e.stopPropagation();
            setBalanceModal(user);
          }}
        >
          Баланс
        </button>
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
      key: 'platform',
      label: 'Платформа',
      options: [
        { value: 'telegram', label: 'Telegram' },
        { value: 'websocket', label: 'Web' },
        { value: 'whatsapp', label: 'WhatsApp' },
      ],
    },
    {
      key: 'is_active',
      label: 'Статус',
      options: [
        { value: 'true', label: 'Активные' },
        { value: 'false', label: 'Неактивные' },
      ],
    },
    {
      key: 'is_verified',
      label: 'Верификация',
      options: [
        { value: 'true', label: 'Верифицированные' },
        { value: 'false', label: 'Неверифицированные' },
      ],
    },
  ];

  return (
    <AdminLayout>
      <div className="admin-page">
        <div className="admin-page-header">
          <h1 className="admin-page-title">Пользователи</h1>
          <div className="admin-page-stats">
            Всего: {pagination.users.count || 0}
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
          data={users}
          loading={isLoading}
          selectedIds={selectedIds}
          onSelect={setSelectedIds}
          pagination={pagination.users}
          onPageChange={handlePageChange}
          emptyMessage="Пользователи не найдены"
        />

        {/* Balance Modal */}
        {balanceModal && (
          <div className="admin-modal-overlay" onClick={() => setBalanceModal(null)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-modal-header">
                <h3>Изменить баланс</h3>
                <button
                  className="admin-modal-close"
                  onClick={() => setBalanceModal(null)}
                >
                  ×
                </button>
              </div>
              <div className="admin-modal-body">
                <p>
                  Пользователь: <strong>{balanceModal.first_name} {balanceModal.last_name}</strong>
                  <br />
                  Текущий баланс: <strong>{parseFloat(balanceModal.balance || 0).toLocaleString('ru-RU')} ₽</strong>
                </p>
                <form onSubmit={handleBalanceSubmit}>
                  <div className="admin-form-group">
                    <label>Сумма (положительная для пополнения, отрицательная для списания)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={balanceAmount}
                      onChange={(e) => setBalanceAmount(e.target.value)}
                      required
                    />
                  </div>
                  <div className="admin-form-group">
                    <label>Описание</label>
                    <input
                      type="text"
                      value={balanceDescription}
                      onChange={(e) => setBalanceDescription(e.target.value)}
                      placeholder="Причина изменения баланса"
                    />
                  </div>
                  <div className="admin-modal-actions">
                    <button type="button" onClick={() => setBalanceModal(null)}>
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
