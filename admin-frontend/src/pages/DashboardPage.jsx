import { useState, useEffect } from 'react'
import { api } from '../api.js'

const styles = `
.admin-layout { display: flex; min-height: 100vh; }
.sidebar { width: 220px; background: #1e293b; color: #e2e8f0; padding: 24px 0; }
.sidebar h2 { font-size: 16px; padding: 0 20px 20px; border-bottom: 1px solid #334155; }
.sidebar nav a { display: block; padding: 12px 20px; color: #94a3b8; text-decoration: none; cursor: pointer; }
.sidebar nav a:hover, .sidebar nav a.active { color: #fff; background: #334155; }
.main { flex: 1; padding: 32px; }
.main h1 { font-size: 22px; margin-bottom: 24px; }
.stat-row { display: flex; gap: 16px; margin-bottom: 24px; }
.stat-card { flex: 1; background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.07); }
.stat-card .label { font-size: 13px; color: #64748b; margin-bottom: 8px; }
.stat-card .value { font-size: 28px; font-weight: 700; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.07); }
th, td { text-align: left; padding: 12px 16px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
th { background: #f8fafc; font-weight: 600; }
.logout-btn { float: right; padding: 8px 16px; background: #ef4444; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
`

const SECTIONS = ['Users', 'Purchases', 'Payments']

export default function DashboardPage({ onLogout }) {
  const [section, setSection] = useState('Users')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    const fetcher = section === 'Users' ? api.users
      : section === 'Purchases' ? api.purchases
      : api.payments
    fetcher()
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false))
  }, [section])

  const columns = rows.length > 0 ? Object.keys(rows[0]) : []

  return (
    <>
      <style>{styles}</style>
      <div className="admin-layout">
        <aside className="sidebar">
          <h2>GroupBuy Admin</h2>
          <nav>
            {SECTIONS.map((s) => (
              <a
                key={s}
                className={section === s ? 'active' : ''}
                onClick={() => setSection(s)}
              >
                {s}
              </a>
            ))}
          </nav>
        </aside>
        <main className="main">
          <button className="logout-btn" onClick={onLogout}>Logout</button>
          <h1>{section}</h1>
          {loading ? (
            <p>Loading…</p>
          ) : rows.length === 0 ? (
            <p>No data available.</p>
          ) : (
            <table>
              <thead>
                <tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i}>
                    {columns.map((c) => <td key={c}>{String(row[c] ?? '')}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </main>
      </div>
    </>
  )
}
