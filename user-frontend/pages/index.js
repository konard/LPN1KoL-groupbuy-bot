import { useState, useEffect } from 'react'
import Head from 'next/head'

const styles = `
.container { max-width: 960px; margin: 0 auto; padding: 32px 16px; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px; }
.header h1 { font-size: 24px; }
.btn { padding: 9px 18px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-primary { background: #2563eb; color: #fff; }
.btn-danger { background: #ef4444; color: #fff; }
.card { background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.card h2 { font-size: 16px; margin-bottom: 8px; }
.card p { color: #64748b; font-size: 14px; }
.login-wrap { display: flex; align-items: center; justify-content: center; min-height: 80vh; }
.login-card { background: #fff; border-radius: 8px; padding: 40px; width: 360px; box-shadow: 0 2px 12px rgba(0,0,0,.1); }
.login-card h2 { margin-bottom: 20px; text-align: center; }
.login-card input { width: 100%; padding: 10px 12px; margin-bottom: 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 15px; }
.error { color: #dc2626; font-size: 13px; margin-bottom: 10px; }
`

export default function HomePage() {
  const [token, setToken] = useState(null)
  const [user, setUser] = useState(null)
  const [purchases, setPurchases] = useState([])
  const [loginForm, setLoginForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const t = localStorage.getItem('token')
    if (t) {
      setToken(t)
      fetchUser(t)
    }
  }, [])

  async function fetchUser(t) {
    try {
      const res = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${t}` },
      })
      if (!res.ok) throw new Error()
      const data = await res.json()
      setUser(data)
      fetchPurchases(t)
    } catch {
      localStorage.removeItem('token')
      setToken(null)
    }
  }

  async function fetchPurchases(t) {
    try {
      const res = await fetch('/api/purchases/', {
        headers: { Authorization: `Bearer ${t}` },
      })
      if (res.ok) setPurchases(await res.json())
    } catch {}
  }

  async function handleLogin(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm),
      })
      if (!res.ok) throw new Error()
      const data = await res.json()
      localStorage.setItem('token', data.access_token)
      setToken(data.access_token)
      fetchUser(data.access_token)
    } catch {
      setError('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  function handleLogout() {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
    setPurchases([])
  }

  return (
    <>
      <Head>
        <title>GroupBuy — Personal Account</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>
      <style>{styles}</style>
      {token && user ? (
        <div className="container">
          <div className="header">
            <h1>Welcome, {user.email || user.username || 'User'}</h1>
            <button className="btn btn-danger" onClick={handleLogout}>Logout</button>
          </div>
          <h2 style={{ marginBottom: 16 }}>Your Purchases</h2>
          {purchases.length === 0 ? (
            <div className="card"><p>No purchases yet.</p></div>
          ) : (
            purchases.map((p) => (
              <div className="card" key={p.id}>
                <h2>{p.title || `Purchase #${p.id}`}</h2>
                <p>Status: {p.status}</p>
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="login-wrap">
          <div className="login-card">
            <h2>Sign In</h2>
            {error && <div className="error">{error}</div>}
            <form onSubmit={handleLogin}>
              <input
                type="email"
                placeholder="Email"
                value={loginForm.email}
                onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
                required
              />
              <input
                type="password"
                placeholder="Password"
                value={loginForm.password}
                onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                required
              />
              <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: '100%' }}>
                {loading ? 'Signing in…' : 'Sign In'}
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
