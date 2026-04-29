import { useState, useEffect } from 'react'
import { adminGetUsers, adminCreateUser, adminToggleBlock, adminDeleteUser, adminChangePassword } from '../api'
import Modal from '../components/Modal'

const styles = {
  page: { padding: '24px', maxWidth: '900px', margin: '0 auto' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' },
  title: { fontSize: '22px', fontWeight: '700', color: '#1e293b' },
  btn: { padding: '10px 18px', borderRadius: '8px', border: 'none', fontSize: '14px', fontWeight: '600', cursor: 'pointer' },
  table: { width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '12px', overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.08)' },
  th: { padding: '14px 16px', background: '#f8fafc', textAlign: 'left', fontSize: '13px', fontWeight: '700', color: '#475569', borderBottom: '1px solid #e2e8f0' },
  td: { padding: '12px 16px', fontSize: '14px', borderBottom: '1px solid #f1f5f9', color: '#334155' },
  badge: (active) => ({
    display: 'inline-block', padding: '2px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: '600',
    background: active ? '#dcfce7' : '#fee2e2',
    color: active ? '#166534' : '#991b1b',
  }),
  roleBadge: (role) => {
    const map = { admin: ['#fef3c7', '#92400e'], advanced_user: ['#dbeafe', '#1d4ed8'], simple_user: ['#f1f5f9', '#475569'] }
    const [bg, color] = map[role] || ['#f1f5f9', '#475569']
    return { display: 'inline-block', padding: '2px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: '600', background: bg, color }
  },
  actions: { display: 'flex', gap: '6px', flexWrap: 'wrap' },
  input: { width: '100%', padding: '12px 14px', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '14px', outline: 'none', marginBottom: '14px' },
  select: { width: '100%', padding: '12px 14px', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '14px', background: '#fff', outline: 'none', marginBottom: '14px' },
  error: { color: '#ef4444', fontSize: '13px', marginBottom: '12px' },
  formActions: { display: 'flex', gap: '10px', justifyContent: 'flex-end' },
  label: { fontSize: '13px', fontWeight: '600', color: '#475569', display: 'block', marginBottom: '6px' },
}

const ROLE_LABELS = { admin: 'Администратор', advanced_user: 'Продвинутый', simple_user: 'Простой' }

function CreateUserModal({ onSave, onClose }) {
  const [form, setForm] = useState({ username: '', password: '', role: 'simple_user' })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.username.trim() || !form.password.trim()) return setError('Заполните все поля')
    setSaving(true)
    setError('')
    try {
      await onSave(form)
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка создания')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Создать пользователя" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <label style={styles.label}>Логин</label>
        <input style={styles.input} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="Логин" autoFocus />
        <label style={styles.label}>Пароль</label>
        <input style={styles.input} type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Пароль" />
        <label style={styles.label}>Роль</label>
        <select style={styles.select} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
          <option value="simple_user">Простой пользователь</option>
          <option value="advanced_user">Продвинутый пользователь</option>
          <option value="admin">Администратор</option>
        </select>
        {error && <div style={styles.error}>{error}</div>}
        <div style={styles.formActions}>
          <button type="button" style={{ ...styles.btn, background: '#f1f5f9', color: '#475569' }} onClick={onClose}>Отмена</button>
          <button type="submit" disabled={saving} style={{ ...styles.btn, background: '#3b82f6', color: '#fff' }}>
            {saving ? 'Создание...' : 'Создать'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function ChangePasswordModal({ userId, onClose }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!password.trim()) return setError('Введите пароль')
    setSaving(true)
    setError('')
    try {
      await adminChangePassword(userId, password)
      setDone(true)
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка изменения пароля')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Изменить пароль" onClose={onClose}>
      {done ? (
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>✓</div>
          <div style={{ color: '#166534', fontWeight: '600' }}>Пароль успешно изменён</div>
          <button style={{ ...styles.btn, background: '#3b82f6', color: '#fff', marginTop: '20px' }} onClick={onClose}>Закрыть</button>
        </div>
      ) : (
        <form onSubmit={handleSubmit}>
          <label style={styles.label}>Новый пароль</label>
          <input style={styles.input} type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Новый пароль" autoFocus />
          {error && <div style={styles.error}>{error}</div>}
          <div style={styles.formActions}>
            <button type="button" style={{ ...styles.btn, background: '#f1f5f9', color: '#475569' }} onClick={onClose}>Отмена</button>
            <button type="submit" disabled={saving} style={{ ...styles.btn, background: '#3b82f6', color: '#fff' }}>
              {saving ? 'Сохранение...' : 'Изменить'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}

export default function AdminPage({ currentUserId }) {
  const [users, setUsers] = useState([])
  const [showCreate, setShowCreate] = useState(false)
  const [pwdUserId, setPwdUserId] = useState(null)

  async function load() {
    try {
      const { data } = await adminGetUsers()
      setUsers(data)
    } catch {}
  }

  useEffect(() => { load() }, [])

  async function handleCreate(data) {
    await adminCreateUser(data)
    setShowCreate(false)
    load()
  }

  async function handleToggleBlock(id) {
    await adminToggleBlock(id)
    load()
  }

  async function handleDelete(id) {
    if (!confirm('Удалить пользователя?')) return
    await adminDeleteUser(id)
    load()
  }

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div style={styles.title}>Управление пользователями</div>
        <button style={{ ...styles.btn, background: '#3b82f6', color: '#fff' }} onClick={() => setShowCreate(true)}>
          + Создать пользователя
        </button>
      </div>

      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Логин</th>
            <th style={styles.th}>Роль</th>
            <th style={styles.th}>Статус</th>
            <th style={styles.th}>Действия</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td style={styles.td}><b>{u.username}</b></td>
              <td style={styles.td}>
                <span style={styles.roleBadge(u.role)}>{ROLE_LABELS[u.role] || u.role}</span>
              </td>
              <td style={styles.td}>
                <span style={styles.badge(u.is_active)}>{u.is_active ? 'Активен' : 'Заблокирован'}</span>
              </td>
              <td style={styles.td}>
                <div style={styles.actions}>
                  <button
                    style={{ ...styles.btn, padding: '5px 10px', fontSize: '12px', background: u.is_active ? '#fef9c3' : '#dcfce7', color: u.is_active ? '#854d0e' : '#166534' }}
                    onClick={() => handleToggleBlock(u.id)}
                    disabled={u.id === currentUserId}
                  >
                    {u.is_active ? 'Заблокировать' : 'Разблокировать'}
                  </button>
                  <button
                    style={{ ...styles.btn, padding: '5px 10px', fontSize: '12px', background: '#f1f5f9', color: '#475569' }}
                    onClick={() => setPwdUserId(u.id)}
                  >
                    Сменить пароль
                  </button>
                  <button
                    style={{ ...styles.btn, padding: '5px 10px', fontSize: '12px', background: '#fee2e2', color: '#ef4444' }}
                    onClick={() => handleDelete(u.id)}
                    disabled={u.id === currentUserId}
                  >
                    Удалить
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showCreate && <CreateUserModal onSave={handleCreate} onClose={() => setShowCreate(false)} />}
      {pwdUserId && <ChangePasswordModal userId={pwdUserId} onClose={() => setPwdUserId(null)} />}
    </div>
  )
}
