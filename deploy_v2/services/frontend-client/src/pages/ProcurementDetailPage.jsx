import { useState, useEffect } from 'react'
import { api } from '../api.js'

const s = {
  wrap: { display: 'flex', flexDirection: 'column', height: '100vh' },
  header: { background: '#1a1a2e', color: '#fff', padding: '1rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  nav: { display: 'flex', gap: '1rem', alignItems: 'center' },
  navBtn: (active) => ({ background: active ? '#007bff' : 'transparent', color: '#fff', border: '1px solid #007bff', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer', fontSize: '.9rem' }),
  logoutBtn: { background: 'none', border: '1px solid #a8d8ea', color: '#a8d8ea', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer' },
  main: { flex: 1, padding: '1.5rem', overflowY: 'auto', background: '#f0f2f5' },
  card: { background: '#fff', borderRadius: 8, padding: '1.5rem', maxWidth: 820, margin: '0 auto 1rem', boxShadow: '0 2px 8px rgba(0,0,0,.08)' },
  title: { fontSize: '1.5rem', fontWeight: 700, marginBottom: '.5rem' },
  meta: { fontSize: '.85rem', color: '#666', marginBottom: '.75rem' },
  section: { marginTop: '1.2rem' },
  sectionTitle: { fontSize: '1.05rem', fontWeight: 700, marginBottom: '.5rem' },
  input: { padding: '.4rem', border: '1px solid #ccc', borderRadius: 4, fontSize: '.9rem', marginRight: '.4rem' },
  btn: { padding: '.4rem 1rem', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '.85rem', fontWeight: 600, background: '#007bff', color: '#fff', marginRight: '.4rem' },
  btnSecondary: { padding: '.4rem 1rem', border: '1px solid #6c757d', borderRadius: 4, cursor: 'pointer', fontSize: '.85rem', fontWeight: 600, background: '#fff', color: '#6c757d', marginRight: '.4rem' },
  btnDanger: { padding: '.4rem 1rem', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '.85rem', fontWeight: 600, background: '#dc3545', color: '#fff' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '.85rem' },
  th: { textAlign: 'left', padding: '.4rem', borderBottom: '2px solid #ddd' },
  td: { padding: '.4rem', borderBottom: '1px solid #eee' },
  badge: (st) => ({ display: 'inline-block', padding: '.15rem .5rem', borderRadius: 3, fontSize: '.75rem', fontWeight: 700,
    background: { draft: '#e9ecef', active: '#d4edda', stopped: '#fff3cd', payment: '#d1ecf1', completed: '#cce5ff', cancelled: '#f5c6cb' }[st] || '#e9ecef' }),
  tallyRow: { display: 'flex', justifyContent: 'space-between', padding: '.25rem .4rem', background: '#f8f9fa', marginBottom: '.25rem', borderRadius: 4 },
  err: { color: '#dc3545', fontSize: '.85rem' },
  ok: { color: '#28a745', fontSize: '.85rem' },
}

export default function ProcurementDetailPage({ user, procurementId, onNavigate, onLogout }) {
  const [proc, setProc] = useState(null)
  const [receipt, setReceipt] = useState(null)
  const [voteResults, setVoteResults] = useState(null)
  const [voteOption, setVoteOption] = useState('')
  const [supplier, setSupplier] = useState('')
  const [supplierPrice, setSupplierPrice] = useState('')
  const [stopAmt, setStopAmt] = useState('')
  const [inviteId, setInviteId] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  function load() {
    api.getProcurement(procurementId).then(setProc).catch(() => {})
    api.getReceipt(procurementId).then(setReceipt).catch(() => {})
    api.voteResults(procurementId).then(setVoteResults).catch(() => {})
  }
  useEffect(() => { load() }, [procurementId])

  async function doAction(fn, successMsg) {
    setErr(''); setMsg('')
    try { await fn(); setMsg(successMsg); load() }
    catch (e) { setErr(e.message) }
  }

  const isOrganizer = proc && (proc.organizer_id === user.id || user.is_admin)

  return (
    <div style={s.wrap}>
      <div style={s.header}>
        <span>GroupBuy &mdash; <strong>{user.username}</strong></span>
        <div style={s.nav}>
          <button style={s.navBtn(false)} onClick={() => onNavigate('dashboard')}>Dashboard</button>
          <button style={s.navBtn(true)} onClick={() => onNavigate('procurements')}>Procurements</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('notifications')}>Notifications</button>
          <button style={s.navBtn(false)} onClick={() => onNavigate('profile')}>Profile</button>
          <button style={s.logoutBtn} onClick={onLogout}>Logout</button>
        </div>
      </div>
      <div style={s.main}>
        <div style={s.card}>
          <button style={s.btnSecondary} onClick={() => onNavigate('procurements')}>← Back</button>
          {!proc && <p>Loading…</p>}
          {proc && (
            <>
              <h2 style={{ ...s.title, marginTop: '.8rem' }}>
                {proc.title} <span style={s.badge(proc.status)}>{proc.status}</span>
              </h2>
              <div style={s.meta}>
                By {proc.organizer_username} · {proc.city || 'no city'} · deadline {new Date(proc.deadline).toLocaleString()}
              </div>
              <p>{proc.description}</p>

              <div style={s.section}>
                <div style={s.sectionTitle}>Progress</div>
                <div>Target: ₽{proc.target_amount.toLocaleString()} / Current: ₽{proc.current_amount.toLocaleString()}</div>
                <div>Participants: {proc.participant_count}</div>
                {proc.stop_at_amount != null && <div>Stop at: ₽{proc.stop_at_amount.toLocaleString()}</div>}
                {proc.price_per_unit != null && <div>Price/unit: ₽{proc.price_per_unit} {proc.unit}</div>}
              </div>

              {err && <p style={s.err}>{err}</p>}
              {msg && <p style={s.ok}>{msg}</p>}

              {/* Voting — open to participants */}
              <div style={s.section}>
                <div style={s.sectionTitle}>Voting</div>
                <div>
                  <input style={s.input} placeholder="Your vote (e.g. supplier name)"
                    value={voteOption} onChange={e => setVoteOption(e.target.value)} />
                  <button style={s.btn} disabled={!voteOption}
                    onClick={() => doAction(() => api.castVote(procurementId, voteOption), 'Vote recorded')}>Vote</button>
                </div>
                {voteResults && voteResults.total_votes > 0 && (
                  <div style={{ marginTop: '.5rem' }}>
                    <div style={s.meta}>Total votes: {voteResults.total_votes} · Leader: <strong>{voteResults.winner}</strong></div>
                    {Object.entries(voteResults.tally).map(([opt, n]) => (
                      <div key={opt} style={s.tallyRow}><span>{opt}</span><span>{n}</span></div>
                    ))}
                  </div>
                )}
              </div>

              {/* Organizer/admin controls */}
              {isOrganizer && (
                <>
                  <div style={s.section}>
                    <div style={s.sectionTitle}>Supplier approval</div>
                    <input style={s.input} placeholder="Supplier name" value={supplier}
                      onChange={e => setSupplier(e.target.value)} />
                    <input style={s.input} placeholder="Price/unit (optional)" value={supplierPrice}
                      onChange={e => setSupplierPrice(e.target.value)} />
                    <button style={s.btn} disabled={!supplier}
                      onClick={() => doAction(
                        () => api.approveSupplier(procurementId, supplier, supplierPrice ? parseFloat(supplierPrice) : null),
                        'Supplier approved · status → payment'
                      )}>Approve</button>
                  </div>

                  <div style={s.section}>
                    <div style={s.sectionTitle}>Stop-at amount</div>
                    <input style={s.input} placeholder="Amount" value={stopAmt}
                      onChange={e => setStopAmt(e.target.value)} />
                    <button style={s.btn} disabled={!stopAmt}
                      onClick={() => doAction(
                        () => api.setStopAmount(procurementId, parseFloat(stopAmt)),
                        'Stop-at amount set'
                      )}>Set</button>
                  </div>

                  <div style={s.section}>
                    <div style={s.sectionTitle}>Invite user</div>
                    <input style={s.input} placeholder="User ID" value={inviteId}
                      onChange={e => setInviteId(e.target.value)} />
                    <button style={s.btn} disabled={!inviteId}
                      onClick={() => doAction(
                        () => api.inviteUser(procurementId, parseInt(inviteId, 10)),
                        'Invitation sent'
                      )}>Invite</button>
                  </div>

                  <div style={s.section}>
                    <button style={s.btn}
                      onClick={() => doAction(() => api.closeProcurement(procurementId, 'completed'), 'Procurement completed')}>
                      Mark completed
                    </button>
                    <button style={s.btnDanger}
                      onClick={() => doAction(() => api.closeProcurement(procurementId, 'cancelled'), 'Procurement cancelled')}>
                      Cancel
                    </button>
                  </div>
                </>
              )}

              {/* Receipt */}
              {receipt && (
                <div style={s.section}>
                  <div style={s.sectionTitle}>Receipt</div>
                  <table style={s.table}>
                    <thead>
                      <tr>
                        <th style={s.th}>User</th>
                        <th style={s.th}>Quantity</th>
                        <th style={s.th}>Amount</th>
                        <th style={s.th}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {receipt.participants.map(pt => (
                        <tr key={pt.id}>
                          <td style={s.td}>{pt.username}</td>
                          <td style={s.td}>{pt.quantity}</td>
                          <td style={s.td}>₽{pt.amount.toLocaleString()}</td>
                          <td style={s.td}>{pt.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div style={{ marginTop: '.5rem' }}>
                    Total: ₽{receipt.total_amount.toLocaleString()} ·
                    Commission ({receipt.commission_percent}%): ₽{receipt.commission_amount.toLocaleString()} ·
                    <strong> Grand total: ₽{receipt.grand_total.toLocaleString()}</strong>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
