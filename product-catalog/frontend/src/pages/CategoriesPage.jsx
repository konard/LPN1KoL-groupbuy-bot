import { useState, useEffect } from 'react'
import { getCategories, createCategory, updateCategory, deleteCategory } from '../api'
import Modal from '../components/Modal'

const styles = {
  page: { padding: '24px', maxWidth: '700px', margin: '0 auto' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' },
  title: { fontSize: '22px', fontWeight: '700', color: '#1e293b' },
  btn: { padding: '10px 18px', borderRadius: '8px', border: 'none', fontSize: '14px', fontWeight: '600', cursor: 'pointer' },
  list: { background: '#fff', borderRadius: '12px', boxShadow: '0 1px 4px rgba(0,0,0,0.08)', overflow: 'hidden' },
  item: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 20px', borderBottom: '1px solid #f1f5f9' },
  name: { fontWeight: '600', fontSize: '15px', color: '#1e293b' },
  actions: { display: 'flex', gap: '8px' },
  input: { width: '100%', padding: '12px 14px', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '14px', outline: 'none', marginBottom: '16px' },
  error: { color: '#ef4444', fontSize: '13px', marginBottom: '12px' },
  formActions: { display: 'flex', gap: '10px', justifyContent: 'flex-end' },
  empty: { padding: '40px', textAlign: 'center', color: '#94a3b8' },
}

function CategoryFormModal({ initial, onSave, onClose }) {
  const [name, setName] = useState(initial?.name || '')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!name.trim()) return setError('Введите название')
    setSaving(true)
    setError('')
    try {
      await onSave(name.trim())
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={initial ? 'Изменить категорию' : 'Добавить категорию'} onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <input style={styles.input} value={name} onChange={(e) => setName(e.target.value)} placeholder="Название категории" autoFocus />
        {error && <div style={styles.error}>{error}</div>}
        <div style={styles.formActions}>
          <button type="button" style={{ ...styles.btn, background: '#f1f5f9', color: '#475569' }} onClick={onClose}>Отмена</button>
          <button type="submit" disabled={saving} style={{ ...styles.btn, background: '#3b82f6', color: '#fff' }}>
            {saving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

export default function CategoriesPage() {
  const [categories, setCategories] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [editCat, setEditCat] = useState(null)

  async function load() {
    try {
      const { data } = await getCategories()
      setCategories(data)
    } catch {}
  }

  useEffect(() => { load() }, [])

  async function handleSave(name) {
    if (editCat) {
      await updateCategory(editCat.id, name)
    } else {
      await createCategory(name)
    }
    setShowForm(false)
    setEditCat(null)
    load()
  }

  async function handleDelete(id) {
    if (!confirm('Удалить категорию? Все продукты этой категории будут удалены.')) return
    await deleteCategory(id)
    load()
  }

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div style={styles.title}>Справочник категорий</div>
        <button style={{ ...styles.btn, background: '#3b82f6', color: '#fff' }} onClick={() => { setEditCat(null); setShowForm(true) }}>
          + Добавить
        </button>
      </div>

      <div style={styles.list}>
        {categories.length === 0 ? (
          <div style={styles.empty}>Нет категорий</div>
        ) : (
          categories.map((c) => (
            <div key={c.id} style={styles.item}>
              <span style={styles.name}>{c.name}</span>
              <div style={styles.actions}>
                <button
                  style={{ ...styles.btn, padding: '6px 12px', background: '#f1f5f9', color: '#475569', fontSize: '13px' }}
                  onClick={() => { setEditCat(c); setShowForm(true) }}
                >
                  Изменить
                </button>
                <button
                  style={{ ...styles.btn, padding: '6px 12px', background: '#fee2e2', color: '#ef4444', fontSize: '13px' }}
                  onClick={() => handleDelete(c.id)}
                >
                  Удалить
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {showForm && (
        <CategoryFormModal
          initial={editCat}
          onSave={handleSave}
          onClose={() => { setShowForm(false); setEditCat(null) }}
        />
      )}
    </div>
  )
}
