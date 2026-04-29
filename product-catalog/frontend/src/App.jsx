import { useState, useEffect } from 'react'
import LoginPage from './pages/LoginPage.jsx'
import CatalogPage from './pages/CatalogPage.jsx'
import CategoriesPage from './pages/CategoriesPage.jsx'
import AdminPage from './pages/AdminPage.jsx'
import { getMe } from './api.js'
import { useRole } from './hooks/useRole.js'

const navStyles = {
  nav: {
    background: '#1e293b',
    padding: '0 24px',
    display: 'flex',
    alignItems: 'center',
    gap: '0',
    minHeight: '56px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
  },
  brand: { color: '#f8fafc', fontWeight: '700', fontSize: '17px', marginRight: '32px', whiteSpace: 'nowrap' },
  navBtn: (active) => ({
    background: 'none',
    border: 'none',
    color: active ? '#60a5fa' : '#94a3b8',
    fontSize: '14px',
    fontWeight: active ? '700' : '500',
    cursor: 'pointer',
    padding: '18px 14px',
    borderBottom: active ? '2px solid #60a5fa' : '2px solid transparent',
    transition: 'color 0.2s',
    whiteSpace: 'nowrap',
  }),
  spacer: { flex: 1 },
  userInfo: { color: '#94a3b8', fontSize: '13px', marginRight: '16px' },
  roleBadge: (role) => {
    const map = { admin: '#fef3c7', advanced_user: '#dbeafe', simple_user: '#f1f5f9' }
    const colorMap = { admin: '#92400e', advanced_user: '#1d4ed8', simple_user: '#475569' }
    return {
      display: 'inline-block', padding: '2px 10px', borderRadius: '20px',
      fontSize: '11px', fontWeight: '700',
      background: map[role] || '#f1f5f9',
      color: colorMap[role] || '#475569',
      marginLeft: '8px',
    }
  },
  logoutBtn: {
    background: '#dc2626',
    border: 'none',
    color: '#fff',
    fontSize: '13px',
    fontWeight: '600',
    cursor: 'pointer',
    padding: '7px 14px',
    borderRadius: '6px',
  },
}

const ROLE_LABELS = { admin: 'Администратор', advanced_user: 'Продвинутый', simple_user: 'Простой' }

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState('catalog')
  const roles = useRole(user)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) { setLoading(false); return }
    getMe()
      .then(({ data }) => setUser(data))
      .catch(() => { localStorage.clear() })
      .finally(() => setLoading(false))
  }, [])

  function handleLogin(loginData) {
    setUser({ role: loginData.role })
    getMe().then(({ data }) => setUser(data)).catch(() => {})
  }

  function handleLogout() {
    localStorage.clear()
    setUser(null)
    setPage('catalog')
  }

  if (loading) return null

  if (!user) return <LoginPage onLogin={handleLogin} />

  return (
    <div>
      <nav style={navStyles.nav}>
        <span style={navStyles.brand}>Каталог продуктов</span>
        <button style={navStyles.navBtn(page === 'catalog')} onClick={() => setPage('catalog')}>Каталог</button>
        {roles.canManageCategories && (
          <button style={navStyles.navBtn(page === 'categories')} onClick={() => setPage('categories')}>Категории</button>
        )}
        {roles.isAdmin && (
          <button style={navStyles.navBtn(page === 'admin')} onClick={() => setPage('admin')}>Пользователи</button>
        )}
        <span style={navStyles.spacer} />
        <span style={navStyles.userInfo}>
          {user.username}
          <span style={navStyles.roleBadge(user.role)}>{ROLE_LABELS[user.role] || user.role}</span>
        </span>
        <button style={navStyles.logoutBtn} onClick={handleLogout}>Выйти</button>
      </nav>

      {page === 'catalog' && <CatalogPage user={user} />}
      {page === 'categories' && roles.canManageCategories && <CategoriesPage />}
      {page === 'admin' && roles.isAdmin && <AdminPage currentUserId={user.id} />}
    </div>
  )
}
