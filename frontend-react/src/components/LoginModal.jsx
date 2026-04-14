import React, { useState, useEffect, useRef } from 'react';
import { useStore } from '../store/useStore';

// ─── Validation helpers ────────────────────────────────────────────────────────

function validatePhone(phone) {
  if (!phone || !phone.trim()) return 'Номер телефона обязателен';
  if (!/^\+?[1-9]\d{6,19}$/.test(phone.trim())) return 'Введите корректный номер телефона (напр. +79001234567)';
  return null;
}

function validateRegisterForm(formData) {
  const errors = {};
  const phoneErr = validatePhone(formData.phone);
  if (phoneErr) errors.phone = phoneErr;
  if (!formData.email || !formData.email.trim()) {
    errors.email = 'Email обязателен';
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email.trim())) {
    errors.email = 'Введите корректный email';
  }
  if (!formData.role) {
    errors.role = 'Роль обязательна';
  }
  return errors;
}

// ─── Icons ────────────────────────────────────────────────────────────────────

function TelegramPhoneIcon() {
  return (
    <svg width="160" height="160" viewBox="0 0 160 160" fill="none">
      <circle cx="80" cy="80" r="80" fill="var(--tg-primary)" opacity="0.1" />
      <circle cx="80" cy="80" r="60" fill="var(--tg-primary)" opacity="0.15" />
      <rect x="58" y="32" width="44" height="96" rx="10" fill="var(--tg-primary)" />
      <rect x="62" y="42" width="36" height="68" rx="4" fill="white" />
      <circle cx="80" cy="118" r="5" fill="white" opacity="0.8" />
    </svg>
  );
}

