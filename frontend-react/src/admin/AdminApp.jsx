/**
 * Admin App Component
 * Main entry point for admin panel routing
 */
import React, { useEffect, useState } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useAdminStore } from './store/adminStore';

import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import UsersPage from './pages/UsersPage';
import ProcurementsPage from './pages/ProcurementsPage';
import PaymentsPage from './pages/PaymentsPage';
import CategoriesPage from './pages/CategoriesPage';
import MessagesPage from './pages/MessagesPage';
import ReportsPage from './pages/ReportsPage';
import AdminChatPage from './pages/AdminChatPage';
import ActivityLogPage from './pages/ActivityLogPage';
import ReputationPage from './pages/ReputationPage';
import ComplaintsPage from './pages/ComplaintsPage';
import EscrowPage from './pages/EscrowPage';
import SearchAnalyticsPage from './pages/SearchAnalyticsPage';

function ProtectedRoute({ children }) {
  const { isAuthenticated, checkAuth } = useAdminStore();
  const [checking, setChecking] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    checkAuth().then((isAuth) => {
      if (cancelled) return;
      if (!isAuth) {
        navigate('/admin-panel/login');
      }
      setChecking(false);
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (checking) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: '#f8fafc'
      }}>
        <div>Загрузка...</div>
      </div>
    );
  }

  return isAuthenticated ? children : <Navigate to="/admin-panel/login" />;
}

export default function AdminApp() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="users"
        element={
          <ProtectedRoute>
            <UsersPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="procurements"
        element={
          <ProtectedRoute>
            <ProcurementsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="payments"
        element={
          <ProtectedRoute>
            <PaymentsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="categories"
        element={
          <ProtectedRoute>
            <CategoriesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="messages"
        element={
          <ProtectedRoute>
            <MessagesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="reports"
        element={
          <ProtectedRoute>
            <ReportsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="chat"
        element={
          <ProtectedRoute>
            <AdminChatPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="activity"
        element={
          <ProtectedRoute>
            <ActivityLogPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="reputation"
        element={
          <ProtectedRoute>
            <ReputationPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="complaints"
        element={
          <ProtectedRoute>
            <ComplaintsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="escrow"
        element={
          <ProtectedRoute>
            <EscrowPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="search-analytics"
        element={
          <ProtectedRoute>
            <SearchAnalyticsPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/admin-panel" />} />
    </Routes>
  );
}
