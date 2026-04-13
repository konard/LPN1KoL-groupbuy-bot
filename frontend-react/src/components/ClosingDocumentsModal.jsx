import React, { useState } from 'react';
import { CloseIcon } from './Icons';

function ClosingDocumentsModal({ isOpen, onClose, onSave, orderTableId }) {
  const [files, setFiles] = useState([]);
  const [comment, setComment] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [errors, setErrors] = useState({});

  const handleFileChange = (e) => {
    const selected = Array.from(e.target.files);
    setFiles(selected);
    if (errors.files) setErrors((prev) => ({ ...prev, files: undefined }));
  };

  const validate = () => {
    const errs = {};
    if (files.length === 0) errs.files = 'Добавьте хотя бы один документ';
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
      await onSave({ files, comment, orderTableId });
      setFiles([]);
      setComment('');
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
          <h3 className="modal-title">Отправить закрывающие документы</h3>
          <button className="modal-close" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>
        <div className="modal-body">
          <div className="form-group">
            <label className="form-label">Документы *</label>
            <input
              type="file"
              className={`form-input${errors.files ? ' form-input-error' : ''}`}
              multiple
              accept=".pdf,.doc,.docx,.xls,.xlsx"
              onChange={handleFileChange}
            />
            {files.length > 0 && (
              <p className="text-secondary" style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>
                Выбрано файлов: {files.length}
              </p>
            )}
            {errors.files && <span className="form-field-error">{errors.files}</span>}
          </div>
          <div className="form-group">
            <label className="form-label">Комментарий</label>
            <textarea
              className="form-input form-textarea"
              placeholder="Дополнительная информация для покупателей (необязательно)"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
            />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary btn-round" onClick={onClose}>
            Отмена
          </button>
          <button className="btn btn-primary btn-round" onClick={handleSubmit} disabled={isSaving}>
            {isSaving ? 'Отправка...' : 'Отправить документы'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ClosingDocumentsModal;
