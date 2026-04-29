import { useState, useEffect } from 'react'

const styles = {
  form: { display: 'flex', flexDirection: 'column', gap: '14px' },
  label: { fontSize: '13px', fontWeight: '600', color: '#475569', marginBottom: '4px', display: 'block' },
  input: {
    width: '100%', padding: '10px 12px', border: '1px solid #e2e8f0',
    borderRadius: '8px', fontSize: '14px', outline: 'none',
    transition: 'border-color 0.2s',
  },
  select: {
    width: '100%', padding: '10px 12px', border: '1px solid #e2e8f0',
    borderRadius: '8px', fontSize: '14px', background: '#fff', outline: 'none',
  },
  textarea: {
    width: '100%', padding: '10px 12px', border: '1px solid #e2e8f0',
    borderRadius: '8px', fontSize: '14px', minHeight: '72px', resize: 'vertical', outline: 'none',
  },
  actions: { display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' },
  btn: {
    padding: '10px 20px', borderRadius: '8px', border: 'none',
    fontSize: '14px', fontWeight: '600', cursor: 'pointer',
  },
  error: { color: '#ef4444', fontSize: '13px', marginTop: '4px' },
}

export default function ProductForm({ initial, categories, onSave, onCancel, canEditSpecial }) {
  const [form, setForm] = useState({
    name: '',
    description: '',
    price_rub: '',
    general_note: '',
    special_note: '',
    category_id: categories[0]?.id || '',
    ...initial,
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.name.trim()) return setError('Введите название')
    if (!form.price_rub || isNaN(Number(form.price_rub))) return setError('Введите корректную стоимость')
    if (!form.category_id) return setError('Выберите категорию')
    setSaving(true)
    setError('')
    try {
      await onSave({ ...form, price_rub: Number(form.price_rub), category_id: Number(form.category_id) })
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form style={styles.form} onSubmit={handleSubmit}>
      <div>
        <label style={styles.label}>Название *</label>
        <input style={styles.input} value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="Название продукта" />
      </div>
      <div>
        <label style={styles.label}>Категория *</label>
        <select style={styles.select} value={form.category_id} onChange={(e) => set('category_id', e.target.value)}>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>
      <div>
        <label style={styles.label}>Описание</label>
        <textarea style={styles.textarea} value={form.description} onChange={(e) => set('description', e.target.value)} placeholder="Описание продукта" />
      </div>
      <div>
        <label style={styles.label}>Стоимость (руб.) *</label>
        <input style={styles.input} type="number" step="0.001" min="0" value={form.price_rub} onChange={(e) => set('price_rub', e.target.value)} placeholder="0.000" />
      </div>
      <div>
        <label style={styles.label}>Примечание общее</label>
        <input style={styles.input} value={form.general_note} onChange={(e) => set('general_note', e.target.value)} placeholder="Общее примечание" />
      </div>
      {canEditSpecial && (
        <div>
          <label style={styles.label}>Примечание специальное</label>
          <input style={styles.input} value={form.special_note || ''} onChange={(e) => set('special_note', e.target.value)} placeholder="Специальное примечание" />
        </div>
      )}
      {error && <div style={styles.error}>{error}</div>}
      <div style={styles.actions}>
        <button type="button" style={{ ...styles.btn, background: '#f1f5f9', color: '#475569' }} onClick={onCancel}>Отмена</button>
        <button type="submit" disabled={saving} style={{ ...styles.btn, background: '#3b82f6', color: '#fff' }}>
          {saving ? 'Сохранение...' : 'Сохранить'}
        </button>
      </div>
    </form>
  )
}
