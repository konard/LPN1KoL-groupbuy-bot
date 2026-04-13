/**
 * Admin Reports Page
 * Advanced analytics with date filtering, time-series charts,
 * top categories/organizers, conversion funnel, and CSV export
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useAdminStore } from '../store/adminStore';
import AdminLayout from '../components/AdminLayout';
import BarChart from '../components/BarChart';
import DonutChart from '../components/DonutChart';

const formatCurrency = (num) => {
  if (num === undefined || num === null) return '0 ₽';
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
  }).format(num);
};

const formatNumber = (num) => {
  if (num === undefined || num === null) return '0';
  return new Intl.NumberFormat('ru-RU').format(num);
};

function objectToChartData(obj) {
  if (!obj) return [];
  return Object.entries(obj).map(([name, value]) => ({ name, value: Number(value) }));
}

function seriesToChartData(series, valueKey = 'count') {
  if (!series || !Array.isArray(series)) return [];
  return series.map((item) => ({
    name: item.date ? item.date.slice(5, 10) : '?',
    value: Number(item[valueKey] || 0),
  }));
}

function getDefaultDateFrom() {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().slice(0, 10);
}

function getDefaultDateTo() {
  return new Date().toISOString().slice(0, 10);
}

function exportCSV(headers, rows, filename) {
  const csvContent = [
    headers.join(','),
    ...rows.map((r) => r.map((v) => `"${v}"`).join(',')),
  ].join('\n');
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
}

export default function ReportsPage() {
  const {
    dashboardStats,
    loadDashboardStats,
    analyticsData,
    loadAnalytics,
    isLoading,
  } = useAdminStore();

  const [dateFrom, setDateFrom] = useState(getDefaultDateFrom);
  const [dateTo, setDateTo] = useState(getDefaultDateTo);
  const [period, setPeriod] = useState('day');

  const loadDashboardStatsRef = useRef(loadDashboardStats);
  loadDashboardStatsRef.current = loadDashboardStats;
  const loadAnalyticsRef = useRef(loadAnalytics);
  loadAnalyticsRef.current = loadAnalytics;

  const fetchData = useCallback(() => {
    loadDashboardStatsRef.current();
    loadAnalyticsRef.current({ date_from: dateFrom, date_to: dateTo, period });
  }, [dateFrom, dateTo, period]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const stats = dashboardStats || {};
  const analytics = analyticsData || {};

  const usersByRoleData = objectToChartData(stats.users_by_role);
  const usersByPlatformData = objectToChartData(stats.users_by_platform);
  const procurementsByStatusData = objectToChartData(stats.procurements_by_status);
  const paymentsByStatusData = objectToChartData(stats.payments_by_status);

  const userRegData = seriesToChartData(analytics.user_registrations);
  const revenueData = seriesToChartData(analytics.revenue, 'count');
  const procurementData = seriesToChartData(analytics.procurements_created);
  const messageData = seriesToChartData(analytics.messages_sent);

  const topCategories = analytics.top_categories || [];
  const topOrganizers = analytics.top_organizers || [];
  const funnel = analytics.funnel || {};

  const funnelData = [
    { name: 'Регистрации', value: funnel.registered || 0 },
    { name: 'Участвовали', value: funnel.participated || 0 },
    { name: 'Оплатили', value: funnel.paid || 0 },
  ];

  const handleExportUsers = () => {
    if (!analytics.user_registrations) return;
    exportCSV(
      ['Дата', 'Регистрации'],
      analytics.user_registrations.map((r) => [r.date, r.count]),
      'user_registrations.csv'
    );
  };

  const handleExportRevenue = () => {
    if (!analytics.revenue) return;
    exportCSV(
      ['Дата', 'Платежей', 'Сумма'],
      analytics.revenue.map((r) => [r.date, r.count, r.total || 0]),
      'revenue.csv'
    );
  };

  return (
    <AdminLayout>
      <div className="admin-page">
        <div className="admin-page-header">
          <h1 className="admin-page-title">Отчёты и аналитика</h1>
        </div>

        {/* Date Range Filter */}
        <div className="admin-filters" style={{ marginBottom: '1.5rem' }}>
          <div className="admin-filter-controls">
            <div className="admin-filter-item">
              <label>С:</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                style={{
                  padding: '0.375rem 0.75rem',
                  border: '1px solid var(--admin-border)',
                  borderRadius: '0.375rem',
                  fontSize: '0.875rem',
                }}
              />
            </div>
            <div className="admin-filter-item">
              <label>По:</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                style={{
                  padding: '0.375rem 0.75rem',
                  border: '1px solid var(--admin-border)',
                  borderRadius: '0.375rem',
                  fontSize: '0.875rem',
                }}
              />
            </div>
            <div className="admin-filter-item">
              <label>Период:</label>
              <select
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
              >
                <option value="day">По дням</option>
                <option value="week">По неделям</option>
                <option value="month">По месяцам</option>
              </select>
            </div>
            <button
              className="admin-btn admin-btn-primary"
              onClick={fetchData}
              disabled={isLoading}
            >
              Обновить
            </button>
          </div>
        </div>

        {isLoading && !dashboardStats && !analyticsData ? (
          <div className="admin-loading">Загрузка данных...</div>
        ) : (
          <>
            {/* Summary Cards */}
            <div className="admin-reports-grid">
              <div className="admin-report-card">
                <h3>Сводка по пользователям</h3>
                <table className="admin-report-table">
                  <thead>
                    <tr><th>Метрика</th><th>Значение</th></tr>
                  </thead>
                  <tbody>
                    <tr><td>Всего пользователей</td><td>{formatNumber(stats.total_users)}</td></tr>
                    <tr><td>Новых сегодня</td><td>{formatNumber(stats.new_users_today)}</td></tr>
                    <tr><td>За неделю</td><td>{formatNumber(stats.new_users_week)}</td></tr>
                    <tr><td>За месяц</td><td>{formatNumber(stats.new_users_month)}</td></tr>
                    {usersByRoleData.map((r) => (
                      <tr key={r.name}><td>Роль: {r.name}</td><td>{r.value}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="admin-report-card">
                <h3>Сводка по закупкам</h3>
                <table className="admin-report-table">
                  <thead>
                    <tr><th>Метрика</th><th>Значение</th></tr>
                  </thead>
                  <tbody>
                    <tr><td>Всего закупок</td><td>{formatNumber(stats.total_procurements)}</td></tr>
                    <tr><td>Активных</td><td>{formatNumber(stats.active_procurements)}</td></tr>
                    <tr><td>Завершённых</td><td>{formatNumber(stats.completed_procurements)}</td></tr>
                    {procurementsByStatusData.map((r) => (
                      <tr key={r.name}><td>Статус: {r.name}</td><td>{r.value}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="admin-report-card">
                <h3>Финансовый отчёт</h3>
                <table className="admin-report-table">
                  <thead>
                    <tr><th>Период</th><th>Сумма</th></tr>
                  </thead>
                  <tbody>
                    <tr><td>Общий оборот</td><td>{formatCurrency(stats.total_revenue)}</td></tr>
                    <tr><td>Сегодня</td><td>{formatCurrency(stats.revenue_today)}</td></tr>
                    <tr><td>За неделю</td><td>{formatCurrency(stats.revenue_week)}</td></tr>
                    <tr><td>Всего платежей</td><td>{formatNumber(stats.total_payments)}</td></tr>
                    {paymentsByStatusData.map((r) => (
                      <tr key={r.name}><td>Статус: {r.name}</td><td>{r.value}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="admin-report-card">
                <h3>Активность платформы</h3>
                <table className="admin-report-table">
                  <thead>
                    <tr><th>Метрика</th><th>Значение</th></tr>
                  </thead>
                  <tbody>
                    <tr><td>Всего сообщений</td><td>{formatNumber(stats.total_messages)}</td></tr>
                    <tr><td>Сообщений сегодня</td><td>{formatNumber(stats.messages_today)}</td></tr>
                    {usersByPlatformData.map((r) => (
                      <tr key={r.name}><td>Платформа: {r.name}</td><td>{r.value}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Time-series Charts */}
            <section className="admin-section admin-report-section">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 className="admin-section-title">Динамика за выбранный период</h2>
                <div className="admin-actions">
                  <button className="admin-btn admin-btn-sm" onClick={handleExportUsers}>
                    CSV: Регистрации
                  </button>
                  <button className="admin-btn admin-btn-sm" onClick={handleExportRevenue}>
                    CSV: Выручка
                  </button>
                </div>
              </div>

              <div className="admin-charts-row">
                <div className="admin-chart-card">
                  <h3 className="admin-chart-title">Регистрации пользователей</h3>
                  <BarChart data={userRegData} color="#2563eb" />
                </div>
                <div className="admin-chart-card">
                  <h3 className="admin-chart-title">Платежи</h3>
                  <BarChart data={revenueData} color="#d97706" />
                </div>
              </div>

              <div className="admin-charts-row">
                <div className="admin-chart-card">
                  <h3 className="admin-chart-title">Создание закупок</h3>
                  <BarChart data={procurementData} color="#16a34a" />
                </div>
                <div className="admin-chart-card">
                  <h3 className="admin-chart-title">Сообщения</h3>
                  <BarChart data={messageData} color="#0891b2" />
                </div>
              </div>
            </section>

            {/* Distribution Charts */}
            <section className="admin-section admin-report-section">
              <h2 className="admin-section-title">Распределение</h2>
              <div className="admin-charts-row">
                {usersByRoleData.length > 0 && (
                  <div className="admin-chart-card">
                    <h3 className="admin-chart-title">Пользователи по ролям</h3>
                    <DonutChart data={usersByRoleData} size={200} />
                  </div>
                )}
                {usersByPlatformData.length > 0 && (
                  <div className="admin-chart-card">
                    <h3 className="admin-chart-title">По платформам</h3>
                    <DonutChart data={usersByPlatformData} size={200} />
                  </div>
                )}
                {procurementsByStatusData.length > 0 && (
                  <div className="admin-chart-card">
                    <h3 className="admin-chart-title">Закупки по статусам</h3>
                    <DonutChart data={procurementsByStatusData} size={200} />
                  </div>
                )}
              </div>
            </section>

            {/* Conversion Funnel */}
            <section className="admin-section admin-report-section">
              <h2 className="admin-section-title">Воронка конверсии</h2>
              <div className="admin-charts-row">
                <div className="admin-chart-card">
                  <h3 className="admin-chart-title">Регистрация → Участие → Оплата</h3>
                  <BarChart data={funnelData} color="#8b5cf6" />
                </div>
                <div className="admin-chart-card">
                  <h3 className="admin-chart-title">Конверсия (%)</h3>
                  <table className="admin-report-table">
                    <thead>
                      <tr><th>Этап</th><th>Кол-во</th><th>Конверсия</th></tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Зарегистрировались</td>
                        <td>{formatNumber(funnel.registered)}</td>
                        <td>100%</td>
                      </tr>
                      <tr>
                        <td>Участвовали в закупке</td>
                        <td>{formatNumber(funnel.participated)}</td>
                        <td>
                          {funnel.registered
                            ? Math.round((funnel.participated / funnel.registered) * 100) + '%'
                            : '—'}
                        </td>
                      </tr>
                      <tr>
                        <td>Совершили оплату</td>
                        <td>{formatNumber(funnel.paid)}</td>
                        <td>
                          {funnel.registered
                            ? Math.round((funnel.paid / funnel.registered) * 100) + '%'
                            : '—'}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </section>

            {/* Top Categories & Organizers */}
            <section className="admin-section admin-report-section">
              <h2 className="admin-section-title">Рейтинги</h2>
              <div className="admin-reports-grid">
                <div className="admin-report-card">
                  <h3>Топ категории по закупкам</h3>
                  <table className="admin-report-table">
                    <thead>
                      <tr><th>Категория</th><th>Закупок</th></tr>
                    </thead>
                    <tbody>
                      {topCategories.length === 0 ? (
                        <tr><td colSpan={2} style={{ textAlign: 'center', color: 'var(--admin-text-muted)' }}>Нет данных</td></tr>
                      ) : topCategories.map((cat) => (
                        <tr key={cat.id}>
                          <td>{cat.icon || ''} {cat.name}</td>
                          <td>{cat.procurement_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="admin-report-card">
                  <h3>Топ организаторы</h3>
                  <table className="admin-report-table">
                    <thead>
                      <tr><th>Организатор</th><th>Закупок</th></tr>
                    </thead>
                    <tbody>
                      {topOrganizers.length === 0 ? (
                        <tr><td colSpan={2} style={{ textAlign: 'center', color: 'var(--admin-text-muted)' }}>Нет данных</td></tr>
                      ) : topOrganizers.map((org) => (
                        <tr key={org.id}>
                          <td>{org.first_name} {org.last_name || ''}</td>
                          <td>{org.procurement_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </AdminLayout>
  );
}
