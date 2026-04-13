import React, { useState } from 'react';
import { useStore } from '../store/useStore';
import { api } from '../services/api';
import { CloseIcon } from './Icons';

function WithdrawModal({ isOpen, onClose }) {
  const { user, addToast, loadUser } = useStore();
  const [amount, setAmount] = useState('');
  const [requisites, setRequisites] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleWithdraw = async () => {
    const withdrawAmount = parseFloat(amount);
    if (!withdrawAmount || withdrawAmount < 100) {
      addToast('Минимальная сумма вывода: 100 руб.', 'error');
      return;
    }
    if (!requisites.trim()) {
      addToast('Введите реквизиты счёта', 'error');
      return;
    }
    if (withdrawAmount > (user?.balance || 0)) {
      addToast('Недостаточно средств на балансе', 'error');
      return;
    }
    setIsLoading(true);
    try {
      await api.createPayment({
        user_id: user.coreId || user.id,
        amount: withdrawAmount,
        payment_type: 'withdrawal',
        description: `Вывод на: ${requisites}`,
      });
      addToast('Заявка на вывод средств отправлена', 'success');
      onClose();
      setAmount('');
      setRequisites('');
      if (user) loadUser(user.coreId || user.id);
    } catch (error) {
      addToast('Ошибка при создании заявки на вывод', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay active" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <h3 className="modal-title">Вывод средств</h3>
          <button className="modal-close" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>
        <div className="modal-body">
          <div className="form-group">
            <label className="form-label">Сумма (руб.) *</label>
            <input
              type="number"
              className="form-input"
              placeholder="1000"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              min="100"
            />
            <p className="text-secondary" style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>
              Доступно: {parseFloat(user?.balance || 0).toLocaleString('ru-RU')} руб.
            </p>
          </div>
          <div className="form-group">
            <label className="form-label">Реквизиты счёта *</label>
            <textarea
              className="form-input form-textarea"
              placeholder="Номер карты, расчётный счёт или другие реквизиты..."
              value={requisites}
              onChange={(e) => setRequisites(e.target.value)}
              rows={3}
            />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary btn-round" onClick={onClose}>
            Отмена
          </button>
          <button className="btn btn-primary btn-round" onClick={handleWithdraw} disabled={isLoading}>
            {isLoading ? 'Обработка...' : 'Вывести'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default WithdrawModal;
