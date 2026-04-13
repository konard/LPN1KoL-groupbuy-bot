/**
 * Admin Categories Page
 */
import React, { useEffect, useState } from 'react';
import { useAdminStore } from '../store/adminStore';
import { adminApi } from '../services/adminApi';
import AdminLayout from '../components/AdminLayout';
import DataTable from '../components/DataTable';

export default function CategoriesPage() {
  const { categories, loadCategories, isLoading, addToast } = useAdminStore();
  const [editModal, setEditModal] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    icon: '',
    is_active: true,
    parent: null,
  });

  useEffect(() => {
    loadCategories();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleEdit = (category) => {
    setFormData({
      name: category.name,
      description: category.description || '',
      icon: category.icon || '',
      is_active: category.is_active,
      parent: category.parent,
    });
    setEditModal(category);
  };

  const handleCreate = () => {
    setFormData({
      name: '',
      description: '',
      icon: '',
      is_active: true,
      parent: null,
    });
    setEditModal({ id: null });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editModal.id) {
        await adminApi.updateCategory(editModal.id, formData);
        addToast('Категория обновлена', 'success');
      } else {
        await adminApi.createCategory(formData);
        addToast('Категория создана', 'success');
      }
      loadCategories();
      setEditModal(null);
    } catch (error) {
      addToast(error.message, 'error');
    }
  };

  const handleDelete = async (category) => {
    if (!window.confirm(`Удалить категорию "${category.name}"?`)) return;
    try {
      await adminApi.deleteCategory(category.id);
      addToast('Категория удалена', 'success');
      loadCategories();
    } catch (error) {
      addToast(error.message, 'error');
    }
  };

  const columns = [
    { key: 'id', label: 'ID', width: '60px' },
    {
      key: 'icon',
      label: '',
      width: '50px',
      render: (icon) => <span style={{ fontSize: '1.5em' }}>{icon || '📁'}</span>,
    },
    {
      key: 'name',
      label: 'Название',
    },
    {
      key: 'description',
      label: 'Описание',
      render: (desc) => desc || '-',
    },
    {
      key: 'parent',
      label: 'Родитель',
      render: (parentId) => {
        if (!parentId) return '-';
        const parent = categories.find((c) => c.id === parentId);
        return parent ? parent.name : '-';
      },
    },
    {
      key: 'procurements_count',
      label: 'Закупок',
      width: '100px',
    },
    {
      key: 'is_active',
      label: 'Активна',
      width: '100px',
      render: (isActive) => (
        <span className={`admin-badge ${isActive ? 'admin-badge-success' : 'admin-badge-danger'}`}>
          {isActive ? 'Да' : 'Нет'}
        </span>
      ),
    },
    {
      key: 'actions',
      label: 'Действия',
      width: '150px',
      render: (_, category) => (
        <div className="admin-actions">
          <button
            className="admin-btn admin-btn-sm"
            onClick={(e) => {
              e.stopPropagation();
              handleEdit(category);
            }}
          >
            Редактировать
          </button>
          <button
            className="admin-btn admin-btn-sm admin-btn-danger"
            onClick={(e) => {
              e.stopPropagation();
              handleDelete(category);
            }}
          >
            Удалить
          </button>
        </div>
      ),
    },
  ];

  return (
    <AdminLayout>
      <div className="admin-page">
        <div className="admin-page-header">
          <h1 className="admin-page-title">Категории</h1>
          <button className="admin-btn admin-btn-primary" onClick={handleCreate}>
            Добавить категорию
          </button>
        </div>

        <DataTable
          columns={columns}
          data={categories}
          loading={isLoading}
          emptyMessage="Категории не найдены"
        />

        {/* Edit/Create Modal */}
        {editModal && (
          <div className="admin-modal-overlay" onClick={() => setEditModal(null)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-modal-header">
                <h3>{editModal.id ? 'Редактировать категорию' : 'Новая категория'}</h3>
                <button
                  className="admin-modal-close"
                  onClick={() => setEditModal(null)}
                >
                  ×
                </button>
              </div>
              <div className="admin-modal-body">
                <form onSubmit={handleSubmit}>
                  <div className="admin-form-group">
                    <label>Название</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      required
                    />
                  </div>
                  <div className="admin-form-group">
                    <label>Описание</label>
                    <textarea
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      rows={3}
                    />
                  </div>
                  <div className="admin-form-group">
                    <label>Иконка (emoji)</label>
                    <input
                      type="text"
                      value={formData.icon}
                      onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                      placeholder="Например: 🍎"
                    />
                  </div>
                  <div className="admin-form-group">
                    <label>Родительская категория</label>
                    <select
                      value={formData.parent || ''}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          parent: e.target.value ? parseInt(e.target.value) : null,
                        })
                      }
                    >
                      <option value="">Нет (корневая)</option>
                      {categories
                        .filter((c) => c.id !== editModal.id)
                        .map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                    </select>
                  </div>
                  <div className="admin-form-group">
                    <label>
                      <input
                        type="checkbox"
                        checked={formData.is_active}
                        onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                      />{' '}
                      Активна
                    </label>
                  </div>
                  <div className="admin-modal-actions">
                    <button type="button" onClick={() => setEditModal(null)}>
                      Отмена
                    </button>
                    <button type="submit" className="admin-btn-primary">
                      {editModal.id ? 'Сохранить' : 'Создать'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
