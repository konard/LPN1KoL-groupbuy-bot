import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../store/useStore';
import { api } from '../services/api';
import { formatCurrency, getStatusText } from '../utils/helpers';
import { CloseIcon } from './Icons';

function ProcurementModal() {
  const navigate = useNavigate();
  const {
    user,
    procurementModalOpen,
    closeProcurementModal,
    selectedProcurement,
    joinProcurement,
    leaveProcurement,
    stopProcurement,
    approveSupplier,
    closeProcurement,
    castVote,
    setCurrentChat,
    addToast,
  } = useStore();

  const [amount, setAmount] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [notes, setNotes] = useState('');
  const [joinCity, setJoinCity] = useState('');
  const [activeTab, setActiveTab] = useState('info');
  const [voteResults, setVoteResults] = useState(null);
  const [suppliers, setSuppliers] = useState([]);
  const [selectedSupplierId, setSelectedSupplierId] = useState('');
  const [voteComment, setVoteComment] = useState('');
  const [participants, setParticipants] = useState([]);
  const [isLoadingTab, setIsLoadingTab] = useState(false);

  const isOrganizer = user && selectedProcurement && selectedProcurement.organizer === (user.coreId || user.id);
  const canVote = selectedProcurement && ['active', 'stopped'].includes(selectedProcurement.status);
  const canJoin = selectedProcurement && selectedProcurement.status === 'active';
  const canStop = isOrganizer && selectedProcurement && selectedProcurement.status === 'active';
  const canClose = isOrganizer && selectedProcurement && ['payment', 'stopped'].includes(selectedProcurement.status);
  const canApproveSupplier = isOrganizer && selectedProcurement && selectedProcurement.status === 'stopped';

  useEffect(() => {
    if (!procurementModalOpen || !selectedProcurement) return;
    setActiveTab('info');
    setAmount('');
    setQuantity('1');
    setNotes('');
    setJoinCity('');
    setVoteResults(null);
    setSelectedSupplierId('');
  }, [procurementModalOpen, selectedProcurement?.id]);

  useEffect(() => {
    if (activeTab === 'vote' && selectedProcurement && canVote) {
      setIsLoadingTab(true);
      Promise.all([
        api.getVoteResults(selectedProcurement.id).catch(() => null),
        api.getSuppliers().catch(() => null),
      ]).then(([results, suppliersResp]) => {
        if (results) setVoteResults(results);
        if (suppliersResp) {
          const list = suppliersResp.results || suppliersResp;
          setSuppliers(Array.isArray(list) ? list : []);
        }
        setIsLoadingTab(false);
      });
    }
    if (activeTab === 'participants' && selectedProcurement) {
      setIsLoadingTab(true);
      api.getParticipants(selectedProcurement.id)
        .then((data) => {
          setParticipants(Array.isArray(data) ? data : data.results || []);
          setIsLoadingTab(false);
        })
        .catch(() => setIsLoadingTab(false));
    }
  }, [activeTab, selectedProcurement?.id]);

  if (!procurementModalOpen || !selectedProcurement) return null;

  const handleJoin = async () => {
    const joinAmount = parseFloat(amount) || 0;
    const joinQuantity = parseFloat(quantity) || 1;
    if (!joinAmount) {
      addToast('Введите сумму участия', 'error');
      return;
    }
    if (!joinCity.trim()) {
      addToast('Введите город получения товара', 'error');
      return;
    }
    await joinProcurement(selectedProcurement.id, { amount: joinAmount, quantity: joinQuantity, notes, city: joinCity });
  };

  const handleLeave = async () => {
    if (!window.confirm('Вы уверены, что хотите выйти из закупки?')) return;
    await leaveProcurement(selectedProcurement.id);
    closeProcurementModal();
  };

  const handleStop = async () => {
    if (!window.confirm('Остановить закупку? Новые участники не смогут присоединиться.')) return;
    await stopProcurement(selectedProcurement.id);
    closeProcurementModal();
  };

  const handleApproveSupplier = async () => {
    if (!selectedSupplierId) {
      addToast('Выберите поставщика', 'error');
      return;
    }
    await approveSupplier(selectedProcurement.id, parseInt(selectedSupplierId));
  };

  const handleClose = async () => {
    if (!window.confirm('Закрыть закупку и перенести в историю?')) return;
    await closeProcurement(selectedProcurement.id);
  };

  const handleSendReceiptTable = async () => {
    try {
      await api.getReceiptTable(selectedProcurement.id);
      addToast('Таблица чеков отправлена поставщику', 'success');
    } catch {
      addToast('Ошибка отправки таблицы чеков', 'error');
    }
  };

  const canSendReceiptTable = isOrganizer && selectedProcurement && ['payment', 'stopped'].includes(selectedProcurement.status);

  const handleCastVote = async () => {
    if (!selectedSupplierId) {
      addToast('Выберите поставщика для голосования', 'error');
      return;
    }
    await castVote(selectedProcurement.id, parseInt(selectedSupplierId), voteComment);
    // Refresh vote results
    api.getVoteResults(selectedProcurement.id)
      .then(setVoteResults)
      .catch(() => {});
  };

  const handleOpenChat = () => {
    setCurrentChat(selectedProcurement.id);
    navigate(`/chat/${selectedProcurement.id}`);
    closeProcurementModal();
  };

  const showVoteTab = canVote || (voteResults && voteResults.total_votes > 0);

  return (
    <div className="modal-overlay active" onClick={(e) => e.target === e.currentTarget && closeProcurementModal()}>
      <div className="modal" style={{ maxWidth: '520px' }}>
        <div className="modal-header">
          <h3 className="modal-title">{selectedProcurement.title}</h3>
          <button className="modal-close" onClick={closeProcurementModal}>
            <CloseIcon />
          </button>
        </div>

        {/* Tabs */}
        <div className="tabs">
          {['info', 'participants', showVoteTab && 'vote'].filter(Boolean).map((tab) => (
            <button
              key={tab}
              className={`tab${activeTab === tab ? ' active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab === 'info' && 'Информация'}
              {tab === 'participants' && 'Участники'}
              {tab === 'vote' && 'Голосование'}
            </button>
          ))}
        </div>

        <div className="modal-body">
          {activeTab === 'info' && (
            <>
              <div className="form-group">
                <label className="form-label">Описание</label>
                <p>{selectedProcurement.description || 'Нет описания'}</p>
              </div>
              <div className="form-group">
                <label className="form-label">Город</label>
                <p>{selectedProcurement.city || 'Не указан'}</p>
              </div>
              {selectedProcurement.unit && (
                <div className="form-group">
                  <label className="form-label">Единица измерения</label>
                  <p>{selectedProcurement.unit}</p>
                </div>
              )}
              {selectedProcurement.commission_percent && (
                <div className="form-group">
                  <label className="form-label">Комиссия организатора</label>
                  <p>{selectedProcurement.commission_percent}%</p>
                </div>
              )}
              <div className="form-group">
                <label className="form-label">Прогресс</label>
                <div className="procurement-progress mt-sm">
                  <div
                    className="procurement-progress-bar"
                    style={{ width: `${Math.min(selectedProcurement.progress || 0, 100)}%` }}
                  />
                </div>
                <p className="mt-sm text-secondary">
                  {formatCurrency(selectedProcurement.current_amount)} из{' '}
                  {formatCurrency(selectedProcurement.target_amount)}
                </p>
              </div>
              <div className="form-group">
                <label className="form-label">Участники</label>
                <p>{selectedProcurement.participant_count || 0} человек</p>
              </div>
              <div className="form-group">
                <label className="form-label">Статус</label>
                <span className={`status-badge status-${selectedProcurement.status}`}>
                  {getStatusText(selectedProcurement.status)}
                </span>
              </div>
              {canJoin && (
                <>
                  <div className="form-group">
                    <label className="form-label">
                      Количество {selectedProcurement.unit ? `(${selectedProcurement.unit})` : ''} *
                    </label>
                    <input
                      type="number"
                      className="form-input"
                      placeholder="1"
                      value={quantity}
                      onChange={(e) => setQuantity(e.target.value)}
                      min="1"
                      step="0.01"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Сумма участия (руб.) *</label>
                    <input
                      type="number"
                      className="form-input"
                      placeholder="Введите сумму"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      min="0"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Город получения товара *</label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Москва"
                      value={joinCity}
                      onChange={(e) => setJoinCity(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Примечание</label>
                    <textarea
                      className="form-input form-textarea"
                      placeholder="Дополнительная информация (необязательно)"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={2}
                    />
                  </div>
                </>
              )}
            </>
          )}

          {activeTab === 'participants' && (
            isLoadingTab ? (
              <p className="text-muted text-center">Загрузка...</p>
            ) : participants.length === 0 ? (
              <p className="text-muted text-center">Нет участников</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {participants.map((p) => (
                  <div key={p.id} style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '8px',
                    background: 'var(--tg-bg-secondary)',
                    borderRadius: '10px',
                  }}>
                    <span>{p.user_name || `Пользователь #${p.user}`}</span>
                    <span className="text-secondary">{p.quantity} × {formatCurrency(p.amount)}</span>
                    <span className={`status-badge status-${p.status}`} style={{ fontSize: '12px' }}>
                      {p.status}
                    </span>
                  </div>
                ))}
              </div>
            )
          )}

          {activeTab === 'vote' && (
            isLoadingTab ? (
              <p className="text-muted text-center">Загрузка...</p>
            ) : (
              <>
                {voteResults && voteResults.total_votes > 0 && (
                  <div className="form-group">
                    <label className="form-label">Результаты голосования ({voteResults.total_votes} голосов)</label>
                    {voteResults.results.map((r) => (
                      <div key={r.supplier_id} style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.4rem 0',
                        borderBottom: '1px solid var(--tg-border)',
                      }}>
                        <span>{r.supplier_name || `Поставщик #${r.supplier_id}`}</span>
                        <span className="text-secondary">{r.vote_count} ({r.percentage}%)</span>
                      </div>
                    ))}
                  </div>
                )}
                {canVote && user && (
                  <div className="form-group">
                    <label className="form-label">Проголосовать за поставщика</label>
                    <select
                      className="form-input form-select"
                      value={selectedSupplierId}
                      onChange={(e) => setSelectedSupplierId(e.target.value)}
                    >
                      <option value="">Выберите поставщика</option>
                      {suppliers.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.first_name} {s.last_name} {s.username ? `(@${s.username})` : ''}
                        </option>
                      ))}
                    </select>
                    <input
                      type="text"
                      className="form-input"
                      style={{ marginTop: '0.5rem' }}
                      placeholder="Комментарий (необязательно)"
                      value={voteComment}
                      onChange={(e) => setVoteComment(e.target.value)}
                    />
                    <button
                      className="btn btn-primary btn-round"
                      style={{ marginTop: '0.5rem', width: '100%' }}
                      onClick={handleCastVote}
                      disabled={!selectedSupplierId}
                    >
                      Проголосовать
                    </button>
                  </div>
                )}
                {canApproveSupplier && (
                  <div className="form-group">
                    <label className="form-label">Утвердить поставщика (только для организатора)</label>
                    <select
                      className="form-input form-select"
                      value={selectedSupplierId}
                      onChange={(e) => setSelectedSupplierId(e.target.value)}
                    >
                      <option value="">Выберите поставщика</option>
                      {suppliers.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.first_name} {s.last_name} {s.username ? `(@${s.username})` : ''}
                        </option>
                      ))}
                    </select>
                    <button
                      className="btn btn-primary btn-round"
                      style={{ marginTop: '0.5rem', width: '100%' }}
                      onClick={handleApproveSupplier}
                      disabled={!selectedSupplierId}
                    >
                      Утвердить поставщика
                    </button>
                  </div>
                )}
              </>
            )
          )}
        </div>

        <div className="modal-footer" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
          <button className="btn btn-secondary btn-round" onClick={handleOpenChat}>
            Открыть чат
          </button>
          {canJoin && (
            <button className="btn btn-primary btn-round" onClick={handleJoin}>
              Участвовать
            </button>
          )}
          {user && selectedProcurement.status !== 'completed' && !isOrganizer && (
            <button className="btn btn-outline btn-round" onClick={handleLeave}
              style={{ color: 'var(--tg-error)', borderColor: 'var(--tg-error)' }}>
              Выйти
            </button>
          )}
          {canStop && (
            <button className="btn btn-outline btn-round" onClick={handleStop}
              style={{ color: 'var(--tg-warning)', borderColor: 'var(--tg-warning)' }}>
              Стоп-сумма
            </button>
          )}
          {canSendReceiptTable && (
            <button className="btn btn-outline btn-round" onClick={handleSendReceiptTable}
              style={{ color: 'var(--tg-primary)', borderColor: 'var(--tg-primary)' }}>
              Отправить таблицу чеков
            </button>
          )}
          {canClose && (
            <button className="btn btn-outline btn-round" onClick={handleClose}
              style={{ color: 'var(--tg-error)', borderColor: 'var(--tg-error)' }}>
              Закрыть закупку
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default ProcurementModal;
