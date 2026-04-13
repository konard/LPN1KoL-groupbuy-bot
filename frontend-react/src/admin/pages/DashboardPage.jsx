/**
 * Admin Dashboard Page with Analytics Charts
 */
import React, { useEffect, useRef } from 'react';
import { useAdminStore } from '../store/adminStore';
import AdminLayout from '../components/AdminLayout';
import StatCard from '../components/StatCard';
import BarChart from '../components/BarChart';
import DonutChart from '../components/DonutChart';

const formatNumber = (num) => {
  if (num === undefined || num === null) return '0';
  return new Intl.NumberFormat('ru-RU').format(num);
};

const formatCurrency = (num) => {
  if (num === undefined || num === null) return '0 ₽';
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
  }).format(num);
};

function objectToChartData(obj) {
  if (!obj) return [];
  return Object.entries(obj).map(([name, value]) => ({ name, value: Number(value) }));
}

export default function DashboardPage() {
  const { dashboardStats, loadDashboardStats, isLoading } = useAdminStore();
  const loadRef = useRef(loadDashboardStats);
  loadRef.current = loadDashboardStats;

  useEffect(() => {
    let cancelled = false;

    const load = () => {
      if (!cancelled) loadRef.current();
    };

    load();

    // Refresh every 30 seconds, but only when the tab is visible
    const REFRESH_INTERVAL = 30_000;
    let intervalId = null;

    const startPolling = () => {
      if (!intervalId) {
        intervalId = setInterval(() => {
          if (!document.hidden) {
            load();
          }
        }, REFRESH_INTERVAL);
      }
    };

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        load();
        startPolling();
      }
    };

    startPolling();
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      cancelled = true;
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []); // Empty deps — runs once on mount, uses ref for stable access

  if (isLoading && !dashboardStats) {
    return (
      <AdminLayout>
        <div className="admin-loading">Загрузка...</div>
      </AdminLayout>
    );
  }

  const stats = dashboardStats || {};

  const usersByRoleData = objectToChartData(stats.users_by_role);
  const usersByPlatformData = objectToChartData(stats.users_by_platform);
  const procurementsByStatusData = objectToChartData(stats.procurements_by_status);
  const paymentsByStatusData = objectToChartData(stats.payments_by_status);

  // Build growth trend from available stats
  const userGrowthData = [
    { name: 'Сегодня', value: stats.new_users_today || 0 },
    { name: 'Неделя', value: stats.new_users_week || 0 },
    { name: 'Месяц', value: stats.new_users_month || 0 },
  ];

  const revenueData = [
    { name: 'Сегодня', value: stats.revenue_today || 0 },
    { name: 'Неделя', value: stats.revenue_week || 0 },
  ];

  return (
    <AdminLayout>
      <div className="admin-page">
        <h1 className="admin-page-title">Дашборд — Аналитика</h1>

        {/* Quick Stats */}
        <section className="admin-section">
          <h2 className="admin-section-title">Пользователи</h2>
          <div className="admin-stat-grid">
            <StatCard
              label="Всего пользователей"
              value={formatNumber(stats.total_users)}
              icon="👥"
              color="primary"
            />
            <StatCard
              label="Новых сегодня"
              value={formatNumber(stats.new_users_today)}
              icon="📈"
              color="success"
            />
            <StatCard
              label="За неделю"
              value={formatNumber(stats.new_users_week)}
              icon="📊"
              color="info"
            />
            <StatCard
              label="За месяц"
              value={formatNumber(stats.new_users_month)}
              icon="📅"
              color="info"
            />
          </div>

          {/* Charts Row */}
          <div className="admin-charts-row">
            <div className="admin-chart-card">
              <h3 className="admin-chart-title">Рост пользователей</h3>
              <BarChart data={userGrowthData} color="#2563eb" label="" />
            </div>
            {usersByRoleData.length > 0 && (
              <div className="admin-chart-card">
                <h3 className="admin-chart-title">По ролям</h3>
                <DonutChart data={usersByRoleData} size={200} />
              </div>
            )}
            {usersByPlatformData.length > 0 && (
              <div className="admin-chart-card">
                <h3 className="admin-chart-title">По платформам</h3>
                <DonutChart data={usersByPlatformData} size={200} />
              </div>
            )}
          </div>
        </section>

        {/* Procurements */}
        <section className="admin-section">
          <h2 className="admin-section-title">Закупки</h2>
          <div className="admin-stat-grid">
            <StatCard
              label="Всего закупок"
              value={formatNumber(stats.total_procurements)}
              icon="🛒"
              color="primary"
            />
            <StatCard
              label="Активных"
              value={formatNumber(stats.active_procurements)}
              icon="✅"
              color="success"
            />
            <StatCard
              label="Завершенных"
              value={formatNumber(stats.completed_procurements)}
              icon="🏁"
              color="info"
            />
          </div>

          {procurementsByStatusData.length > 0 && (
            <div className="admin-charts-row">
              <div className="admin-chart-card">
                <h3 className="admin-chart-title">По статусам</h3>
                <BarChart data={procurementsByStatusData} color="#16a34a" />
              </div>
              <div className="admin-chart-card">
                <h3 className="admin-chart-title">Распределение</h3>
                <DonutChart data={procurementsByStatusData} size={200} />
              </div>
            </div>
          )}
        </section>

        {/* Payments */}
        <section className="admin-section">
          <h2 className="admin-section-title">Платежи и выручка</h2>
          <div className="admin-stat-grid">
            <StatCard
              label="Всего платежей"
              value={formatNumber(stats.total_payments)}
              icon="💳"
              color="primary"
            />
            <StatCard
              label="Общий оборот"
              value={formatCurrency(stats.total_revenue)}
              icon="💰"
              color="success"
            />
            <StatCard
              label="Сегодня"
              value={formatCurrency(stats.revenue_today)}
              icon="📈"
              color="info"
            />
            <StatCard
              label="За неделю"
              value={formatCurrency(stats.revenue_week)}
              icon="📊"
              color="info"
            />
          </div>

          <div className="admin-charts-row">
            <div className="admin-chart-card">
              <h3 className="admin-chart-title">Динамика выручки</h3>
              <BarChart data={revenueData} color="#d97706" />
            </div>
            {paymentsByStatusData.length > 0 && (
              <div className="admin-chart-card">
                <h3 className="admin-chart-title">Статусы платежей</h3>
                <DonutChart data={paymentsByStatusData} size={200} />
              </div>
            )}
          </div>
        </section>

        {/* Activity */}
        <section className="admin-section">
          <h2 className="admin-section-title">Активность</h2>
          <div className="admin-stat-grid">
            <StatCard
              label="Всего сообщений"
              value={formatNumber(stats.total_messages)}
              icon="💬"
              color="primary"
            />
            <StatCard
              label="Сообщений сегодня"
              value={formatNumber(stats.messages_today)}
              icon="📨"
              color="success"
            />
          </div>
        </section>
      </div>
    </AdminLayout>
  );
}