function TelegramRegisterIcon() {
  return (
    <svg width="160" height="160" viewBox="0 0 160 160" fill="none">
      <circle cx="80" cy="80" r="80" fill="var(--tg-primary)" opacity="0.1" />
      <circle cx="80" cy="80" r="60" fill="var(--tg-primary)" opacity="0.15" />
      <circle cx="80" cy="62" r="20" fill="var(--tg-primary)" />
      <path d="M50 110 C50 90 65 80 80 80 C95 80 110 90 110 110" stroke="var(--tg-primary)" strokeWidth="6" fill="none" strokeLinecap="round" />
      <circle cx="110" cy="58" r="14" fill="var(--tg-success, #4fae4e)" />
      <line x1="110" y1="52" x2="110" y2="64" stroke="white" strokeWidth="3" strokeLinecap="round" />
      <line x1="104" y1="58" x2="116" y2="58" stroke="white" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

function OtpIcon() {
  return (
    <svg width="160" height="160" viewBox="0 0 160 160" fill="none">
      <circle cx="80" cy="80" r="80" fill="var(--tg-primary)" opacity="0.1" />
      <circle cx="80" cy="80" r="60" fill="var(--tg-primary)" opacity="0.15" />
      <rect x="40" y="55" width="80" height="56" rx="8" fill="var(--tg-primary)" />
      <path d="M40 75 L80 95 L120 75" stroke="white" strokeWidth="4" fill="none" strokeLinecap="round" />
      <circle cx="80" cy="118" r="14" fill="var(--tg-success, #4fae4e)" />
      <path d="M73 118 L78 123 L88 113" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

const RESEND_COOLDOWN_SECONDS = 30;

function LoginModal() {
  const {
    loginModalOpen,
    login, confirmLogin,
    register, confirmRegistration,
    resendOtp,
    isLoading, error,
    otpPending,
  } = useStore();

  const [activeTab, setActiveTab] = useState('login');

  // Login step 1: phone
  const [loginData, setLoginData] = useState({ phone: '' });
  const [loginErrors, setLoginErrors] = useState({});

  // Registration step 1: phone + email + name + role
  const [registerData, setRegisterData] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    email: '',
    role: 'buyer',
  });
  const [formErrors, setFormErrors] = useState({});

  // OTP step (shared for login and registration)
  const [otpValue, setOtpValue] = useState('');

  // Resend cooldown timer
  const [resendCooldown, setResendCooldown] = useState(0);
  const resendTimerRef = useRef(null);

  // Start 30-second cooldown when OTP screen is shown
  useEffect(() => {
    if (otpPending) {
      setResendCooldown(RESEND_COOLDOWN_SECONDS);
    } else {
      setResendCooldown(0);
      if (resendTimerRef.current) {
        clearInterval(resendTimerRef.current);
        resendTimerRef.current = null;
      }
    }
  }, [otpPending]);

  useEffect(() => {
    if (resendCooldown <= 0) {
      if (resendTimerRef.current) {
        clearInterval(resendTimerRef.current);
        resendTimerRef.current = null;
      }
      return;
    }
    resendTimerRef.current = setInterval(() => {
      setResendCooldown((prev) => {
        if (prev <= 1) {
          clearInterval(resendTimerRef.current);
          resendTimerRef.current = null;
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => {
      if (resendTimerRef.current) {
        clearInterval(resendTimerRef.current);
        resendTimerRef.current = null;
      }
    };
  }, [resendCooldown]);

  // ─── Handlers ──────────────────────────────────────────────────────────────

  const handleLoginChange = (e) => {
    const { name, value } = e.target;
    setLoginData((prev) => ({ ...prev, [name]: value }));
    if (loginErrors[name]) setLoginErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  const handleRegisterChange = (e) => {
    const { name, value } = e.target;
    setRegisterData((prev) => ({ ...prev, [name]: value }));
    if (formErrors[name]) setFormErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  // Step 1: submit phone to initiate login
  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    const phoneErr = validatePhone(loginData.phone);
    if (phoneErr) {
      setLoginErrors({ phone: phoneErr });
      return;
    }
    setLoginErrors({});
    try {
      await login(loginData);
    } catch (_) {}
  };

  // Step 2: submit OTP to confirm login
  const handleLoginOtpSubmit = async (e) => {
    e.preventDefault();
    if (!otpValue.trim()) return;
    try {
      await confirmLogin({ phone: otpPending.phone, otp: otpValue.trim() });
    } catch (_) {}
  };

  // Step 1: submit phone+email to initiate registration
  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    const errors = validateRegisterForm(registerData);
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }
    setFormErrors({});
    try {
      await register(registerData);
    } catch (_) {}
  };

  // Step 2: submit OTP to confirm registration
  const handleRegisterOtpSubmit = async (e) => {
    e.preventDefault();
    if (!otpValue.trim()) return;
    try {
      await confirmRegistration({ phone: otpPending.phone, otp: otpValue.trim() });
    } catch (_) {}
  };

  const handleBackFromOtp = () => {
    useStore.setState({ otpPending: null });
    setOtpValue('');
  };

  const handleResendOtp = async () => {
    if (resendCooldown > 0 || isLoading) return;
    try {
      await resendOtp();
      setResendCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (_) {}
  };

  if (!loginModalOpen) return null;

  // ─── OTP confirmation screen ───────────────────────────────────────────────

  if (otpPending) {
    const isLogin = otpPending.context === 'login';
    const handleOtpSubmit = isLogin ? handleLoginOtpSubmit : handleRegisterOtpSubmit;

    return (
      <div className="auth-screen">
        <div className="auth-container">
          <div className="auth-logo">
            <OtpIcon />
          </div>

          <h1 className="auth-title">Введите код</h1>
          <p className="auth-subtitle">
            {otpPending.maskedEmail
              ? `Код подтверждения отправлен на почту ${otpPending.maskedEmail}`
              : 'Код подтверждения отправлен на вашу электронную почту.'}
          </p>

          <form className="auth-form" onSubmit={handleOtpSubmit}>
            {error && <div className="form-error-banner">{error}</div>}

            <div className={`form-group${otpValue ? ' has-value' : ''}`}>
              <label className="form-label">Код подтверждения</label>
              <input
                type="text"
                className="form-input"
                name="otp"
                value={otpValue}
                onChange={(e) => setOtpValue(e.target.value)}
                autoComplete="one-time-code"
                inputMode="numeric"
                maxLength={8}
                autoFocus
              />
            </div>

            <button
              type="submit"
              className="auth-btn"
              disabled={isLoading || !otpValue.trim()}
            >
              {isLoading && <span className="auth-spinner" />}
              {isLoading ? 'Проверка...' : 'Подтвердить'}
            </button>

            <p className="form-hint" style={{ textAlign: 'center' }}>
              {resendCooldown > 0 ? (
                <span className="form-hint-muted">
                  Отправить код повторно через {resendCooldown} с.
                </span>
              ) : (
                <button
                  type="button"
                  className="form-link-btn"
                  onClick={handleResendOtp}
                  disabled={isLoading}
                >
                  Отправить код повторно
                </button>
              )}
            </p>

            <p className="form-hint" style={{ textAlign: 'center' }}>
              <button
                type="button"
                className="form-link-btn"
                onClick={handleBackFromOtp}
              >
                Назад
              </button>
            </p>
          </form>
        </div>
      </div>
    );
  }

  // ─── Main login / register screen ─────────────────────────────────────────

  return (
    <div className="auth-screen">
      <div className="auth-container">
        {/* Tab switcher */}
        <div className="auth-tabs">
          <button
            className={`auth-tab${activeTab === 'login' ? ' active' : ''}`}
            onClick={() => setActiveTab('login')}
            type="button"
          >
            Вход
          </button>
          <button
            className={`auth-tab${activeTab === 'register' ? ' active' : ''}`}
            onClick={() => setActiveTab('register')}
            type="button"
          >
            Регистрация
          </button>
        </div>

        {activeTab === 'login' ? (
          <>
            <div className="auth-logo">
              <TelegramPhoneIcon />
            </div>

            <h1 className="auth-title">GroupBuy</h1>
            <p className="auth-subtitle">
              Войдите по номеру телефона
            </p>

            <form className="auth-form" onSubmit={handleLoginSubmit}>
              {error && <div className="form-error-banner">{error}</div>}

              <div className={`form-group${loginData.phone ? ' has-value' : ''}${loginErrors.phone ? ' form-group-error' : ''}`}>
                <label className="form-label">Номер телефона</label>
                <input
                  type="tel"
                  className={`form-input${loginErrors.phone ? ' form-input-error' : ''}`}
                  name="phone"
                  value={loginData.phone}
                  onChange={handleLoginChange}
                  autoComplete="tel"
                  placeholder="+79001234567"
                />
                {loginErrors.phone && (
                  <span className="form-field-error">{loginErrors.phone}</span>
                )}
              </div>

              <button
                type="submit"
                className="auth-btn"
                disabled={isLoading}
              >
                {isLoading && <span className="auth-spinner" />}
                {isLoading ? 'Загрузка...' : 'Получить код'}
              </button>

              <p className="form-hint" style={{ textAlign: 'center' }}>
                Нет аккаунта?{' '}
                <button
                  type="button"
                  className="form-link-btn"
                  onClick={() => setActiveTab('register')}
                >
                  Зарегистрироваться
                </button>
              </p>
            </form>
          </>
        ) : (
          <>
            <div className="auth-logo">
              <TelegramRegisterIcon />
            </div>

            <h1 className="auth-title">Регистрация</h1>
            <p className="auth-subtitle">
              Создайте аккаунт для участия в совместных закупках
            </p>

            <form className="auth-form" onSubmit={handleRegisterSubmit}>
              {error && <div className="form-error-banner">{error}</div>}

              <div className={`form-group${registerData.phone ? ' has-value' : ''}${formErrors.phone ? ' form-group-error' : ''}`}>
                <label className="form-label">Номер телефона *</label>
                <input
                  type="tel"
                  className={`form-input${formErrors.phone ? ' form-input-error' : ''}`}
                  name="phone"
                  required
                  value={registerData.phone}
                  onChange={handleRegisterChange}
                  autoComplete="tel"
                  placeholder="+79001234567"
                />
                {formErrors.phone && (
                  <span className="form-field-error">{formErrors.phone}</span>
                )}
              </div>

              <div className={`form-group${registerData.email ? ' has-value' : ''}${formErrors.email ? ' form-group-error' : ''}`}>
                <label className="form-label">Email *</label>
                <input
                  type="email"
                  className={`form-input${formErrors.email ? ' form-input-error' : ''}`}
                  name="email"
                  required
                  value={registerData.email}
                  onChange={handleRegisterChange}
                  autoComplete="email"
                />
                {formErrors.email && (
                  <span className="form-field-error">{formErrors.email}</span>
                )}
              </div>

              <div className={`form-group${registerData.first_name ? ' has-value' : ''}`}>
                <label className="form-label">Имя</label>
                <input
                  type="text"
                  className="form-input"
                  name="first_name"
                  value={registerData.first_name}
                  onChange={handleRegisterChange}
                  autoComplete="given-name"
                />
              </div>

              <div className={`form-group${registerData.last_name ? ' has-value' : ''}`}>
                <label className="form-label">Фамилия</label>
                <input
                  type="text"
                  className="form-input"
                  name="last_name"
                  value={registerData.last_name}
                  onChange={handleRegisterChange}
                  autoComplete="family-name"
                />
              </div>

              <div className="form-group has-value">
                <label className="form-label">Роль *</label>
                <select
                  className={`form-input form-select${formErrors.role ? ' form-input-error' : ''}`}
                  name="role"
                  required
                  value={registerData.role}
                  onChange={handleRegisterChange}
                >
                  <option value="buyer">Покупатель</option>
                  <option value="organizer">Организатор</option>
                  <option value="supplier">Поставщик</option>
                </select>
                {formErrors.role && (
                  <span className="form-field-error">{formErrors.role}</span>
                )}
              </div>

              <button
                type="submit"
                className="auth-btn"
                disabled={isLoading}
              >
                {isLoading && <span className="auth-spinner" />}
                {isLoading ? 'Загрузка...' : 'Зарегистрироваться'}
              </button>

              <p className="form-hint" style={{ textAlign: 'center' }}>
                Уже есть аккаунт?{' '}
                <button
                  type="button"
                  className="form-link-btn"
                  onClick={() => setActiveTab('login')}
                >
                  Войти
                </button>
              </p>
            </form>
          </>
        )}
      </div>
    </div>
  );
}

export default LoginModal;
