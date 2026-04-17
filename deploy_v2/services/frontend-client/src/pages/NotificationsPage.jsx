import { useState, useEffect } from 'react'
import { api } from '../api.js'

const s = {
  wrap: { display: 'flex', flexDirection: 'column', height: '100vh' },
  header: { background: '#1a1a2e', color: '#fff', padding: '1rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  nav: { display: 'flex', gap: '1rem', alignItems: 'center' },
  navBtn: (active) => ({ background: active ? '#007bff' : 'transparent', color: '#fff', border: '1px solid #007bff', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer', fontSize: '.9rem' }),
  logoutBtn: { background: 'none', border: '1px solid #a8d8ea', color: '#a8d8ea', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer' },
  main: { flex: 1, padding: '1.5rem', overflowY: 'auto', background: '#f0f2f5' },
  card: { background: '#fff', borderRadius: 8, padding: '1.5rem', maxWidth: 720, margin: '0 auto', boxShadow: '0 2px 8px rgba(0,0,0,.08)' },
  row: (read) => ({ padding: '.75rem .5rem', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', opacity: read ? .6 : 1 }),
  title: { fontWeight: 700, marginBottom: '.25rem' },
  body: { fontSize: '.9rem', color: '#555' },
  meta: { fontSize: '.75rem', color: '#999', marginTop: '.25rem' },
  kindBadge: (kind) => ({ display: 'inline-block', padding: '.1rem .4rem', borderRadius: 3, fontSize: '.7rem', fontWeight: 700, marginRight: '.4rem',
    background: {system:'#e9ecef',procurement:'#d1ecf1',payment:'#d4edda',vote:'#fff3cd',invitation:'#f8d7da',complaint:'#f5c6cb'}[kind] || '#e9ecef' }),
  btn: { padding: '.3rem .8rem', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '.8rem', fontWeight: 600, background: '#007bff', color: '#fff' },
  topbar: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' },
  empty: { color: '#999', textAlign: 'center', padding: '2rem' },
}

export default function NotificationsPage({ user, onNavigate, onLogout }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  function load() {
    setLoading(true)
    api.listNotifications({ limit: 100 }).then(setItems).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  function markAll() {
    api.markAllNotificationsRead().then(load)
  }
  function markOne(id) {
    api.markNotificationRead(id).then(load)
  }

  return (
    <div style={s.wrap}>
      <div style={s.header}>
        <span>GroupBuy &mdash; <strong>{user.username}</strong></span>
        <div style={s.nav}>
          <button style={s.navBtn(false)} onClick={() => onNavigate('dashboard')}>Dashboard</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('procurements')}>Procurements</button>
          <button style={s.navBtn(true)}>Notifications</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('profile')}>Profile</button>
          <button style={s.logoutBtn} onClick={onLogout}>Logout</button>
        </div>
      </div>
      <div style={s.main}>
        <div style={s.card}>
          <div style={s.topbar}>
            <h2 style={{ fontSize: '1.25rem' }}>Notifications</h2>
            <button style={s.btn} onClick={markAll}>Mark all read</button>
          </div>
          {loading && <p style={s.empty}>Loading…</p>}
          {!loading && items.length === 0 && <p style={s.empty}>No notifications yet.</p>}
          {items.map(n => (
            <div key={n.id} style={s.row(n.is_read)}>
              <div style={{ flex: 1 }}>
                <div style={s.title}>
                  <span style={s.kindBadge(n.kind)}>{n.kind}</span>
                  {n.title || '(untitled)'}
                </div>
                <div style={s.body}>{n.body}</div>
                <div style={s.meta}>{new Date(n.created_at).toLocaleString()}</div>
              </div>
              {!n.is_read && (
                <button style={s.btn} onClick={() => markOne(n.id)}>Read</button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
