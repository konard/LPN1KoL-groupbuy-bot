import { useState, useEffect } from 'react'
import { api } from '../api.js'

const s = {
  wrap: { display: 'flex', flexDirection: 'column', height: '100vh' },
  header: { background: '#1a1a2e', color: '#fff', padding: '1rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  nav: { display: 'flex', gap: '1rem', alignItems: 'center' },
  navBtn: (active) => ({ background: active ? '#007bff' : 'transparent', color: '#fff', border: '1px solid #007bff', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer', fontSize: '.9rem' }),
  logoutBtn: { background: 'none', border: '1px solid #a8d8ea', color: '#a8d8ea', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer' },
  main: { flex: 1, padding: '1.5rem', overflowY: 'auto', background: '#f0f2f5' },
  statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' },
  statCard: (color) => ({ background: '#fff', borderRadius: 8, padding: '1.25rem', boxShadow: '0 2px 4px rgba(0,0,0,.08)', borderLeft: `4px solid ${color}` }),
  statValue: { fontSize: '1.8rem', fontWeight: 700, marginBottom: '.25rem' },
  statLabel: { fontSize: '.85rem', color: '#666' },
  section: { background: '#fff', borderRadius: 8, padding: '1.25rem', boxShadow: '0 2px 4px rgba(0,0,0,.08)', marginBottom: '1rem' },
  sectionTitle: { fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', borderBottom: '1px solid #f0f0f0', paddingBottom: '.5rem' },
  procRow: { display: 'flex', alignItems: 'center', gap: '.75rem', padding: '.6rem 0', borderBottom: '1px solid #f5f5f5' },
  badge: (status) => {
    const colors = { draft: '#6c757d', active: '#28a745', stopped: '#fd7e14', payment: '#007bff', completed: '#20c997', cancelled: '#dc3545' }
    return { display: 'inline-block', padding: '.15rem .5rem', borderRadius: 4, fontSize: '.75rem', fontWeight: 600, background: (colors[status] || '#999') + '22', color: colors[status] || '#999' }
  },
  progress: { background: '#e9ecef', borderRadius: 4, height: 6, flex: 1 },
  progressBar: (pct) => ({ background: '#007bff', height: 6, borderRadius: 4, width: `${Math.min(pct, 100)}%` }),
  btn: { padding: '.4rem .9rem', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '.85rem', background: '#007bff', color: '#fff' },
}

export default function DashboardPage({ user, onNavigate, onLogout }) {
  const [procurements, setProcurements] = useState([])
  const [payments, setPayments] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.listProcurements({ limit: 100 }),
      api.listPayments(),
    ]).then(([procs, pays]) => {
      setProcurements(procs || [])
      setPayments(pays || [])
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const stats = {
    active: procurements.filter(p => p.status === 'active').length,
    completed: procurements.filter(p => p.status === 'completed').length,
    total: procurements.length,
    balance: parseFloat(user?.balance || 0),
  }

  const myProcurements = procurements.filter(p => p.organizer_id === user?.id).slice(0, 5)
  const recentPayments = payments.slice(0, 5)

  return (
    <div style={s.wrap}>
      <div style={s.header}>
        <span>GroupBuy &mdash; <strong>{user.username}</strong></span>
        <div style={s.nav}>
          <button style={s.navBtn(true)}>Dashboard</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('procurements')}>Procurements</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('chat')}>Chat</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('payments')}>Payments</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('profile')}>Profile</button>
          <button style={s.logoutBtn} onClick={onLogout}>Logout</button>
        </div>
      </div>

      <div style={s.main}>
        {loading ? <p style={{ color: '#666' }}>Loading…</p> : (
          <>
            <div style={s.statsGrid}>
              {[
                ['Balance', `₽${stats.balance.toLocaleString()}`, '#28a745'],
                ['Active Procurements', stats.active, '#007bff'],
                ['Completed', stats.completed, '#20c997'],
                ['Total Procurements', stats.total, '#6c757d'],
              ].map(([label, value, color]) => (
                <div key={label} style={s.statCard(color)}>
                  <div style={s.statValue}>{value}</div>
                  <div style={s.statLabel}>{label}</div>
                </div>
              ))}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div style={s.section}>
                <div style={s.sectionTitle}>My Procurements</div>
                {myProcurements.length === 0 ? (
                  <p style={{ color: '#999', fontSize: '.9rem' }}>No procurements yet. <button style={{ ...s.btn, fontSize: '.85rem', marginLeft: '.5rem' }} onClick={() => onNavigate('procurements')}>Create one</button></p>
                ) : (
                  myProcurements.map(p => {
                    const pct = p.target_amount > 0 ? Math.round(p.current_amount / p.target_amount * 100) : 0
                    return (
                      <div key={p.id} style={s.procRow}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 600, fontSize: '.9rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.title}</div>
                          <div style={{ ...s.progress, marginTop: '.3rem' }}>
                            <div style={s.progressBar(pct)} />
                          </div>
                          <div style={{ fontSize: '.75rem', color: '#888', marginTop: '.2rem' }}>{pct}% funded</div>
                        </div>
                        <span style={s.badge(p.status)}>{p.status}</span>
                      </div>
                    )
                  })
                )}
              </div>

              <div style={s.section}>
                <div style={s.sectionTitle}>Recent Payments</div>
                {recentPayments.length === 0 ? (
                  <p style={{ color: '#999', fontSize: '.9rem' }}>No payments yet.</p>
                ) : (
                  recentPayments.map(p => (
                    <div key={p.id} style={s.procRow}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: '.9rem' }}>{p.payment_type === 'deposit' ? 'Deposit' : p.payment_type === 'withdrawal' ? 'Withdrawal' : 'Payment'}</div>
                        <div style={{ fontSize: '.75rem', color: '#888' }}>{new Date(p.created_at).toLocaleDateString()}</div>
                      </div>
                      <span style={{ fontWeight: 600, color: p.payment_type === 'deposit' ? '#28a745' : '#dc3545' }}>
                        {p.payment_type === 'deposit' ? '+' : '−'}₽{parseFloat(p.amount).toLocaleString()}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div style={{ ...s.section, marginTop: '1rem' }}>
              <div style={s.sectionTitle}>Quick Actions</div>
              <div style={{ display: 'flex', gap: '.75rem', flexWrap: 'wrap' }}>
                {[
                  ['Browse Procurements', 'procurements'],
                  ['Open Chat', 'chat'],
                  ['Payments', 'payments'],
                  ['My Profile', 'profile'],
                ].map(([label, page]) => (
                  <button key={page} style={s.btn} onClick={() => onNavigate(page)}>{label}</button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
