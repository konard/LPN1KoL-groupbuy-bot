import { useState } from 'react'
import { api } from '../api.js'

const s = {
  wrap: { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#1a1a2e' },
  box: { background: '#fff', borderRadius: 8, padding: '2.5rem', width: 360, boxShadow: '0 4px 20px rgba(0,0,0,.3)' },
  title: { marginBottom: '1.5rem', color: '#1a1a2e', fontSize: '1.4rem' },
  label: { display: 'block', marginBottom: '.3rem', fontWeight: 600, fontSize: '.9rem' },
  input: { width: '100%', padding: '.6rem', border: '1px solid #ccc', borderRadius: 4, marginBottom: '1rem', fontSize: '1rem' },
  btn: { width: '100%', padding: '.75rem', background: '#007bff', color: '#fff', border: 'none', borderRadius: 4, fontSize: '1rem', cursor: 'pointer', marginBottom: '.5rem' },
  link: { background: 'none', border: 'none', color: '#007bff', cursor: 'pointer', width: '100%', textAlign: 'center', display: 'block', marginTop: '.5rem' },
  error: { color: '#dc3545', marginBottom: '1rem', fontSize: '.9rem' },
  hint: { color: '#6c757d', marginBottom: '1rem', fontSize: '.9rem' },
}

export default function AuthPage({ onLogin }) {
  const [mode, setMode] = useState('login') // 'login' | 'register' | 'otp'
  const [form, setForm] = useState({ username: '', phone: '', email: '', password: '', code: '' })
  const [emailHint, setEmailHint] = useState('')
  const [error, setError] = useState('')

  function set(field) {
    return (e) => setForm(f => ({ ...f, [field]: e.target.value }))
  }

  async function submit(e) {
    e.preventDefault()
    setError('')
    try {
      if (mode === 'otp') {
        const { access_token } = await api.verifyCode(form.phone, form.code)
        onLogin(access_token)
      } else if (mode === 'login') {
        const res = await api.login(form.phone, form.password)
        setEmailHint(res.email_hint || '')
        setMode('otp')
      } else {
        await api.register(form.username, form.phone, form.email, form.password)
        const res = await api.login(form.phone, form.password)
        setEmailHint(res.email_hint || '')
        setMode('otp')
      }
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div style={s.wrap}>
      <div style={s.box}>
        <h2 style={s.title}>
          GroupBuy —{' '}
          {mode === 'login' ? 'Sign In' : mode === 'register' ? 'Register' : 'Enter Code'}
        </h2>
        {error && <p style={s.error}>{error}</p>}
        <form onSubmit={submit}>
          {mode === 'otp' ? (
            <>
              <p style={s.hint}>
                A verification code was sent to {emailHint}. Please check your email.
              </p>
              <label style={s.label}>Verification Code</label>
              <input
                style={s.input}
                value={form.code}
                onChange={set('code')}
                required
                autoFocus
                placeholder="6-digit code"
                maxLength={6}
              />
            </>
          ) : (
            <>
              {mode === 'register' && (
                <>
                  <label style={s.label}>Username</label>
                  <input style={s.input} value={form.username} onChange={set('username')} required />
                </>
              )}
              <label style={s.label}>Phone</label>
              <input
                style={s.input}
                value={form.phone}
                onChange={set('phone')}
                required
                autoFocus
                placeholder="+71234567890"
              />
              {mode === 'register' && (
                <>
                  <label style={s.label}>Email</label>
                  <input style={s.input} type="email" value={form.email} onChange={set('email')} required />
                </>
              )}
              <label style={s.label}>Password</label>
              <input style={s.input} type="password" value={form.password} onChange={set('password')} required />
            </>
          )}
          <button style={s.btn} type="submit">
            {mode === 'otp' ? 'Verify' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>
        {mode !== 'otp' && (
          <button
            style={s.link}
            onClick={() => {
              setMode(m => m === 'login' ? 'register' : 'login')
              setError('')
            }}
          >
            {mode === 'login' ? 'No account? Register' : 'Already have an account? Sign In'}
          </button>
        )}
        {mode === 'otp' && (
          <button
            style={s.link}
            onClick={() => { setMode('login'); setError('') }}
          >
            Back to Sign In
          </button>
        )}
      </div>
    </div>
  )
}
