import { useState, useEffect } from 'react'
import AuthPage from './pages/AuthPage.jsx'
import ChatPage from './pages/ChatPage.jsx'
import ProcurementsPage from './pages/ProcurementsPage.jsx'

const styles = `
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #f0f2f5; color: #333; }
`

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('token'))
  const [user, setUser] = useState(null)
  const [page, setPage] = useState('procurements')

  useEffect(() => {
    if (token) {
      import('./api.js').then(({ api }) =>
        api.me().then(setUser).catch(() => { localStorage.removeItem('token'); setToken(null) })
      )
    }
  }, [token])

  function handleLogin(newToken) {
    localStorage.setItem('token', newToken)
    setToken(newToken)
  }

  function handleLogout() {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
  }

  return (
    <>
      <style>{styles}</style>
      {token && user
        ? page === 'chat'
          ? <ChatPage user={user} onLogout={handleLogout} onNavigate={setPage} />
          : <ProcurementsPage user={user} onLogout={handleLogout} onNavigate={setPage} />
        : <AuthPage onLogin={handleLogin} />
      }
    </>
  )
}
