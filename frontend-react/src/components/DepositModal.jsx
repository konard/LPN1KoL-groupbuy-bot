import React, { useState } from 'react';
import { useStore } from '../store/useStore';
import { api } from '../services/api';
import { CloseIcon } from './Icons';

function DepositModal() {
  const { user, depositModalOpen, closeDepositModal, addToast, loadUser } = useStore();
  const [amount, setAmount] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('card');
  const [isLoading, setIsLoading] = useState(false);

  const handleDeposit = async () => {
    const depositAmount = parseFloat(amount);
    if (!depositAmount || depositAmount < 100) {
      addToast('Минимальная сумма пополнения: 100 руб.', 'error');
      return;
    }

    setIsLoading(true);
    try {
      await api.createPayment({
        user_id: user.coreId || user.id,
        amount: depositAmount,
        payment_type: 'deposit',
        payment_method: paymentMethod,
      });
      addToast('Платеж создан. Ожидайте подтверждения.', 'success');
      closeDepositModal();
      setAmount('');
      // Reload user to update balance (in real app, this would wait for payment confirmation)
      if (user) {
        loadUser(user.coreId || user.id);
      }
    } catch (error) {
      addToast('Ошибка создания платежа', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  if (!depositModalOpen) return null;

  return (
    <div className="modal-overlay active" onClick={(e) => e.target === e.currentTarget && closeDepositModal()}>
      <div className="modal">
        <div className="modal-header">
          <h3 className="modal-title">Пополнение баланса</h3>
          <button className="modal-close" onClick={closeDepositModal}>
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
          </div>
          <div className="form-group" style={{ marginTop: '0.75rem' }}>
            <label className="form-label">Способ оплаты *</label>
            <select
              className="form-input form-select"
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
            >
              <option value="card">Банковская карта</option>
              <option value="wallet">Электронный кошелёк</option>
              <option value="transfer">Банковский перевод</option>
            </select>
          </div>
          <p className="text-secondary text-sm mt-md">
            Минимальная сумма пополнения: 100 руб.
          </p>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary btn-round" onClick={closeDepositModal}>
            Отмена
          </button>
          <button
            className="btn btn-primary btn-round"
            onClick={handleDeposit}
            disabled={isLoading}
          >
            {isLoading ? 'Обработка...' : 'Пополнить'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default DepositModal;
