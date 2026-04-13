import React, { useState } from 'react';
import { useStore } from '../store/useStore';
import { api } from '../services/api';
import {
  formatCurrency,
  getInitials,
  getAvatarColor,
  getRoleText,
} from '../utils/helpers';
import WithdrawModal from './WithdrawModal';

function EditSvg() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function ArrowDownSvg() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 4v16m0 0l-6-6m6 6l6-6" />
    </svg>
  );
}

function ArrowUpSvg() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 20V4m0 0l-6 6m6-6l6 6" />
    </svg>
  );
}

function SwitchSvg() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17 1l4 4-4 4" />
      <path d="M3 11V9a4 4 0 0 1 4-4h14" />
      <path d="M7 23l-4-4 4-4" />
      <path d="M21 13v2a4 4 0 0 1-4 4H3" />
    </svg>
  );
}

function DownloadAppSvg() {
  return (
    <svg className="lk-btn-action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 9a6 6 0 01-6 6m0 0a6 6 0 01-6-6m6 6V3m-6 18h12" />
    </svg>
  );
}

function WalletSvg() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z" />
      <path d="M16 3H8a2 2 0 0 0-2 2v2h12V5a2 2 0 0 0-2-2z" />
      <circle cx="16" cy="14" r="1.5" fill="currentColor" stroke="none" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function LogoutSvg() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

