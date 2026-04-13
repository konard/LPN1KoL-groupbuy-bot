/**
 * Admin Search Analytics Page
 * Search performance metrics, popular queries, and Elasticsearch health
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useAdminStore } from '../store/adminStore';
import AdminLayout from '../components/AdminLayout';
import DataTable from '../components/DataTable';
import StatCard from '../components/StatCard';
import BarChart from '../components/BarChart';

export default function SearchAnalyticsPage() {
  const { isLoading, addToast } = useAdminStore();

  const [stats, setStats] = useState({
    total_queries: 0,
    avg_latency_ms: 0,
    queries_today: 0,
    unique_users: 0,
  });
  const [popularTerms, setPopularTerms] = useState([]);
  const [volumeData, setVolumeData] = useState([]);
  const [savedFilters, setSavedFilters] = useState([]);
  const [indexHealth, setIndexHealth] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [period, setPeriod] = useState('7d');

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    // Search analytics backend is not yet implemented.
    // The /api/admin/search-analytics/ endpoints do not exist.
    setStats({ total_queries: 0, avg_latency_ms: 0, queries_today: 0, unique_users: 0 });
    setPopularTerms([]);
    setVolumeData([]);
    setIndexHealth([]);
    setLoading(false);
  }, []);

  const loadSavedFilters = useCallback(async () => {
    // Saved filters endpoint is not yet implemented.
    setSavedFilters([]);
  }, []);

  useEffect(() => {
    loadAnalytics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (activeTab === 'filters') {
      loadSavedFilters();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const handleDeleteFilter = async (/* filterId */) => {
    // Saved filters delete endpoint is not yet implemented.
    addToast('Функция в разработке', 'info');
  };

  const popularTermColumns = [
    {
      key: 'rank',
      label: '#',
      width: '50px',
      render: (_, __, index) => index + 1,
    },
    {
      key: 'term',
      label: 'Поисковый запрос',
    },
    {
      key: 'count',
      label: 'Кол-во запросов',
      render: (count) => (count || 0).toLocaleString('ru-RU'),
    },
    {
      key: 'avg_results',
      label: 'Ср. результатов',
      render: (avg) => (avg || 0).toLocaleString('ru-RU'),
    },
    {
      key: 'avg_latency',
      label: 'Ср. время (мс)',
      render: (latency) => {
        const value = parseFloat(latency || 0);
        const color = value > 500 ? 'admin-text-danger' : value > 200 ? 'admin-text-warning' : 'admin-text-success';
        return <span className={color}>{value.toFixed(0)} мс</span>;
      },
    },
  ];

  const savedFilterColumns = [
    { key: 'id', label: 'ID', width: '60px' },
    {
      key: 'name',
      label: 'Название',
    },
    {
      key: 'user_name',
      label: 'Пользователь',
    },
    {
      key: 'query',
      label: 'Запрос',
      render: (query) => (
        <code style={{ fontSize: '12px', background: '#f1f5f9', padding: '2px 6px', borderRadius: '3px' }}>
          {query && query.length > 50 ? query.slice(0, 50) + '...' : query}
        </code>
      ),
    },
    {
      key: 'usage_count',
      label: 'Использований',
      render: (count) => count || 0,
    },
    {
      key: 'created_at',
      label: 'Создан',
      render: (date) => new Date(date).toLocaleDateString('ru-RU'),
    },
    {
      key: 'actions',
      label: 'Действия',
      render: (_, filter) => (
        <button
          className="admin-btn admin-btn-sm admin-btn-danger"
          onClick={(e) => {
            e.stopPropagation();
            handleDeleteFilter(filter.id);
          }}
        >
          Удалить
        </button>
      ),
    },
  ];

  const getHealthStatusBadge = (status) => {
    const colors = {
      green: 'succeeded',
      yellow: 'pending',
      red: 'cancelled',
    };
    const labels = {
      green: 'Здоров',
      yellow: 'Предупреждение',
      red: 'Критический',
    };
    return (
      <span className={`admin-badge admin-status-badge admin-status-${colors[status] || 'pending'}`}>
        {labels[status] || status}
      </span>
    );
  };

  const chartData = volumeData.map((item) => ({
    name: item.date || item.label,
    value: item.count || item.value,
  }));

  return (
    <AdminLayout>
      <div className="admin-page">
        <div className="admin-page-header">
          <h1 className="admin-page-title">Аналитика поиска</h1>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <label style={{ fontSize: '14px', color: '#64748b' }}>Период:</label>
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              style={{ padding: '6px 12px', borderRadius: '4px', border: '1px solid #d1d5db' }}
            >
              <option value="1d">1 день</option>
              <option value="7d">7 дней</option>
              <option value="30d">30 дней</option>
              <option value="90d">90 дней</option>
            </select>
          </div>
        </div>

        <div className="admin-notice" style={{ background: '#fef9c3', border: '1px solid #fde047', borderRadius: '8px', padding: '12px 16px', marginBottom: '16px', color: '#713f12' }}>
          Раздел в разработке. Аналитика поиска будет доступна в следующей версии.
        </div>

        <div className="admin-stats-grid">
          <StatCard
            label="Всего запросов"
            value={(stats.total_queries || 0).toLocaleString('ru-RU')}
            icon="🔍"
            color="primary"
          />
          <StatCard
            label="Ср. время ответа"
            value={`${parseFloat(stats.avg_latency_ms || 0).toFixed(0)} мс`}
            icon="⚡"
            color={stats.avg_latency_ms > 500 ? 'danger' : 'success'}
          />
          <StatCard
            label="Запросов сегодня"
            value={(stats.queries_today || 0).toLocaleString('ru-RU')}
            icon="📊"
            color="info"
          />
          <StatCard
            label="Уникальных пользователей"
            value={(stats.unique_users || 0).toLocaleString('ru-RU')}
            icon="👥"
            color="warning"
          />
        </div>

        <div className="admin-tabs">
          <button
            className={`admin-tab ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Обзор
          </button>
          <button
            className={`admin-tab ${activeTab === 'popular' ? 'active' : ''}`}
            onClick={() => setActiveTab('popular')}
          >
            Популярные запросы
          </button>
          <button
            className={`admin-tab ${activeTab === 'filters' ? 'active' : ''}`}
            onClick={() => setActiveTab('filters')}
          >
            Сохраненные фильтры
          </button>
          <button
            className={`admin-tab ${activeTab === 'health' ? 'active' : ''}`}
            onClick={() => setActiveTab('health')}
          >
            Состояние индексов
          </button>
        </div>

        {loading ? (
          <div className="admin-loading">Загрузка...</div>
        ) : (
          <>
            {activeTab === 'overview' && (
              <div>
                <div style={{ background: '#fff', borderRadius: '8px', padding: '20px', border: '1px solid #e2e8f0' }}>
                  <h3 style={{ margin: '0 0 16px', color: '#1e293b' }}>Объём поисковых запросов</h3>
                  <BarChart
                    data={chartData}
                    color="#3b82f6"
                    height={220}
                    label=""
                  />
                </div>

                {popularTerms.length > 0 && (
                  <div style={{ marginTop: '20px', background: '#fff', borderRadius: '8px', padding: '20px', border: '1px solid #e2e8f0' }}>
                    <h3 style={{ margin: '0 0 16px', color: '#1e293b' }}>Топ-10 запросов</h3>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {popularTerms.slice(0, 10).map((term, i) => (
                        <span
                          key={i}
                          className="admin-badge"
                          style={{
                            fontSize: `${Math.max(12, 18 - i)}px`,
                            padding: '4px 12px',
                          }}
                        >
                          {term.term} ({term.count})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'popular' && (
              <DataTable
                columns={popularTermColumns}
                data={popularTerms}
                loading={false}
                emptyMessage="Нет данных о поисковых запросах"
              />
            )}

            {activeTab === 'filters' && (
              <DataTable
                columns={savedFilterColumns}
                data={savedFilters}
                loading={false}
                emptyMessage="Сохраненные фильтры не найдены"
              />
            )}

            {activeTab === 'health' && (
              <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                {Array.isArray(indexHealth) && indexHealth.length > 0 ? (
                  <table className="admin-table" style={{ margin: 0 }}>
                    <thead>
                      <tr>
                        <th>Индекс</th>
                        <th>Статус</th>
                        <th>Документов</th>
                        <th>Размер</th>
                        <th>Шарды</th>
                        <th>Реплики</th>
                      </tr>
                    </thead>
                    <tbody>
                      {indexHealth.map((index, i) => (
                        <tr key={i}>
                          <td>
                            <code style={{ fontSize: '13px' }}>{index.name}</code>
                          </td>
                          <td>{getHealthStatusBadge(index.status)}</td>
                          <td>{(index.docs_count || 0).toLocaleString('ru-RU')}</td>
                          <td>{index.store_size || '-'}</td>
                          <td>{index.primary_shards || '-'}</td>
                          <td>{index.replica_shards || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="admin-empty">Нет данных о состоянии индексов</div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </AdminLayout>
  );
}
