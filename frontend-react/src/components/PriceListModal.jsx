import React, { useState } from 'react';
import { CloseIcon } from './Icons';

function PriceListModal({ isOpen, onClose, onSave }) {
  const [file, setFile] = useState(null);
  const [popularItems, setPopularItems] = useState([{ name: '', price: '' }]);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  const handleFileChange = (e) => {
    setFile(e.target.files[0] || null);
    setError('');
  };

  const handleAddItem = () => {
    if (popularItems.length >= 20) return;
    setPopularItems((prev) => [...prev, { name: '', price: '' }]);
  };

  const handleRemoveItem = (index) => {
    setPopularItems((prev) => prev.filter((_, i) => i !== index));
  };

  const handleItemChange = (index, field, value) => {
    setPopularItems((prev) =>
      prev.map((item, i) => (i === index ? { ...item, [field]: value } : item))
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Выберите файл прайс-листа');
      return;
    }
    setIsSaving(true);
    try {
      const validItems = popularItems.filter((item) => item.name.trim() && item.price);
      await onSave({ file, popular_items: validItems });
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay active" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: '520px' }}>
        <div className="modal-header">
          <h3 className="modal-title">Загрузить прайс-лист</h3>
          <button className="modal-close" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>
        <div className="modal-body" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
          <div className="form-group">
            <label className="form-label">Файл прайс-листа *</label>
            <input
              type="file"
              className="form-input"
              accept=".xlsx,.xls,.csv,.pdf"
              onChange={handleFileChange}
            />
            {file && <p className="text-secondary" style={{ marginTop: '0.25rem', fontSize: '0.8rem' }}>Выбран: {file.name}</p>}
            {error && <span className="form-field-error">{error}</span>}
          </div>
          <div className="form-group">
            <label className="form-label">
              Популярные товары (до 20) — необязательно
            </label>
            {popularItems.map((item, index) => (
              <div key={index} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', alignItems: 'center' }}>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Название товара"
                  value={item.name}
                  onChange={(e) => handleItemChange(index, 'name', e.target.value)}
                  style={{ flex: 2 }}
                />
                <input
                  type="number"
                  className="form-input"
                  placeholder="Цена"
                  value={item.price}
                  onChange={(e) => handleItemChange(index, 'price', e.target.value)}
                  min="0"
                  style={{ flex: 1 }}
                />
                {popularItems.length > 1 && (
                  <button
                    type="button"
                    className="btn btn-icon"
                    onClick={() => handleRemoveItem(index)}
                    style={{ color: 'var(--error-color, #e53935)' }}
                  >
                    <CloseIcon />
                  </button>
                )}
              </div>
            ))}
            {popularItems.length < 20 && (
              <button type="button" className="btn btn-outline btn-round" onClick={handleAddItem}>
                + Добавить товар
              </button>
            )}
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary btn-round" onClick={onClose}>
            Отмена
          </button>
          <button className="btn btn-primary btn-round" onClick={handleSubmit} disabled={isSaving}>
            {isSaving ? 'Загрузка...' : 'Загрузить'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default PriceListModal;