function ChevronRight() {
  return (
    <svg className="lk-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

function ActionRow({ icon, label, onClick, danger }) {
  return (
    <button
      className={`lk-list-action-btn${danger ? ' lk-list-action-btn--danger' : ''}`}
      onClick={onClick}
    >
      <span className={`lk-list-icon-container${danger ? ' lk-list-icon-container--danger' : ''}`}>{icon}</span>
      <span style={{ flex: 1, textAlign: 'left' }}>{label}</span>
      <ChevronRight />
    </button>
  );
}

function SectionHeader({ title }) {
  return <div className="lk-group-header">{title}</div>;
}

function SettingsPage() {
  const { user, openDepositModal, openLoginModal, logout, addToast, theme, toggleTheme } = useStore();
  const [roleSwitchOpen, setRoleSwitchOpen] = useState(false);
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [settingsExpanded, setSettingsExpanded] = useState(false);

  const handleRoleSwitch = async (newRole) => {
    if (newRole === user.role) { setRoleSwitchOpen(false); return; }
    try {
      await api.updateUser(user.coreId || user.id, { role: newRole });
      const updated = await api.getUser(user.coreId || user.id);
      useStore.setState({ user: { ...updated, id: user.id, coreId: updated.id } });
      setRoleSwitchOpen(false);
      addToast(`Роль изменена на: ${getRoleText(newRole)}`, 'success');
    } catch {
      addToast('Ошибка смены роли', 'error');
    }
  };

  if (!user) {
    return (
      <div className="lk-root" style={{ alignItems: 'center', justifyContent: 'center', gap: '1rem' }}>
        <p style={{ color: 'var(--tg-text-muted)' }}>Войдите для доступа к настройкам</p>
        <button className="lk-btn-action" style={{ width: 'auto', flex: 'none', padding: '0 24px' }} onClick={openLoginModal}>
          Войти / Зарегистрироваться
        </button>
      </div>
    );
  }

  const initials = getInitials(user.first_name, user.last_name);
  const avatarBg = getAvatarColor(user.first_name || '');

  return (
    <div className="lk-root">
      {/* ═══ M3 PROFILE HEADER ═══ */}
      <div className="lk-profile-header">
        <div className="lk-profile-cover" style={{ background: `linear-gradient(135deg, ${avatarBg} 0%, ${avatarBg}cc 60%, #3390ec44 100%)` }} />

        <button
          className="lk-profile-edit-btn"
          onClick={() => addToast('Редактирование профиля', 'info')}
          title="Редактировать профиль"
        >
          <EditSvg />
        </button>

        <div className="lk-profile-info-row">
          <div className="lk-profile-avatar" style={{ background: avatarBg }}>
            {initials}
          </div>
          <div className="lk-profile-name-block">
            <div className="lk-profile-name">{user.first_name} {user.last_name || ''}</div>
            <div className="lk-profile-role-badge">{getRoleText(user.role)}</div>
          </div>
        </div>

        <div className="lk-profile-meta-rows">
          {user.phone && (
            <div className="lk-profile-meta-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 10.8a19.79 19.79 0 01-3.07-8.63A2 2 0 012 0h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.09 7.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 14.92z" /></svg>
              <span>{user.phone}</span>
            </div>
          )}
          {user.email && (
            <div className="lk-profile-meta-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" /></svg>
              <span>{user.email}</span>
            </div>
          )}
          {user.username && (
            <div className="lk-profile-meta-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
              <span>@{user.username}</span>
            </div>
          )}
        </div>

        <div className="lk-profile-actions">
          <button className="lk-m3-action-btn" onClick={openDepositModal}>
            <span className="lk-m3-action-btn__icon"><ArrowDownSvg /></span>
            <span className="lk-m3-action-btn__label">Пополнить</span>
          </button>
          <button className="lk-m3-action-btn" onClick={() => setWithdrawOpen(true)}>
            <span className="lk-m3-action-btn__icon"><ArrowUpSvg /></span>
            <span className="lk-m3-action-btn__label">Вывести</span>
          </button>
          <button className="lk-m3-action-btn" onClick={() => setRoleSwitchOpen(true)}>
            <span className="lk-m3-action-btn__icon"><SwitchSvg /></span>
            <span className="lk-m3-action-btn__label">Сменить роль</span>
          </button>
          <button className="lk-m3-action-btn" onClick={() => addToast('Скачать приложение', 'info')}>
            <span className="lk-m3-action-btn__icon"><DownloadAppSvg /></span>
            <span className="lk-m3-action-btn__label">Приложение</span>
          </button>
        </div>
      </div>

      {/* ═══ BALANCE CARD ═══ */}
      <div className="lk-balance-card">
        <div className="lk-balance-card__icon"><WalletSvg /></div>
        <div className="lk-balance-card__info">
          <div className="lk-balance-card__label">Баланс</div>
          <div className="lk-balance-card__value">{formatCurrency(user.balance || 0)}</div>
        </div>
        <button className="lk-balance-card__btn" onClick={openDepositModal}>Пополнить</button>
      </div>

      {/* ═══ SETTINGS SECTIONS ═══ */}
      <div className="lk-body">
        <div className="lk-section-group" style={{ margin: '8px 16px' }}>
          <SectionHeader title="Настройки" />
          <ActionRow
            icon={<SettingsIcon />}
            label="Настройки оформления"
            onClick={() => setSettingsExpanded((prev) => !prev)}
          />
          {settingsExpanded && (
            <div className="lk-content-panel">
              <div className="lk-settings-section">
                <div className="lk-settings-item">
                  <span className="lk-settings-item-label">Тема оформления</span>
                  <div className="lk-theme-switcher">
                    {['light', 'dark'].map((t) => (
                      <button
                        key={t}
                        className={`lk-theme-btn${theme === t ? ' active' : ''}`}
                        onClick={() => {
                          document.documentElement.setAttribute('data-theme', t);
                          localStorage.setItem('theme', t);
                          if (theme !== t) toggleTheme();
                        }}
                      >
                        {t === 'light' ? 'Светлая' : 'Тёмная'}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
          <ActionRow
            icon={<LogoutSvg />}
            label="Выйти из аккаунта"
            danger
            onClick={logout}
          />
        </div>

        <div style={{ height: 24 }} />
      </div>

      {/* ═══ MODALS ═══ */}
      {roleSwitchOpen && (
        <div className="modal-overlay active" onClick={(e) => e.target === e.currentTarget && setRoleSwitchOpen(false)}>
          <div className="modal" style={{ maxWidth: 320 }}>
            <div className="modal-header">
              <h3 className="modal-title">Сменить роль</h3>
              <button className="modal-close" onClick={() => setRoleSwitchOpen(false)}>×</button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                { value: 'buyer', label: 'Покупатель' },
                { value: 'organizer', label: 'Организатор' },
                { value: 'supplier', label: 'Поставщик' },
              ].map(({ value, label }) => (
                <button
                  key={value}
                  className={`lk-btn-action${user.role === value ? '' : ' lk-btn-action--outline'}`}
                  style={{ height: 44 }}
                  onClick={() => handleRoleSwitch(value)}
                >
                  {label}{user.role === value && ' (текущая)'}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <WithdrawModal isOpen={withdrawOpen} onClose={() => setWithdrawOpen(false)} />
    </div>
  );
}

export default SettingsPage;
