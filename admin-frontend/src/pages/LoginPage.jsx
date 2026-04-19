import { useState } from 'react'
import { api } from '../api.js'

const styles = `
.login-wrap { display: flex; align-items: center; justify-content: center; min-height: 100vh; }
.login-card { background: #fff; border-radius: 8px; padding: 40px; width: 360px; box-shadow: 0 2px 12px rgba(0,0,0,.1); }
.login-card h1 { font-size: 22px; margin-bottom: 24px; text-align: center; }
.login-card input { width: 100%; padding: 10px 12px; margin-bottom: 14px; border: 1px solid #ddd; border-radius: 4px; font-size: 15px; }
.login-card button { width: 100%; padding: 11px; background: #2563eb; color: #fff; border: none; border-radius: 4px; font-size: 15px; cursor: pointer; }
.login-card button:hover { background: #1d4ed8; }
.error { color: #dc2626; font-size: 13px; margin-bottom: 10px; }
`

export default function LoginPage({ onLogin }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const data = await api.login({ email, password })
      onLogin(data.access_token)
    } catch (err) {
      setError('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <style>{styles}</style>
      <div className="login-wrap">
        <div className="login-card">
          <h1>Admin Panel</h1>
          {error && <div className="error">{error}</div>}
          <form onSubmit={handleSubmit}>
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
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
    </>
  )
}
