import { useState, useEffect } from 'react'
import Head from 'next/head'

const styles = `
.container { max-width: 960px; margin: 0 auto; padding: 32px 16px; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px; }
.header h1 { font-size: 24px; }
.btn { padding: 9px 18px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-primary { background: #2563eb; color: #fff; }
.btn-secondary { background: #64748b; color: #fff; }
.btn-danger { background: #ef4444; color: #fff; }
.card { background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.card h2 { font-size: 16px; margin-bottom: 8px; }
.card p { color: #64748b; font-size: 14px; }
.login-wrap { display: flex; align-items: center; justify-content: center; min-height: 80vh; }
.login-card { background: #fff; border-radius: 8px; padding: 40px; width: 360px; box-shadow: 0 2px 12px rgba(0,0,0,.1); }
.login-card h2 { margin-bottom: 8px; text-align: center; }
.login-card .subtitle { color: #64748b; font-size: 13px; margin-bottom: 20px; text-align: center; }
.login-card input { width: 100%; padding: 10px 12px; margin-bottom: 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 15px; box-sizing: border-box; }
.error { color: #dc2626; font-size: 13px; margin-bottom: 10px; }
.info { color: #2563eb; font-size: 13px; margin-bottom: 10px; }
.btn-link { background: none; border: none; color: #2563eb; cursor: pointer; font-size: 13px; padding: 0; text-decoration: underline; }
`

export default function HomePage() {
  const [token, setToken] = useState(null)
  const [user, setUser] = useState(null)
  const [purchases, setPurchases] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // OTP login flow: 'phone' → 'otp'
  const [step, setStep] = useState('phone')
  const [phone, setPhone] = useState('')
  const [maskedEmail, setMaskedEmail] = useState('')
  const [otp, setOtp] = useState('')

  useEffect(() => {
    const t = localStorage.getItem('token')
    if (t) {
      setToken(t)
      fetchUser(t)
    }
  }, [])

  async function fetchUser(t) {
    try {
      const res = await fetch('/api/v1/auth/validate', {
        headers: { Authorization: `Bearer ${t}` },
      })
      if (!res.ok) throw new Error()
      const data = await res.json()
      setUser(data.data || data)
      fetchPurchases(t)
    } catch {
      localStorage.removeItem('token')
      setToken(null)
    }
  }

  async function fetchPurchases(t) {
    try {
      const res = await fetch('/api/v1/purchases/list', {
        headers: { Authorization: `Bearer ${t}` },
      })
      if (res.ok) {
        const data = await res.json()
        setPurchases(Array.isArray(data) ? data : (data.data || []))
      }
    } catch {}
  }

  async function handlePhoneSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.message || 'Failed to send OTP. Please try again.')
        return
      }
      setMaskedEmail(data.data?.maskedEmail || data.maskedEmail || '')
      setStep('otp')
    } catch {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function handleOtpSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/v1/auth/login/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, otp }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.message || 'Invalid or expired code. Please try again.')
        return
      }
      const accessToken = data.data?.accessToken || data.data?.access_token || data.accessToken || data.access_token
      if (!accessToken) {
        setError('Authentication failed. Please try again.')
        return
      }
      localStorage.setItem('token', accessToken)
      setToken(accessToken)
      setStep('phone')
      setPhone('')
      setOtp('')
      fetchUser(accessToken)
    } catch {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function handleResend() {
    setError('')
    try {
      await fetch('/api/v1/auth/resend-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, context: 'login' }),
      })
    } catch {}
  }

  function handleLogout() {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
    setPurchases([])
    setStep('phone')
    setPhone('')
    setOtp('')
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
            <h1>Welcome, {user.email || user.phone || user.username || 'User'}</h1>
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
            {step === 'phone' ? (
              <>
                <h2>Sign In</h2>
                <p className="subtitle">Enter your phone number to receive a one-time code</p>
                {error && <div className="error">{error}</div>}
                <form onSubmit={handlePhoneSubmit}>
                  <input
                    type="tel"
                    placeholder="+79001234567"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    required
                  />
                  <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: '100%' }}>
                    {loading ? 'Sending…' : 'Send Code'}
                  </button>
                </form>
              </>
            ) : (
              <>
                <h2>Enter Code</h2>
                <p className="subtitle">
                  {maskedEmail
                    ? `A code was sent to ${maskedEmail}`
                    : `A code was sent to your registered email`}
                </p>
                {error && <div className="error">{error}</div>}
                <form onSubmit={handleOtpSubmit}>
                  <input
                    type="text"
                    placeholder="Enter OTP code"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                    autoComplete="one-time-code"
                    required
                  />
                  <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: '100%' }}>
                    {loading ? 'Verifying…' : 'Confirm'}
                  </button>
                </form>
                <div style={{ marginTop: 12, display: 'flex', justifyContent: 'space-between' }}>
                  <button className="btn-link" onClick={() => { setStep('phone'); setError('') }}>
                    ← Change phone
                  </button>
                  <button className="btn-link" onClick={handleResend}>
                    Resend code
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  )
}
