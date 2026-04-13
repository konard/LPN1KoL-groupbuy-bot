import React, { useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../store/useStore';
import { getInitials, getAvatarColor } from '../utils/helpers';
import {
  SettingsIcon,
  NightModeIcon,
  LogoutIcon,
  ShoppingBagIcon,
  HistoryIcon,
  PlusIcon,
  RequestsIcon,
  MailIcon,
  SearchIcon,
} from './Icons';

function BurgerMenu() {
  const navigate = useNavigate();
  const {
    user,
    burgerMenuOpen,
    closeBurgerMenu,
    openCreateProcurementModal,
    theme,
    toggleTheme,
    logout,
    setSidebarTab,
  } = useStore();

  const handleKeyDown = useCallback(
    (e) => { if (e.key === 'Escape') closeBurgerMenu(); },
    [closeBurgerMenu]
  );

  useEffect(() => {
    if (burgerMenuOpen) document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [burgerMenuOpen, handleKeyDown]);

  if (!burgerMenuOpen) return null;

  const go = (path) => { closeBurgerMenu(); navigate(path); };
  const openSettings = () => { closeBurgerMenu(); setSidebarTab('settings'); navigate('/settings'); };

  return (
    <>
      <div className="burger-overlay" onClick={closeBurgerMenu} aria-hidden="true" />

      <nav className="burger-panel" role="navigation" aria-label="Главное меню">
        {/* User section */}
        {user && (
          <div className="burger-user-section">
            <div
              className="burger-user-avatar"
              style={{ backgroundColor: getAvatarColor(user.first_name || '') }}
            >
              {getInitials(user.first_name, user.last_name)}
            </div>
            <div className="burger-user-info">
              <span className="burger-user-name">{user.first_name} {user.last_name || ''}</span>
              <span className="burger-user-sub">{user.phone || user.email || ''}</span>
            </div>
          </div>
        )}

        {/* Role-specific items */}
        {user && (
          <>
            <div className="burger-divider" />
            <ul className="burger-menu-list" role="list">
              {user.role === 'organizer' && (
                <>
                  <li>
                    <button className="burger-menu-item" onClick={() => { closeBurgerMenu(); openCreateProcurementModal(); }}>
                      <PlusIcon />
                      <span>Создать закупку</span>
                    </button>
                  </li>
                  <li>
                    <button className="burger-menu-item" onClick={() => go('/cabinet')}>
                      <ShoppingBagIcon />
                      <span>Мои закупки</span>
                    </button>
                  </li>
                  <li>
                    <button className="burger-menu-item" onClick={() => go('/cabinet')}>
                      <HistoryIcon />
                      <span>История закупок</span>
                    </button>
                  </li>
                </>
              )}
              {user.role === 'supplier' && (
                <>
                  <li>
                    <button className="burger-menu-item" onClick={() => go('/cabinet')}>
                      <ShoppingBagIcon />
                      <span>Текущие отгрузки</span>
                    </button>
                  </li>
                  <li>
                    <button className="burger-menu-item" onClick={() => go('/cabinet')}>
                      <HistoryIcon />
                      <span>История отгрузок</span>
                    </button>
                  </li>
                </>
              )}
              {(user.role === 'buyer' || !user.role) && (
                <>
                  <li>
                    <button className="burger-menu-item" onClick={() => go('/cabinet')}>
                      <ShoppingBagIcon />
                      <span>Текущие закупки</span>
                    </button>
                  </li>
                  <li>
                    <button className="burger-menu-item" onClick={() => go('/cabinet')}>
                      <RequestsIcon />
                      <span>Мои запросы</span>
                    </button>
                  </li>
                  <li>
                    <button className="burger-menu-item" onClick={() => go('/cabinet')}>
                      <HistoryIcon />
                      <span>История закупок</span>
                    </button>
                  </li>
                </>
              )}
              <li>
                <button className="burger-menu-item" onClick={() => go('/cabinet')}>
                  <MailIcon />
                  <span>Подписки</span>
                </button>
              </li>
            </ul>
          </>
        )}

        <div className="burger-divider" />

        <ul className="burger-menu-list" role="list">
          <li>
            <button className="burger-menu-item" onClick={() => go('/')}>
              <SearchIcon />
              <span>Активные закупки</span>
            </button>
          </li>
        </ul>

        <div className="burger-divider" />

        <ul className="burger-menu-list" role="list">
          {/* Настройки */}
          <li>
            <button className="burger-menu-item" onClick={openSettings}>
              <SettingsIcon />
              <span>Настройки</span>
            </button>
          </li>

          {/* Night mode toggle */}
          <li>
            <button
              className="burger-menu-item burger-menu-item--toggle"
              onClick={toggleTheme}
              aria-pressed={theme === 'dark'}
            >
              <NightModeIcon />
              <span>Ночной режим</span>
              <span
                className={`burger-toggle ${theme === 'dark' ? 'burger-toggle--on' : ''}`}
                aria-hidden="true"
              />
            </button>
          </li>

          {user && (
            <li>
              <button
                className="burger-menu-item burger-menu-item--danger"
                onClick={() => { closeBurgerMenu(); logout(); }}
              >
                <LogoutIcon />
                <span>Выйти</span>
              </button>
            </li>
          )}
        </ul>
      </nav>
    </>
  );
}

export default BurgerMenu;
