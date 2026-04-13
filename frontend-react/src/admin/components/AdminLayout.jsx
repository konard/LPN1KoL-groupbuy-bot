/**
 * Admin Layout Component
 * Main layout wrapper for admin panel pages
 */
import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAdminStore } from '../store/adminStore';
import '../styles/admin.css';

export default function AdminLayout({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { adminUser, logout, toasts, removeToast } = useAdminStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/admin-panel/login');
  };

  const closeSidebar = () => setSidebarOpen(false);

  const navItems = [
    { path: '/admin-panel', label: 'Дашборд', icon: '📊' },
    { path: '/admin-panel/users', label: 'Пользователи', icon: '👥' },
    { path: '/admin-panel/procurements', label: 'Закупки', icon: '🛒' },
    { path: '/admin-panel/payments', label: 'Платежи', icon: '💳' },
    { path: '/admin-panel/categories', label: 'Категории', icon: '📁' },
    { path: '/admin-panel/messages', label: 'Сообщения', icon: '💬' },
    { path: '/admin-panel/reports', label: 'Отчёты', icon: '📈' },
    { path: '/admin-panel/reputation', label: 'Репутация', icon: '⭐' },
    { path: '/admin-panel/complaints', label: 'Жалобы', icon: '❗' },
    { path: '/admin-panel/escrow', label: 'Эскроу', icon: '🔒' },
    { path: '/admin-panel/search-analytics', label: 'Поиск', icon: '🔍' },
    { path: '/admin-panel/chat', label: 'Чат с юзерами', icon: '🗨️' },
    { path: '/admin-panel/activity', label: 'Журнал', icon: '📋' },
  ];

  const isActive = (path) => {
    if (path === '/admin-panel') {
      return location.pathname === path;
    }
    return location.pathname.startsWith(path);
  };

  return (
    <div className="admin-layout">
      {/* Mobile hamburger button */}
      <button
        className="admin-mobile-toggle"
        onClick={() => setSidebarOpen(true)}
        aria-label="Открыть меню"
      >
        ☰
      </button>

      {/* Sidebar overlay for mobile */}
      {sidebarOpen && (
        <div className="admin-sidebar-overlay" onClick={closeSidebar} />
      )}

      <aside className={`admin-sidebar${sidebarOpen ? ' open' : ''}`}>
        <div className="admin-sidebar-header">
          <h2>GroupBuy Admin</h2>
        </div>
        <nav className="admin-nav">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`admin-nav-item ${isActive(item.path) ? 'active' : ''}`}
              onClick={closeSidebar}
            >
              <span className="admin-nav-icon">{item.icon}</span>
              <span className="admin-nav-label">{item.label}</span>
            </Link>
          ))}
        </nav>
        <div className="admin-sidebar-footer">
          {adminUser && (
            <div className="admin-user-info">
              <span className="admin-user-name">{adminUser.username}</span>
              {adminUser.email && (
                <span className="admin-user-email">{adminUser.email}</span>
              )}
              {adminUser.is_superuser && (
                <span className="admin-badge">Superuser</span>
              )}
            </div>
          )}
          <button className="admin-logout-btn" onClick={handleLogout}>
            Выйти
          </button>
        </div>
      </aside>
      <main className="admin-main">
        <div className="admin-content">{children}</div>
      </main>

      {/* Toast notifications */}
      <div className="admin-toasts">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`admin-toast admin-toast-${toast.type}`}
            onClick={() => removeToast(toast.id)}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  );
}
