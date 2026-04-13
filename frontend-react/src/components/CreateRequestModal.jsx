import React, { useState } from 'react';
import { CloseIcon } from './Icons';

function CreateRequestModal({ isOpen, onClose, onSave }) {
  const [formData, setFormData] = useState({
    product_name: '',
    quantity: '',
    city: '',
    notes: '',
  });
  const [errors, setErrors] = useState({});
  const [isSaving, setIsSaving] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  const validate = () => {
    const errs = {};
    if (!formData.product_name.trim()) errs.product_name = 'Название товара обязательно';
    if (!formData.quantity.trim()) errs.quantity = 'Количество обязательно';
    if (!formData.city.trim()) errs.city = 'Город получения обязателен';
    return errs;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    setIsSaving(true);
    try {
      await onSave(formData);
      setFormData({ product_name: '', quantity: '', city: '', notes: '' });
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay active" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <h3 className="modal-title">Создать запрос на товар</h3>
          <button className="modal-close" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>
        <div className="modal-body">
          <div className="form-group">
            <label className="form-label">Название товара *</label>
            <input
              type="text"
              className={`form-input${errors.product_name ? ' form-input-error' : ''}`}
              name="product_name"
              placeholder="Например: Мёд натуральный"
              value={formData.product_name}
              onChange={handleChange}
            />
            {errors.product_name && <span className="form-field-error">{errors.product_name}</span>}
          </div>
          <div className="form-group">
            <label className="form-label">Количество товара *</label>
            <input
              type="text"
              className={`form-input${errors.quantity ? ' form-input-error' : ''}`}
              name="quantity"
              placeholder="Например: 5 кг"
              value={formData.quantity}
              onChange={handleChange}
            />
            {errors.quantity && <span className="form-field-error">{errors.quantity}</span>}
          </div>
          <div className="form-group">
            <label className="form-label">Город получения товара *</label>
            <input
              type="text"
              className={`form-input${errors.city ? ' form-input-error' : ''}`}
              name="city"
              placeholder="Москва"
              value={formData.city}
              onChange={handleChange}
            />
            {errors.city && <span className="form-field-error">{errors.city}</span>}
          </div>
          <div className="form-group">
            <label className="form-label">Примечание</label>
            <textarea
              className="form-input form-textarea"
              name="notes"
              placeholder="Предпочтения по бренду, срокам и т.д. (необязательно)"
              value={formData.notes}
              onChange={handleChange}
              rows={3}
            />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary btn-round" onClick={onClose}>
            Отмена
          </button>
          <button className="btn btn-primary btn-round" onClick={handleSubmit} disabled={isSaving}>
            {isSaving ? 'Создание...' : 'Создать запрос'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default CreateRequestModal;
