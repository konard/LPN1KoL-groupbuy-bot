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
  row: { padding: '.8rem .5rem', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  meta: { fontSize: '.75rem', color: '#999' },
  actions: { display: 'flex', gap: '.4rem' },
  btnPrimary: { padding: '.3rem .8rem', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '.8rem', fontWeight: 600, background: '#28a745', color: '#fff' },
  btnDanger: { padding: '.3rem .8rem', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '.8rem', fontWeight: 600, background: '#dc3545', color: '#fff' },
  statusBadge: (st) => ({ display: 'inline-block', padding: '.1rem .4rem', borderRadius: 3, fontSize: '.7rem', fontWeight: 700,
    background: { pending:'#fff3cd', accepted:'#d4edda', declined:'#f5c6cb' }[st] || '#e9ecef' }),
}

export default function InvitationsPage({ user, onNavigate, onLogout }) {
  const [list, setList] = useState([])
  function load() { api.myInvitations().then(setList).catch(() => {}) }
  useEffect(() => { load() }, [])
  function respond(id, accept) { api.respondInvitation(id, accept).then(load) }

  return (
    <div style={s.wrap}>
      <div style={s.header}>
        <span>GroupBuy &mdash; <strong>{user.username}</strong></span>
        <div style={s.nav}>
          <button style={s.navBtn(false)} onClick={() => onNavigate('dashboard')}>Dashboard</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('procurements')}>Procurements</button>
          <button style={s.navBtn(true)}>Invitations</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('profile')}>Profile</button>
          <button style={s.logoutBtn} onClick={onLogout}>Logout</button>
        </div>
      </div>
      <div style={s.main}>
        <div style={s.card}>
          <h2 style={{ fontSize: '1.25rem', marginBottom: '1rem' }}>Invitations</h2>
          {list.length === 0 && <p style={{ color: '#999' }}>You have no invitations.</p>}
          {list.map(i => (
            <div key={i.id} style={s.row}>
              <div>
                <div>Procurement #{i.procurement_id} — from user #{i.inviter_id}</div>
                <div style={s.meta}>{new Date(i.created_at).toLocaleString()}
                  &nbsp;<span style={s.statusBadge(i.status)}>{i.status}</span>
                </div>
              </div>
              {i.status === 'pending' && (
                <div style={s.actions}>
                  <button style={s.btnPrimary} onClick={() => respond(i.id, true)}>Accept</button>
                  <button style={s.btnDanger} onClick={() => respond(i.id, false)}>Decline</button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
