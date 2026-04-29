import { useState } from 'react'
import { login } from '../api'

const styles = {
  page: {
    minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  },
  card: {
    background: '#fff', borderRadius: '16px', padding: '40px',
    width: '100%', maxWidth: '380px', boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
  },
  title: { fontSize: '24px', fontWeight: '700', color: '#1e293b', marginBottom: '8px', textAlign: 'center' },
  subtitle: { fontSize: '14px', color: '#64748b', textAlign: 'center', marginBottom: '28px' },
  label: { fontSize: '13px', fontWeight: '600', color: '#475569', display: 'block', marginBottom: '6px' },
  input: {
    width: '100%', padding: '12px 14px', border: '1px solid #e2e8f0',
    borderRadius: '8px', fontSize: '14px', outline: 'none', marginBottom: '16px',
  },
  btn: {
    width: '100%', padding: '13px', background: '#3b82f6', color: '#fff',
    border: 'none', borderRadius: '8px', fontSize: '15px', fontWeight: '600',
    cursor: 'pointer', marginTop: '4px',
  },
  error: { color: '#ef4444', fontSize: '13px', textAlign: 'center', marginTop: '12px' },
  hints: { marginTop: '24px', padding: '16px', background: '#f8fafc', borderRadius: '8px', fontSize: '12px', color: '#64748b' },
  hint: { marginBottom: '4px' },
}

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await login(username, password)
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      onLogin(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Неверный логин или пароль')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.title}>Каталог продуктов</div>
        <div style={styles.subtitle}>Войдите в систему для продолжения</div>
        <form onSubmit={handleSubmit}>
          <label style={styles.label}>Логин</label>
          <input
            style={styles.input}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Введите логин"
            autoFocus
          />
          <label style={styles.label}>Пароль</label>
          <input
            style={styles.input}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Введите пароль"
          />
          <button style={styles.btn} disabled={loading}>
            {loading ? 'Вход...' : 'Войти'}
          </button>
          {error && <div style={styles.error}>{error}</div>}
        </form>
        <div style={styles.hints}>
          <div style={styles.hint}><b>admin</b> / admin123 — Администратор</div>
          <div style={styles.hint}><b>advanced</b> / advanced123 — Продвинутый</div>
          <div style={styles.hint}><b>user</b> / user123 — Простой пользователь</div>
        </div>
      </div>
    </div>
  )
}
