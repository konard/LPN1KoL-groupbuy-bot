import { useState, useEffect } from 'react'
import AuthPage from './pages/AuthPage.jsx'
import ChatPage from './pages/ChatPage.jsx'
import ProcurementsPage from './pages/ProcurementsPage.jsx'
import PaymentsPage from './pages/PaymentsPage.jsx'
import ProfilePage from './pages/ProfilePage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'

const styles = `
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #f0f2f5; color: #333; }
`

const PAGES = {
  dashboard: DashboardPage,
  procurements: ProcurementsPage,
  chat: ChatPage,
  payments: PaymentsPage,
  profile: ProfilePage,
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('token'))
  const [user, setUser] = useState(null)
  const [page, setPage] = useState('dashboard')

  useEffect(() => {
    if (token) {
      import('./api.js').then(({ api }) =>
        api.me().then(setUser).catch(() => { localStorage.removeItem('token'); setToken(null) })
      )
    }
  }, [token])

  useEffect(() => {
    function onLogout() {
      setToken(null)
      setUser(null)
    }
    window.addEventListener('auth:logout', onLogout)
    return () => window.removeEventListener('auth:logout', onLogout)
  }, [])

  function handleLogin(newToken) {
    localStorage.setItem('token', newToken)
    setToken(newToken)
    setPage('dashboard')
  }

  function handleLogout() {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
  }

  if (!token || !user) {
    return (
      <>
        <style>{styles}</style>
        <AuthPage onLogin={handleLogin} />
      </>
    )
  }

  const PageComponent = PAGES[page] || DashboardPage

  return (
    <>
      <style>{styles}</style>
      <PageComponent user={user} onLogout={handleLogout} onNavigate={setPage} />
    </>
  )
}
