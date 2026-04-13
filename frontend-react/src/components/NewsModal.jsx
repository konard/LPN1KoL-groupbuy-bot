import React, { useState } from 'react';
import { CloseIcon } from './Icons';

function NewsModal({ isOpen, onClose, onSave }) {
  const [formData, setFormData] = useState({ title: '', content: '' });
  const [errors, setErrors] = useState({});
  const [isSaving, setIsSaving] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  const validate = () => {
    const errs = {};
    if (!formData.title.trim()) errs.title = 'Заголовок обязателен';
    if (!formData.content.trim()) errs.content = 'Содержание обязательно';
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
      setFormData({ title: '', content: '' });
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
          <h3 className="modal-title">Создать новость</h3>
          <button className="modal-close" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>
        <div className="modal-body">
          <div className="form-group">
            <label className="form-label">Заголовок *</label>
            <input
              type="text"
              className={`form-input${errors.title ? ' form-input-error' : ''}`}
              name="title"
              placeholder="Заголовок новости"
              value={formData.title}
              onChange={handleChange}
            />
            {errors.title && <span className="form-field-error">{errors.title}</span>}
          </div>
          <div className="form-group">
            <label className="form-label">Содержание *</label>
            <textarea
              className={`form-input form-textarea${errors.content ? ' form-input-error' : ''}`}
              name="content"
              placeholder="Текст новости..."
              value={formData.content}
              onChange={handleChange}
              rows={5}
            />
            {errors.content && <span className="form-field-error">{errors.content}</span>}
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary btn-round" onClick={onClose}>
            Отмена
          </button>
          <button className="btn btn-primary btn-round" onClick={handleSubmit} disabled={isSaving}>
            {isSaving ? 'Публикация...' : 'Опубликовать'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default NewsModal;
