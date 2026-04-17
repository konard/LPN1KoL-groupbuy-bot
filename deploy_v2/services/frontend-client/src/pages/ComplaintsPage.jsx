import { useState, useEffect } from 'react'
import { api } from '../api.js'

const s = {
  wrap: { display: 'flex', flexDirection: 'column', height: '100vh' },
  header: { background: '#1a1a2e', color: '#fff', padding: '1rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  nav: { display: 'flex', gap: '1rem', alignItems: 'center' },
  navBtn: (active) => ({ background: active ? '#007bff' : 'transparent', color: '#fff', border: '1px solid #007bff', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer', fontSize: '.9rem' }),
  logoutBtn: { background: 'none', border: '1px solid #a8d8ea', color: '#a8d8ea', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer' },
  main: { flex: 1, padding: '1.5rem', overflowY: 'auto', background: '#f0f2f5' },
  card: { background: '#fff', borderRadius: 8, padding: '1.5rem', maxWidth: 720, margin: '0 auto 1rem', boxShadow: '0 2px 8px rgba(0,0,0,.08)' },
  input: { width: '100%', padding: '.5rem', border: '1px solid #ccc', borderRadius: 4, fontSize: '.95rem', marginBottom: '.6rem' },
  textarea: { width: '100%', padding: '.5rem', border: '1px solid #ccc', borderRadius: 4, fontSize: '.95rem', minHeight: 80, marginBottom: '.6rem' },
  btn: { padding: '.5rem 1.2rem', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '.9rem', fontWeight: 600, background: '#dc3545', color: '#fff' },
  row: { padding: '.8rem .5rem', borderBottom: '1px solid #f0f0f0' },
  subject: { fontWeight: 700 },
  body: { fontSize: '.9rem', color: '#555', margin: '.25rem 0' },
  meta: { fontSize: '.75rem', color: '#999' },
  statusBadge: (st) => ({ display: 'inline-block', padding: '.1rem .4rem', borderRadius: 3, fontSize: '.75rem', fontWeight: 700,
    background: { open:'#fff3cd', in_review:'#d1ecf1', resolved:'#d4edda', rejected:'#f5c6cb' }[st] || '#e9ecef' }),
  success: { color: '#28a745', fontSize: '.85rem', marginBottom: '.5rem' },
  error: { color: '#dc3545', fontSize: '.85rem', marginBottom: '.5rem' },
}

export default function ComplaintsPage({ user, onNavigate, onLogout }) {
  const [list, setList] = useState([])
  const [form, setForm] = useState({ subject: '', body: '', target_user_id: '', procurement_id: '' })
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function load() {
    api.listComplaints({ mine: 'true' }).then(setList).catch(() => {})
  }
  useEffect(() => { load() }, [])

  function submit(e) {
    e.preventDefault()
    setErr(''); setMsg('')
    if (!form.subject || !form.body) { setErr('Subject and body are required'); return }
    setSubmitting(true)
    const payload = { subject: form.subject, body: form.body }
    if (form.target_user_id) payload.target_user_id = parseInt(form.target_user_id, 10)
    if (form.procurement_id) payload.procurement_id = parseInt(form.procurement_id, 10)
    api.createComplaint(payload)
      .then(() => {
        setMsg('Complaint submitted')
        setForm({ subject: '', body: '', target_user_id: '', procurement_id: '' })
        load()
      })
      .catch(e => setErr(e.message))
      .finally(() => setSubmitting(false))
  }

  return (
    <div style={s.wrap}>
      <div style={s.header}>
        <span>GroupBuy &mdash; <strong>{user.username}</strong></span>
        <div style={s.nav}>
          <button style={s.navBtn(false)} onClick={() => onNavigate('dashboard')}>Dashboard</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('procurements')}>Procurements</button>
          <button style={s.navBtn(true)}>Complaints</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('profile')}>Profile</button>
          <button style={s.logoutBtn} onClick={onLogout}>Logout</button>
        </div>
      </div>
      <div style={s.main}>
        <div style={s.card}>
          <h2 style={{ fontSize: '1.25rem', marginBottom: '1rem' }}>File a complaint</h2>
          {err && <p style={s.error}>{err}</p>}
          {msg && <p style={s.success}>{msg}</p>}
          <form onSubmit={submit}>
            <input style={s.input} placeholder="Subject" value={form.subject}
              onChange={e => setForm(f => ({ ...f, subject: e.target.value }))} required />
            <textarea style={s.textarea} placeholder="Describe the issue" value={form.body}
              onChange={e => setForm(f => ({ ...f, body: e.target.value }))} required />
            <input style={s.input} placeholder="Target user ID (optional)" value={form.target_user_id}
              onChange={e => setForm(f => ({ ...f, target_user_id: e.target.value }))} />
            <input style={s.input} placeholder="Procurement ID (optional)" value={form.procurement_id}
              onChange={e => setForm(f => ({ ...f, procurement_id: e.target.value }))} />
            <button type="submit" style={s.btn} disabled={submitting}>
              {submitting ? 'Submitting…' : 'Submit complaint'}
            </button>
          </form>
        </div>

        <div style={s.card}>
          <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>My complaints</h2>
          {list.length === 0 && <p style={{ color: '#999' }}>No complaints yet.</p>}
          {list.map(c => (
            <div key={c.id} style={s.row}>
              <div style={s.subject}>
                {c.subject} <span style={s.statusBadge(c.status)}>{c.status}</span>
              </div>
              <div style={s.body}>{c.body}</div>
              {c.resolution && <div style={{ ...s.body, fontStyle: 'italic' }}>Resolution: {c.resolution}</div>}
              <div style={s.meta}>{new Date(c.created_at).toLocaleString()}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
