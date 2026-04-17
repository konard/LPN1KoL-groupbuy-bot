import { useState, useEffect } from 'react'
import { api } from '../api.js'

const STATUS_COLORS = {
  draft: '#6c757d',
  active: '#28a745',
  stopped: '#fd7e14',
  payment: '#007bff',
  completed: '#20c997',
  cancelled: '#dc3545',
}

const s = {
  wrap: { display: 'flex', flexDirection: 'column', height: '100vh' },
  header: { background: '#1a1a2e', color: '#fff', padding: '1rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  nav: { display: 'flex', gap: '1rem', alignItems: 'center' },
  navBtn: (active) => ({ background: active ? '#007bff' : 'transparent', color: '#fff', border: '1px solid #007bff', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer', fontSize: '.9rem' }),
  logoutBtn: { background: 'none', border: '1px solid #a8d8ea', color: '#a8d8ea', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer' },
  main: { flex: 1, padding: '1.5rem', overflowY: 'auto', background: '#f0f2f5' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem' },
  card: { background: '#fff', borderRadius: 8, padding: '1.2rem', boxShadow: '0 2px 4px rgba(0,0,0,.08)', display: 'flex', flexDirection: 'column', gap: '.5rem' },
  cardTitle: { fontWeight: 700, fontSize: '1.05rem' },
  badge: (status) => ({ display: 'inline-block', padding: '.15rem .5rem', borderRadius: 4, fontSize: '.8rem', fontWeight: 600, background: STATUS_COLORS[status] + '22', color: STATUS_COLORS[status] }),
  progress: { background: '#e9ecef', borderRadius: 4, height: 8 },
  progressBar: (pct) => ({ background: '#007bff', height: 8, borderRadius: 4, width: `${Math.min(pct, 100)}%` }),
  btn: { padding: '.4rem .9rem', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '.9rem' },
  btnPrimary: { background: '#007bff', color: '#fff' },
  btnDanger: { background: '#dc3545', color: '#fff' },
  btnSuccess: { background: '#28a745', color: '#fff' },
  filterRow: { display: 'flex', gap: '.75rem', marginBottom: '1.2rem', flexWrap: 'wrap', alignItems: 'center' },
  select: { padding: '.4rem .6rem', border: '1px solid #ccc', borderRadius: 4, fontSize: '.9rem' },
  input: { padding: '.4rem .6rem', border: '1px solid #ccc', borderRadius: 4, fontSize: '.9rem', minWidth: 120 },
  modal: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 },
  modalBox: { background: '#fff', borderRadius: 8, padding: '2rem', width: 440, maxHeight: '90vh', overflowY: 'auto' },
  formRow: { marginBottom: '.8rem' },
  label: { display: 'block', marginBottom: '.25rem', fontSize: '.9rem', fontWeight: 600 },
  formInput: { width: '100%', padding: '.5rem', border: '1px solid #ccc', borderRadius: 4, fontSize: '.95rem' },
  error: { color: '#dc3545', fontSize: '.85rem', marginBottom: '.5rem' },
}

const STATUS_OPTIONS = ['', 'draft', 'active', 'stopped', 'payment', 'completed', 'cancelled']

export default function ProcurementsPage({ user, onNavigate, onLogout }) {
  const [procurements, setProcurements] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({ status: 'active', city: '' })
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({
    title: '', description: '', city: '', target_amount: '', unit: 'units',
    price_per_unit: '', deadline: '', image_url: '',
  })
  const [createError, setCreateError] = useState('')
  const [actionError, setActionError] = useState('')

  useEffect(() => {
    loadProcurements()
  }, [filter])

  async function loadProcurements() {
    setLoading(true)
    try {
      const params = {}
      if (filter.status) params.status = filter.status
      if (filter.city) params.city = filter.city
      const data = await api.listProcurements(params)
      setProcurements(data || [])
    } catch (e) {
      setActionError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleJoin(procId) {
    setActionError('')
    try {
      await api.joinProcurement(procId, 1)
      await loadProcurements()
    } catch (e) {
      setActionError(e.message)
    }
  }

  async function handleLeave(procId) {
    setActionError('')
    try {
      await api.leaveProcurement(procId)
      await loadProcurements()
    } catch (e) {
      setActionError(e.message)
    }
  }

  async function handleCreate(e) {
    e.preventDefault()
    setCreateError('')
    try {
      await api.createProcurement({
        ...createForm,
        target_amount: parseFloat(createForm.target_amount),
        price_per_unit: createForm.price_per_unit ? parseFloat(createForm.price_per_unit) : null,
        deadline: new Date(createForm.deadline).toISOString(),
      })
      setShowCreate(false)
      setCreateForm({ title: '', description: '', city: '', target_amount: '', unit: 'units', price_per_unit: '', deadline: '', image_url: '' })
      await loadProcurements()
    } catch (e) {
      setCreateError(e.message)
    }
  }

  function setField(field) {
    return (e) => setCreateForm(f => ({ ...f, [field]: e.target.value }))
  }

  return (
    <div style={s.wrap}>
      <div style={s.header}>
        <span>GroupBuy &mdash; <strong>{user.username}</strong></span>
        <div style={s.nav}>
          <button style={s.navBtn(false)} onClick={() => onNavigate('chat')}>Chat</button>
          <button style={s.navBtn(true)}>Procurements</button>
          <button style={s.logoutBtn} onClick={onLogout}>Logout</button>
        </div>
      </div>

      <div style={s.main}>
        <div style={s.filterRow}>
          <select style={s.select} value={filter.status} onChange={e => setFilter(f => ({ ...f, status: e.target.value }))}>
            {STATUS_OPTIONS.map(v => <option key={v} value={v}>{v || 'All statuses'}</option>)}
          </select>
          <input style={s.input} placeholder="Filter by city" value={filter.city}
            onChange={e => setFilter(f => ({ ...f, city: e.target.value }))} />
          <button style={{ ...s.btn, ...s.btnPrimary }} onClick={() => setShowCreate(true)}>+ New Procurement</button>
        </div>

        {actionError && <p style={{ ...s.error, marginBottom: '1rem' }}>{actionError}</p>}

        {loading ? (
          <p style={{ color: '#666' }}>Loading…</p>
        ) : procurements.length === 0 ? (
          <p style={{ color: '#666' }}>No procurements found.</p>
        ) : (
          <div style={s.grid}>
            {procurements.map(p => {
              const pct = p.target_amount > 0 ? Math.round(p.current_amount / p.target_amount * 100) : 0
              return (
                <div key={p.id} style={s.card}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span style={s.cardTitle}>{p.title}</span>
                    <span style={s.badge(p.status)}>{p.status}</span>
                  </div>
                  {p.description && <p style={{ fontSize: '.85rem', color: '#666' }}>{p.description.slice(0, 100)}{p.description.length > 100 ? '…' : ''}</p>}
                  <div style={{ fontSize: '.85rem', color: '#555' }}>
                    <span>Organizer: {p.organizer_username}</span>
                    {p.city && <span style={{ marginLeft: '.5rem' }}>• {p.city}</span>}
                  </div>
                  <div>
                    <div style={{ fontSize: '.8rem', color: '#666', marginBottom: '.25rem' }}>
                      {p.current_amount.toLocaleString()} / {p.target_amount.toLocaleString()} ({pct}%)
                    </div>
                    <div style={s.progress}><div style={s.progressBar(pct)} /></div>
                  </div>
                  <div style={{ fontSize: '.8rem', color: '#777', display: 'flex', justifyContent: 'space-between' }}>
                    <span>{p.participant_count} participants</span>
                    <span>Deadline: {new Date(p.deadline).toLocaleDateString()}</span>
                  </div>
                  {p.status === 'active' && (
                    <div style={{ display: 'flex', gap: '.5rem', marginTop: '.25rem' }}>
                      <button style={{ ...s.btn, ...s.btnSuccess, flex: 1 }} onClick={() => handleJoin(p.id)}>Join</button>
                      <button style={{ ...s.btn, ...s.btnDanger, flex: 1 }} onClick={() => handleLeave(p.id)}>Leave</button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {showCreate && (
        <div style={s.modal} onClick={e => e.target === e.currentTarget && setShowCreate(false)}>
          <div style={s.modalBox}>
            <h3 style={{ marginBottom: '1rem' }}>Create Procurement</h3>
            {createError && <p style={s.error}>{createError}</p>}
            <form onSubmit={handleCreate}>
              {[['title', 'Title', 'text'], ['city', 'City', 'text'], ['target_amount', 'Target Amount (₽)', 'number'], ['price_per_unit', 'Price per Unit (₽)', 'number']].map(([field, label, type]) => (
                <div key={field} style={s.formRow}>
                  <label style={s.label}>{label}</label>
                  <input style={s.formInput} type={type} value={createForm[field]} onChange={setField(field)}
                    required={['title', 'target_amount'].includes(field)} min={type === 'number' ? '0' : undefined} step={type === 'number' ? 'any' : undefined} />
                </div>
              ))}
              <div style={s.formRow}>
                <label style={s.label}>Unit</label>
                <select style={s.formInput} value={createForm.unit} onChange={setField('unit')}>
                  {['units', 'kg', 'liters', 'pieces'].map(u => <option key={u} value={u}>{u}</option>)}
                </select>
              </div>
              <div style={s.formRow}>
                <label style={s.label}>Deadline</label>
                <input style={s.formInput} type="datetime-local" value={createForm.deadline} onChange={setField('deadline')} required />
              </div>
              <div style={s.formRow}>
                <label style={s.label}>Description</label>
                <textarea style={{ ...s.formInput, minHeight: 60 }} value={createForm.description} onChange={setField('description')} />
              </div>
              <div style={{ display: 'flex', gap: '.5rem', marginTop: '.5rem' }}>
                <button type="submit" style={{ ...s.btn, ...s.btnPrimary, flex: 1 }}>Create</button>
                <button type="button" style={{ ...s.btn, background: '#6c757d', color: '#fff', flex: 1 }} onClick={() => setShowCreate(false)}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
