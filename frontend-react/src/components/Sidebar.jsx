import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useStore } from '../store/useStore';
import { getInitials, getAvatarColor, formatTime } from '../utils/helpers';

function firstWords(text, n) {
  if (!text) return '';
  const words = text.trim().split(/\s+/);
  if (words.length <= n) return text;
  return words.slice(0, n).join(' ') + '…';
}

import {
  BurgerMenuIcon,
  SunIcon,
  MoonIcon,
  SearchIcon,
} from './Icons';
import BurgerMenu from './BurgerMenu';

function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const categoryParam = new URLSearchParams(location.search).get('category') || '';
  const [searchQuery, setSearchQuery] = useState(categoryParam);

  useEffect(() => {
    const category = new URLSearchParams(location.search).get('category') || '';
    setSearchQuery(category);
  }, [location.search]);

  const {
    user,
    procurements,
    currentChat,
    unreadCounts,
    sidebarOpen,
    closeSidebar,
    theme,
    toggleTheme,
    toggleBurgerMenu,
    setCurrentChat,
    sidebarTab,
    setSidebarTab,
  } = useStore();

  useEffect(() => {
    if (location.pathname.includes('/settings')) {
      setSidebarTab('settings');
    } else if (location.pathname.includes('/cabinet')) {
      setSidebarTab('cabinet');
    } else if (!location.pathname.includes('/chat')) {
      setSidebarTab('chats');
    }
  }, [location.pathname]);

  const filteredProcurements = searchQuery
    ? procurements.filter(
        (p) =>
          p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          p.city?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : procurements;

  const handleChatClick = (procurement) => {
    setCurrentChat(procurement.id);
    navigate(`/chat/${procurement.id}`);
    closeSidebar();
  };

  const handleTabChange = (tab) => {
    setSidebarTab(tab);
    if (tab === 'chats') navigate('/');
    else if (tab === 'cabinet') { navigate('/cabinet'); closeSidebar(); }
    else if (tab === 'settings') { navigate('/settings'); closeSidebar(); }
  };

  return (
    <>
    <BurgerMenu />
    <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
      <header className="header">
        <button
          className="btn btn-icon burger-btn"
          aria-label="Menu"
          onClick={toggleBurgerMenu}
        >
          <BurgerMenuIcon />
        </button>
        <h1 className="header-title">GroupBuy</h1>
        {!user && (
          <button
            className="btn btn-icon theme-toggle"
            aria-label="Toggle theme"
            onClick={toggleTheme}
          >
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>
        )}
      </header>

      <div className="search-bar">
        <SearchIcon className="search-icon" />
        <input
          type="text"
          className="search-input"
          placeholder="Поиск..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <div className="tabs">
        <button
          className={`tab ${sidebarTab === 'chats' ? 'active' : ''}`}
          onClick={() => handleTabChange('chats')}
        >
          Чаты
        </button>
        <button
          className={`tab ${sidebarTab === 'cabinet' ? 'active' : ''}`}
          onClick={() => handleTabChange('cabinet')}
        >
          Кабинет
        </button>
        <button
          className={`tab ${sidebarTab === 'settings' ? 'active' : ''}`}
          onClick={() => handleTabChange('settings')}
        >
          Настройки
        </button>
      </div>

      {sidebarTab === 'chats' && (
        <div className="chat-list">
          {filteredProcurements.length === 0 ? (
            <div className="p-lg text-center text-muted">
              <p>Нет активных закупок</p>
            </div>
          ) : (
            filteredProcurements.map((procurement) => (
              <div
                key={procurement.id}
                className={`chat-item ${currentChat === procurement.id ? 'active' : ''}`}
                onClick={() => handleChatClick(procurement)}
              >
                <div
                  className="chat-avatar"
                  style={{ backgroundColor: getAvatarColor(procurement.title) }}
                >
                  {getInitials(procurement.title)}
                </div>
                <div className="chat-info">
                  <div className="chat-header">
                    <span className="chat-title">{procurement.title}</span>
                    <span className="chat-time">
                      {formatTime(procurement.updated_at)}
                    </span>
                  </div>
                  <div className="chat-message">
                    {procurement.description
                      ? firstWords(procurement.description, 16)
                      : `${procurement.participant_count || 0} участников • ${procurement.progress || 0}%`}
                  </div>
                </div>
                {unreadCounts[procurement.id] > 0 && (
                  <div className="chat-badge">{unreadCounts[procurement.id]}</div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {sidebarTab === 'cabinet' && <div className="sidebar-spacer" />}

      {sidebarTab === 'settings' && <div className="sidebar-spacer" />}

      {user && sidebarTab !== 'settings' && (
        <div
          className="sidebar-footer"
          style={{ cursor: 'pointer' }}
          onClick={() => handleTabChange('settings')}
          title="Настройки"
        >
          <div
            className="sidebar-footer-avatar"
            style={{ backgroundColor: getAvatarColor(user.first_name || '') }}
          >
            {getInitials(user.first_name, user.last_name)}
          </div>
          <div className="sidebar-footer-info">
            <span className="sidebar-footer-name">{user.first_name} {user.last_name || ''}</span>
          </div>
        </div>
      )}
    </aside>
    </>
  );
}

export default Sidebar;
