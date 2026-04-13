import React, { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useStore } from '../store/useStore';
import Sidebar from './Sidebar';
import { BurgerMenuIcon } from './Icons';

function Layout({ children }) {
  const location = useLocation();
  const { user, sidebarOpen, toggleSidebar, closeSidebar, toggleBurgerMenu, loadProcurements, openLoginModal } = useStore();
  const isChatView = location.pathname.startsWith('/chat/');

  useEffect(() => {
    // Always load procurements so guests can browse and the slider is visible.
    // The login modal is shown only when there is no saved userId at all.
    loadProcurements();
    if (!user) {
      const userId = localStorage.getItem('userId');
      if (!userId) {
        openLoginModal();
      }
    }
  }, [user, loadProcurements, openLoginModal]);

  return (
    <div className="app-container">
      <Sidebar />
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={closeSidebar} />
      )}
      <main className="main-content">
        {!isChatView && (
          <header className="header mobile-header">
            <button
              className="btn btn-icon burger-btn"
              aria-label="Menu"
              onClick={toggleBurgerMenu}
            >
              <BurgerMenuIcon />
            </button>
            <h1 className="header-title">GroupBuy</h1>
          </header>
        )}
        {children}
      </main>
    </div>
  );
}

export default Layout;
