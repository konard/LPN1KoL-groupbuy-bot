import React, { useState } from 'react';
import { CloseIcon } from './Icons';

function CompanyCardModal({ isOpen, onClose, onSave }) {
  const [formData, setFormData] = useState({
    company_name: '',
    legal_address: '',
    postal_address: '',
    actual_address: '',
    okved: '',
    ogrn: '',
    inn: '',
    phone: '',
    email: '',
  });
  const [isSaving, setIsSaving] = useState(false);
  const [errors, setErrors] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  const validate = () => {
    const errs = {};
    const required = ['company_name', 'legal_address', 'postal_address', 'actual_address', 'okved', 'ogrn', 'inn', 'phone', 'email'];
    required.forEach((f) => {
      if (!formData[f] || !formData[f].trim()) {
        errs[f] = 'Обязательное поле';
      }
    });
    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      errs.email = 'Некорректный email';
    }
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
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  const fields = [
    { name: 'company_name', label: 'Название компании *', type: 'text', placeholder: 'ООО "Компания"' },
    { name: 'legal_address', label: 'Юридический адрес *', type: 'text', placeholder: 'г. Москва, ул. Примерная, д. 1' },
    { name: 'postal_address', label: 'Почтовый адрес *', type: 'text', placeholder: 'г. Москва, ул. Примерная, д. 1' },
    { name: 'actual_address', label: 'Фактический адрес *', type: 'text', placeholder: 'г. Москва, ул. Примерная, д. 1' },
    { name: 'okved', label: 'ОКВЭД *', type: 'text', placeholder: '47.11' },
    { name: 'ogrn', label: 'ОГРН *', type: 'text', placeholder: '1234567890123' },
    { name: 'inn', label: 'ИНН *', type: 'text', placeholder: '1234567890' },
    { name: 'phone', label: 'Контактный телефон *', type: 'tel', placeholder: '+7 999 123 4567' },
    { name: 'email', label: 'Электронная почта *', type: 'email', placeholder: 'info@company.ru' },
  ];

  return (
    <div className="modal-overlay active" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: '520px' }}>
        <div className="modal-header">
          <h3 className="modal-title">Карточка компании</h3>
          <button className="modal-close" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>
        <div className="modal-body" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
          <form onSubmit={handleSubmit}>
            {fields.map(({ name, label, type, placeholder }) => (
              <div className="form-group" key={name}>
                <label className="form-label">{label}</label>
                <input
                  type={type}
                  className={`form-input${errors[name] ? ' form-input-error' : ''}`}
                  name={name}
                  placeholder={placeholder}
                  value={formData[name]}
                  onChange={handleChange}
                />
                {errors[name] && <span className="form-field-error">{errors[name]}</span>}
              </div>
            ))}
          </form>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary btn-round" onClick={onClose}>
            Отмена
          </button>
          <button className="btn btn-primary btn-round" onClick={handleSubmit} disabled={isSaving}>
            {isSaving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default CompanyCardModal;
