import { useState } from 'react'
import LoginPage from './pages/LoginPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'

const styles = `
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #f5f5f5; color: #333; }
`

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('admin_token'))

  function handleLogin(newToken) {
    localStorage.setItem('admin_token', newToken)
    setToken(newToken)
  }

  function handleLogout() {
    localStorage.removeItem('admin_token')
    setToken(null)
  }

  return (
    <>
      <style>{styles}</style>
      {token
        ? <DashboardPage onLogout={handleLogout} />
        : <LoginPage onLogin={handleLogin} />
      }
    </>
  )
}
