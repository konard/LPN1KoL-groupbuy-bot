import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useStore } from './store/useStore';
import { loadWasm } from './services/wasm';
import Layout from './components/Layout';
import ChatList from './components/ChatList';
import ChatView from './components/ChatView';
import Cabinet from './components/Cabinet';
import SettingsPage from './components/SettingsPage';
import UnderDevelopmentPage from './components/UnderDevelopmentPage';
import LoginModal from './components/LoginModal';
import ProcurementModal from './components/ProcurementModal';
import CreateProcurementModal from './components/CreateProcurementModal';
import DepositModal from './components/DepositModal';
import Toast from './components/Toast';

// Admin Panel
import AdminApp from './admin/AdminApp';
import BannedPage from './components/BannedPage';

// Pre-load WASM module for high-performance processing
loadWasm();

function MainApp() {
  const { user, loadUser, theme, setTheme } = useStore();

  useEffect(() => {
    // Respect system preference (prefers-color-scheme) as default
    const savedTheme = localStorage.getItem('theme');
    let initialTheme;
    if (savedTheme) {
      initialTheme = savedTheme;
    } else {
      // Check system preference
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      initialTheme = prefersDark ? 'dark' : 'light';
    }
    setTheme(initialTheme);
    document.documentElement.setAttribute('data-theme', initialTheme);

    // Try to load user from storage.
    // Prefer the integer coreUserId for the core API call; fall back to UUID
    // only if coreUserId has not yet been resolved (first login before the
    // async getUserByEmail call finished).
    const userId = localStorage.getItem('userId');
    const coreUserId = localStorage.getItem('coreUserId');
    if (userId) {
      loadUser(coreUserId || userId);
    }
  }, [loadUser, setTheme]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Listen for system theme changes when no explicit preference is saved
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e) => {
      // Only follow system preference if user hasn't set one explicitly
      if (!localStorage.getItem('theme')) {
        const newTheme = e.matches ? 'dark' : 'light';
        setTheme(newTheme);
      }
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [setTheme]);

  return (
    <>
      <Layout>
        <Routes>
          <Route path="/" element={<Cabinet />} />
          <Route path="/chat/:procurementId" element={<ChatView />} />
          <Route path="/cabinet" element={<Cabinet />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/in-development" element={<UnderDevelopmentPage />} />
          <Route path="/banned" element={<BannedPage />} />
        </Routes>
      </Layout>
      <LoginModal />
      <ProcurementModal />
      <CreateProcurementModal />
      <DepositModal />
      <Toast />
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Admin Panel Routes */}
        <Route path="/admin-panel/*" element={<AdminApp />} />

        {/* Main App Routes */}
        <Route path="/*" element={<MainApp />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
