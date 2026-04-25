import { useState, useEffect } from 'react'
import Head from 'next/head'

const styles = `
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #f5f5f5; color: #333; }
.login-wrap { display: flex; align-items: center; justify-content: center; min-height: 100vh; }
.login-card { background: #fff; border-radius: 8px; padding: 40px; width: 360px; box-shadow: 0 2px 12px rgba(0,0,0,.1); }
.login-card h1 { font-size: 22px; margin-bottom: 24px; text-align: center; }
.login-card input { width: 100%; padding: 10px 12px; margin-bottom: 14px; border: 1px solid #ddd; border-radius: 4px; font-size: 15px; }
.login-card button { width: 100%; padding: 11px; background: #2563eb; color: #fff; border: none; border-radius: 4px; font-size: 15px; cursor: pointer; }
.login-card button:hover { background: #1d4ed8; }
.error { color: #dc2626; font-size: 13px; margin-bottom: 10px; }
.admin-layout { display: flex; min-height: 100vh; }
.sidebar { width: 220px; background: #1e293b; color: #e2e8f0; padding: 24px 0; flex-shrink: 0; }
.sidebar h2 { font-size: 16px; padding: 0 20px 20px; border-bottom: 1px solid #334155; }
.sidebar nav a { display: block; padding: 12px 20px; color: #94a3b8; text-decoration: none; cursor: pointer; }
.sidebar nav a:hover, .sidebar nav a.active { color: #fff; background: #334155; }
.main { flex: 1; padding: 32px; overflow: auto; }
.main h1 { font-size: 22px; margin-bottom: 24px; }
.stat-row { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.stat-card { flex: 1; min-width: 140px; background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.07); }
.stat-card .label { font-size: 13px; color: #64748b; margin-bottom: 8px; }
.stat-card .value { font-size: 28px; font-weight: 700; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.07); }
th, td { text-align: left; padding: 12px 16px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
th { background: #f8fafc; font-weight: 600; }
.logout-btn { float: right; padding: 8px 16px; background: #ef4444; color: #fff; border: none; border-radius: 4px; cursor: pointer; margin-bottom: 16px; }
`

const SECTIONS = ['Users', 'Purchases', 'Payments']
const BASE = '/api/admin'

async function apiFetch(path, options = {}) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('admin_token') : null
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

function LoginForm({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })
      onLogin(data.token)
    } catch {
      setError('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <h1>Admin Panel</h1>
        {error && <div className="error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button type="submit" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}

function Dashboard({ onLogout }) {
  const [section, setSection] = useState('Users')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    const path = section === 'Users' ? '/users'
      : section === 'Purchases' ? '/purchases'
      : '/payments'
    apiFetch(path)
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false))
  }, [section])

  const columns = rows.length > 0 ? Object.keys(rows[0]) : []

  return (
    <div className="admin-layout">
      <aside className="sidebar">
        <h2>GroupBuy Admin</h2>
        <nav>
          {SECTIONS.map((s) => (
            <a
              key={s}
              className={section === s ? 'active' : ''}
              onClick={() => setSection(s)}
            >
              {s}
            </a>
          ))}
        </nav>
      </aside>
      <main className="main">
        <button className="logout-btn" onClick={onLogout}>Logout</button>
        <h1>{section}</h1>
        {loading ? (
          <p>Loading…</p>
        ) : rows.length === 0 ? (
          <p>No data available.</p>
        ) : (
          <table>
            <thead>
              <tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  {columns.map((c) => <td key={c}>{String(row[c] ?? '')}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </main>
    </div>
  )
}

export default function AdminPanelPage() {
  const [token, setToken] = useState(null)

  useEffect(() => {
    const t = localStorage.getItem('admin_token')
    if (t) setToken(t)
  }, [])

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
      <Head>
        <title>GroupBuy — Admin Panel</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>
      <style>{styles}</style>
      {token
        ? <Dashboard onLogout={handleLogout} />
        : <LoginForm onLogin={handleLogin} />
      }
    </>
  )
}
