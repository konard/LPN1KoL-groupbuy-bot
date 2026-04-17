import { useState, useEffect } from 'react'
import { api } from '../api.js'

const s = {
  wrap: { display: 'flex', flexDirection: 'column', height: '100vh' },
  header: { background: '#1a1a2e', color: '#fff', padding: '1rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  nav: { display: 'flex', gap: '1rem', alignItems: 'center' },
  navBtn: (active) => ({ background: active ? '#007bff' : 'transparent', color: '#fff', border: '1px solid #007bff', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer', fontSize: '.9rem' }),
  logoutBtn: { background: 'none', border: '1px solid #a8d8ea', color: '#a8d8ea', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer' },
  main: { flex: 1, padding: '1.5rem', overflowY: 'auto', background: '#f0f2f5' },
  balanceCard: { background: '#1a1a2e', color: '#fff', borderRadius: 8, padding: '1.5rem', marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  balanceLabel: { fontSize: '.9rem', opacity: .7 },
  balanceAmount: { fontSize: '2rem', fontWeight: 700, color: '#7bed9f' },
  actions: { display: 'flex', gap: '.75rem', marginBottom: '1.5rem', flexWrap: 'wrap' },
  btn: { padding: '.5rem 1.2rem', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '.9rem', fontWeight: 600 },
  btnDeposit: { background: '#28a745', color: '#fff' },
  btnWithdraw: { background: '#dc3545', color: '#fff' },
  table: { width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: 8, overflow: 'hidden', boxShadow: '0 2px 4px rgba(0,0,0,.08)' },
  th: { textAlign: 'left', padding: '.75rem 1rem', background: '#f9f9f9', fontWeight: 600, borderBottom: '1px solid #eee', fontSize: '.9rem' },
  td: { padding: '.7rem 1rem', borderBottom: '1px solid #f0f0f0', fontSize: '.9rem' },
  badge: (type) => ({
    display: 'inline-block', padding: '.15rem .5rem', borderRadius: 4, fontSize: '.8rem', fontWeight: 600,
    background: type === 'deposit' ? '#d4edda' : type === 'withdrawal' ? '#f8d7da' : '#cce5ff',
    color: type === 'deposit' ? '#155724' : type === 'withdrawal' ? '#721c24' : '#004085',
  }),
  statusBadge: (status) => ({
    display: 'inline-block', padding: '.15rem .5rem', borderRadius: 4, fontSize: '.8rem', fontWeight: 600,
    background: status === 'succeeded' ? '#d4edda' : status === 'pending' ? '#fff3cd' : '#f8d7da',
    color: status === 'succeeded' ? '#155724' : status === 'pending' ? '#856404' : '#721c24',
  }),
  modal: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 },
  modalBox: { background: '#fff', borderRadius: 8, padding: '2rem', width: 360 },
  formRow: { marginBottom: '.8rem' },
  label: { display: 'block', marginBottom: '.25rem', fontSize: '.9rem', fontWeight: 600 },
  formInput: { width: '100%', padding: '.5rem', border: '1px solid #ccc', borderRadius: 4, fontSize: '.95rem' },
  error: { color: '#dc3545', fontSize: '.85rem', marginBottom: '.5rem' },
  empty: { textAlign: 'center', padding: '3rem', color: '#999' },
}

const TYPE_LABELS = { deposit: 'Deposit', withdrawal: 'Withdrawal', procurement_payment: 'Procurement' }

export default function PaymentsPage({ user, onNavigate, onLogout }) {
  const [payments, setPayments] = useState([])
  const [loading, setLoading] = useState(true)
  const [balance, setBalance] = useState(user?.balance ?? 0)
  const [modal, setModal] = useState(null) // 'deposit' | 'withdraw' | null
  const [amount, setAmount] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [paymentsData, meData] = await Promise.all([
        api.listPayments(),
        api.me(),
      ])
      setPayments(paymentsData || [])
      setBalance(meData?.balance ?? balance)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const amt = parseFloat(amount)
    if (!amt || amt <= 0) { setError('Enter a valid amount'); return }
    setSubmitting(true)
    setError('')
    try {
      await api.createPayment({
        payment_type: modal,
        amount: amt,
        description,
      })
      setModal(null)
      setAmount('')
      setDescription('')
      await loadData()
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  function openModal(type) {
    setModal(type)
    setAmount('')
    setDescription('')
    setError('')
  }

  return (
    <div style={s.wrap}>
      <div style={s.header}>
        <span>GroupBuy &mdash; <strong>{user.username}</strong></span>
        <div style={s.nav}>
          <button style={s.navBtn(false)} onClick={() => onNavigate('procurements')}>Procurements</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('chat')}>Chat</button>
          <button style={s.navBtn(true)}>Payments</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('profile')}>Profile</button>
          <button style={s.logoutBtn} onClick={onLogout}>Logout</button>
        </div>
      </div>

      <div style={s.main}>
        <div style={s.balanceCard}>
          <div>
            <div style={s.balanceLabel}>Current Balance</div>
            <div style={s.balanceAmount}>₽{balance.toLocaleString()}</div>
          </div>
          <div style={{ display: 'flex', gap: '.75rem' }}>
            <button style={{ ...s.btn, ...s.btnDeposit }} onClick={() => openModal('deposit')}>+ Deposit</button>
            <button style={{ ...s.btn, ...s.btnWithdraw }} onClick={() => openModal('withdrawal')}>− Withdraw</button>
          </div>
        </div>

        <h2 style={{ marginBottom: '1rem', fontSize: '1.1rem' }}>Payment History</h2>
        {loading ? (
          <p style={{ color: '#666' }}>Loading…</p>
        ) : payments.length === 0 ? (
          <div style={s.empty}>No payments yet.</div>
        ) : (
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>#</th>
                <th style={s.th}>Type</th>
                <th style={s.th}>Amount</th>
                <th style={s.th}>Status</th>
                <th style={s.th}>Description</th>
                <th style={s.th}>Date</th>
              </tr>
            </thead>
            <tbody>
              {payments.map(p => (
                <tr key={p.id}>
                  <td style={s.td}>{p.id}</td>
                  <td style={s.td}><span style={s.badge(p.payment_type)}>{TYPE_LABELS[p.payment_type] || p.payment_type}</span></td>
                  <td style={s.td}>
                    <span style={{ color: p.payment_type === 'deposit' ? '#28a745' : '#dc3545', fontWeight: 600 }}>
                      {p.payment_type === 'deposit' ? '+' : '−'}₽{parseFloat(p.amount).toLocaleString()}
                    </span>
                  </td>
                  <td style={s.td}><span style={s.statusBadge(p.status)}>{p.status}</span></td>
                  <td style={s.td}>{p.description || '—'}</td>
                  <td style={s.td}>{new Date(p.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {modal && (
        <div style={s.modal} onClick={e => e.target === e.currentTarget && setModal(null)}>
          <div style={s.modalBox}>
            <h3 style={{ marginBottom: '1rem' }}>{modal === 'deposit' ? 'Deposit Funds' : 'Withdraw Funds'}</h3>
            {error && <p style={s.error}>{error}</p>}
            <form onSubmit={handleSubmit}>
              <div style={s.formRow}>
                <label style={s.label}>Amount (₽)</label>
                <input style={s.formInput} type="number" min="0.01" step="0.01" value={amount}
                  onChange={e => setAmount(e.target.value)} required autoFocus />
              </div>
              <div style={s.formRow}>
                <label style={s.label}>Description (optional)</label>
                <input style={s.formInput} type="text" value={description}
                  onChange={e => setDescription(e.target.value)} />
              </div>
              <div style={{ display: 'flex', gap: '.5rem', marginTop: '.5rem' }}>
                <button type="submit" disabled={submitting}
                  style={{ ...s.btn, ...(modal === 'deposit' ? s.btnDeposit : s.btnWithdraw), flex: 1 }}>
                  {submitting ? 'Processing…' : modal === 'deposit' ? 'Deposit' : 'Withdraw'}
                </button>
                <button type="button" style={{ ...s.btn, background: '#6c757d', color: '#fff', flex: 1 }}
                  onClick={() => setModal(null)}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
