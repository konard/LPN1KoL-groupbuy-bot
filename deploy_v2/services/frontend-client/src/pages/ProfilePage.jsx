import { useState, useEffect } from 'react'
import { api } from '../api.js'

const s = {
  wrap: { display: 'flex', flexDirection: 'column', height: '100vh' },
  header: { background: '#1a1a2e', color: '#fff', padding: '1rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  nav: { display: 'flex', gap: '1rem', alignItems: 'center' },
  navBtn: (active) => ({ background: active ? '#007bff' : 'transparent', color: '#fff', border: '1px solid #007bff', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer', fontSize: '.9rem' }),
  logoutBtn: { background: 'none', border: '1px solid #a8d8ea', color: '#a8d8ea', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer' },
  main: { flex: 1, padding: '1.5rem', overflowY: 'auto', background: '#f0f2f5', display: 'flex', justifyContent: 'center' },
  card: { background: '#fff', borderRadius: 8, padding: '2rem', width: '100%', maxWidth: 520, boxShadow: '0 2px 8px rgba(0,0,0,.08)', height: 'fit-content' },
  avatar: { width: 72, height: 72, borderRadius: '50%', background: '#1a1a2e', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '2rem', fontWeight: 700, marginBottom: '1.25rem' },
  infoRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '.6rem 0', borderBottom: '1px solid #f0f0f0' },
  infoLabel: { fontSize: '.9rem', color: '#666', fontWeight: 500 },
  infoValue: { fontSize: '.95rem', fontWeight: 600 },
  badge: (admin) => ({ display: 'inline-block', padding: '.15rem .5rem', borderRadius: 4, fontSize: '.8rem', fontWeight: 600, background: admin ? '#cce5ff' : '#d4edda', color: admin ? '#004085' : '#155724' }),
  sectionTitle: { fontSize: '1rem', fontWeight: 700, margin: '1.5rem 0 .75rem' },
  formRow: { marginBottom: '.8rem' },
  label: { display: 'block', marginBottom: '.25rem', fontSize: '.9rem', fontWeight: 600 },
  input: { width: '100%', padding: '.5rem', border: '1px solid #ccc', borderRadius: 4, fontSize: '.95rem' },
  btn: { padding: '.5rem 1.2rem', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '.9rem', fontWeight: 600, background: '#007bff', color: '#fff' },
  error: { color: '#dc3545', fontSize: '.85rem', marginBottom: '.5rem' },
  success: { color: '#28a745', fontSize: '.85rem', marginBottom: '.5rem' },
}

export default function ProfilePage({ user, onNavigate, onLogout }) {
  const [profile, setProfile] = useState(user)
  const [loading, setLoading] = useState(false)
  const [pwForm, setPwForm] = useState({ current: '', next: '', confirm: '' })
  const [pwError, setPwError] = useState('')
  const [pwSuccess, setPwSuccess] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    api.me().then(setProfile).catch(() => {})
  }, [])

  function handlePwChange(e) {
    e.preventDefault()
    setPwError('')
    setPwSuccess('')
    if (pwForm.next !== pwForm.confirm) { setPwError('Passwords do not match'); return }
    if (pwForm.next.length < 6) { setPwError('Password must be at least 6 characters'); return }
    setSubmitting(true)
    api.changePassword(pwForm.current, pwForm.next)
      .then(() => {
        setPwSuccess('Password changed successfully')
        setPwForm({ current: '', next: '', confirm: '' })
      })
      .catch(e => setPwError(e.message))
      .finally(() => setSubmitting(false))
  }

  const initials = profile?.username ? profile.username.slice(0, 2).toUpperCase() : '?'

  return (
    <div style={s.wrap}>
      <div style={s.header}>
        <span>GroupBuy &mdash; <strong>{user.username}</strong></span>
        <div style={s.nav}>
          <button style={s.navBtn(false)} onClick={() => onNavigate('procurements')}>Procurements</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('chat')}>Chat</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('payments')}>Payments</button>
          <button style={s.navBtn(true)}>Profile</button>
          <button style={s.logoutBtn} onClick={onLogout}>Logout</button>
        </div>
      </div>

      <div style={s.main}>
        <div style={s.card}>
          <div style={s.avatar}>{initials}</div>
          <h2 style={{ fontSize: '1.25rem', marginBottom: '.25rem' }}>{profile?.username}</h2>
          <p style={{ color: '#666', fontSize: '.9rem', marginBottom: '1rem' }}>{profile?.email}</p>

          <div>
            {[
              ['Username', profile?.username],
              ['Email', profile?.email],
              ['Role', <span style={s.badge(profile?.is_admin)}>{profile?.is_admin ? 'Admin' : 'User'}</span>],
              ['Balance', `₽${parseFloat(profile?.balance || 0).toLocaleString()}`],
              ['Status', profile?.is_active ? 'Active' : 'Suspended'],
              ['Member since', profile?.created_at ? new Date(profile.created_at).toLocaleDateString() : '—'],
            ].map(([label, value]) => (
              <div key={label} style={s.infoRow}>
                <span style={s.infoLabel}>{label}</span>
                <span style={s.infoValue}>{value}</span>
              </div>
            ))}
          </div>

          <div style={s.sectionTitle}>Change Password</div>
          {pwError && <p style={s.error}>{pwError}</p>}
          {pwSuccess && <p style={s.success}>{pwSuccess}</p>}
          <form onSubmit={handlePwChange}>
            {[
              ['current', 'Current Password'],
              ['next', 'New Password'],
              ['confirm', 'Confirm New Password'],
            ].map(([field, label]) => (
              <div key={field} style={s.formRow}>
                <label style={s.label}>{label}</label>
                <input style={s.input} type="password" value={pwForm[field]}
                  onChange={e => setPwForm(f => ({ ...f, [field]: e.target.value }))} required />
              </div>
            ))}
            <button type="submit" style={s.btn} disabled={submitting}>
              {submitting ? 'Saving…' : 'Change Password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
