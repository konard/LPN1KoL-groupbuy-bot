import { useState, useEffect, useCallback } from 'react'
import { getProducts, getCategories, createProduct, updateProduct, deleteProduct } from '../api'
import { useRole } from '../hooks/useRole'
import PriceCell from '../components/PriceCell'
import Modal from '../components/Modal'
import ProductForm from '../components/ProductForm'

const styles = {
  page: { padding: '24px', maxWidth: '1200px', margin: '0 auto' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' },
  title: { fontSize: '22px', fontWeight: '700', color: '#1e293b' },
  controls: { display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap' },
  input: {
    padding: '10px 14px', border: '1px solid #e2e8f0', borderRadius: '8px',
    fontSize: '14px', outline: 'none', minWidth: '220px',
  },
  select: {
    padding: '10px 14px', border: '1px solid #e2e8f0', borderRadius: '8px',
    fontSize: '14px', background: '#fff', outline: 'none',
  },
  btn: {
    padding: '10px 18px', borderRadius: '8px', border: 'none',
    fontSize: '14px', fontWeight: '600', cursor: 'pointer',
  },
  table: { width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '12px', overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.08)' },
  th: { padding: '14px 16px', background: '#f8fafc', textAlign: 'left', fontSize: '13px', fontWeight: '700', color: '#475569', borderBottom: '1px solid #e2e8f0' },
  td: { padding: '12px 16px', fontSize: '14px', borderBottom: '1px solid #f1f5f9', color: '#334155', verticalAlign: 'top' },
  actions: { display: 'flex', gap: '8px' },
  badge: { display: 'inline-block', padding: '2px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: '600', background: '#dbeafe', color: '#1d4ed8' },
  empty: { textAlign: 'center', padding: '60px', color: '#94a3b8', fontSize: '16px' },
}

export default function CatalogPage({ user }) {
  const roles = useRole(user)
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState([])
  const [search, setSearch] = useState('')
  const [filterCat, setFilterCat] = useState('')
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editProduct, setEditProduct] = useState(null)

  const loadProducts = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (search) params.search = search
      if (filterCat) params.category_id = filterCat
      const { data } = await getProducts(params)
      setProducts(data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [search, filterCat])

  useEffect(() => {
    getCategories().then(({ data }) => setCategories(data)).catch(() => {})
  }, [])

  useEffect(() => {
    const t = setTimeout(loadProducts, 300)
    return () => clearTimeout(t)
  }, [loadProducts])

  async function handleSave(formData) {
    if (editProduct) {
      await updateProduct(editProduct.id, formData)
    } else {
      await createProduct(formData)
    }
    setShowForm(false)
    setEditProduct(null)
    loadProducts()
  }

  async function handleDelete(id) {
    if (!confirm('Удалить продукт?')) return
    await deleteProduct(id)
    loadProducts()
  }

  const columns = [
    'Наименование', 'Категория', 'Описание', 'Стоимость, руб.', 'Примечание общее',
    ...(roles.canSeeSpecialNote ? ['Примечание специальное'] : []),
    'Действия',
  ]

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div style={styles.title}>Каталог продуктов</div>
        <button
          style={{ ...styles.btn, background: '#3b82f6', color: '#fff' }}
          onClick={() => { setEditProduct(null); setShowForm(true) }}
        >
          + Добавить продукт
        </button>
      </div>

      <div style={styles.controls}>
        <input
          style={styles.input}
          placeholder="Поиск по названию..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select style={styles.select} value={filterCat} onChange={(e) => setFilterCat(e.target.value)}>
          <option value="">Все категории</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        {filterCat && (
          <button
            style={{ ...styles.btn, background: '#f1f5f9', color: '#475569' }}
            onClick={() => setFilterCat('')}
          >
            Сбросить
          </button>
        )}
      </div>

      {loading ? (
        <div style={styles.empty}>Загрузка...</div>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col} style={styles.th}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {products.length === 0 ? (
              <tr>
                <td colSpan={columns.length} style={styles.empty}>Продукты не найдены</td>
              </tr>
            ) : (
              products.map((p) => (
                <tr key={p.id}>
                  <td style={styles.td}><b>{p.name}</b></td>
                  <td style={styles.td}>
                    <span style={styles.badge}>{p.category_name}</span>
                  </td>
                  <td style={styles.td}>{p.description}</td>
                  <td style={styles.td}>
                    <PriceCell price={p.price_rub} />
                  </td>
                  <td style={styles.td}>{p.general_note}</td>
                  {roles.canSeeSpecialNote && <td style={styles.td}>{p.special_note}</td>}
                  <td style={styles.td}>
                    <div style={styles.actions}>
                      <button
                        style={{ ...styles.btn, padding: '6px 12px', background: '#f1f5f9', color: '#475569', fontSize: '13px' }}
                        onClick={() => { setEditProduct(p); setShowForm(true) }}
                      >
                        Изменить
                      </button>
                      {roles.canDelete && (
                        <button
                          style={{ ...styles.btn, padding: '6px 12px', background: '#fee2e2', color: '#ef4444', fontSize: '13px' }}
                          onClick={() => handleDelete(p.id)}
                        >
                          Удалить
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      )}

      {showForm && (
        <Modal
          title={editProduct ? 'Редактировать продукт' : 'Добавить продукт'}
          onClose={() => { setShowForm(false); setEditProduct(null) }}
        >
          <ProductForm
            initial={editProduct}
            categories={categories}
            canEditSpecial={roles.canSeeSpecialNote}
            onSave={handleSave}
            onCancel={() => { setShowForm(false); setEditProduct(null) }}
          />
        </Modal>
      )}
    </div>
  )
}
