import React, { useState, useEffect } from 'react';
import { useStore } from '../store/useStore';
import { api } from '../services/api';
import { CloseIcon } from './Icons';

function CreateProcurementModal() {
  const {
    createProcurementModalOpen,
    closeCreateProcurementModal,
    createProcurement,
    isLoading,
  } = useStore();

  const [categories, setCategories] = useState([]);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    category: '',
    city: '',
    target_amount: '',
    unit: '',
    commission_percent: '1',
    min_quantity: '',
    deadline: '',
  });

  useEffect(() => {
    if (createProcurementModalOpen) {
      api.getCategories().then(setCategories).catch(console.error);
    }
  }, [createProcurementModalOpen]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await createProcurement({
        ...formData,
        // Convert empty string to null for nullable FK/numeric fields so the
        // backend serializer does not reject them with a validation error.
        category: formData.category ? parseInt(formData.category, 10) : null,
        target_amount: parseFloat(formData.target_amount) || 0,
        commission_percent: parseFloat(formData.commission_percent) || 1,
        min_quantity: formData.min_quantity ? parseFloat(formData.min_quantity) : null,
      });
      setFormData({
        title: '',
        description: '',
        category: '',
        city: '',
        target_amount: '',
        unit: '',
        commission_percent: '1',
        min_quantity: '',
        deadline: '',
      });
    } catch (error) {
      // Error is handled in the store
    }
  };

  if (!createProcurementModalOpen) return null;

  return (
    <div className="modal-overlay active" onClick={(e) => e.target === e.currentTarget && closeCreateProcurementModal()}>
      <div className="modal">
        <div className="modal-header">
          <h3 className="modal-title">Создать закупку</h3>
          <button className="modal-close" onClick={closeCreateProcurementModal}>
            <CloseIcon />
          </button>
        </div>
        <div className="modal-body">
          <form id="create-procurement-form" onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Название товара *</label>
              <input
                type="text"
                className="form-input"
                name="title"
                required
                placeholder="Например: Мед натуральный"
                value={formData.title}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Описание *</label>
              <textarea
                className="form-input form-textarea"
                name="description"
                required
                placeholder="Подробное описание закупки..."
                value={formData.description}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Категория</label>
              <select
                className="form-input form-select"
                name="category"
                value={formData.category}
                onChange={handleChange}
              >
                <option value="">Выберите категорию</option>
                {categories.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Город получения *</label>
              <input
                type="text"
                className="form-input"
                name="city"
                required
                placeholder="Москва"
                value={formData.city}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Целевая сумма (руб.) *</label>
              <input
                type="number"
                className="form-input"
                name="target_amount"
                required
                min="1000"
                placeholder="10000"
                value={formData.target_amount}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Единица измерения *</label>
              <input
                type="text"
                className="form-input"
                name="unit"
                required
                placeholder="кг, шт, л"
                value={formData.unit}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Комиссия организатора (1–4%) *</label>
              <input
                type="number"
                className="form-input"
                name="commission_percent"
                required
                min="1"
                max="4"
                step="0.5"
                placeholder="1"
                value={formData.commission_percent}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Минимальное количество товара</label>
              <input
                type="number"
                className="form-input"
                name="min_quantity"
                min="1"
                step="0.01"
                placeholder="Необязательно"
                value={formData.min_quantity}
                onChange={handleChange}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Дедлайн *</label>
              <input
                type="datetime-local"
                className="form-input"
                name="deadline"
                required
                value={formData.deadline}
                onChange={handleChange}
              />
            </div>
          </form>
        </div>
        <div className="modal-footer">
          <button
            className="btn btn-secondary btn-round"
            onClick={closeCreateProcurementModal}
          >
            Отмена
          </button>
          <button
            className="btn btn-primary btn-round"
            onClick={handleSubmit}
            disabled={isLoading}
          >
            {isLoading ? 'Создание...' : 'Создать'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default CreateProcurementModal;
