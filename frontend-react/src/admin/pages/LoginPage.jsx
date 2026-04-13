/**
 * Admin Login Page
 * Uses a standard HTML form for credential input
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAdminStore } from '../store/adminStore';
import '../styles/admin.css';

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, checkAuth, isLoading, error, clearError } = useAdminStore();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  useEffect(() => {
    let cancelled = false;
    checkAuth().then((isAuth) => {
      if (!cancelled && isAuth) {
        navigate('/admin-panel');
      }
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    clearError();
    const success = await login(username, password);
    if (success) {
      navigate('/admin-panel');
    }
  };

  return (
    <div className="admin-login-page">
      <div className="admin-login-card">
        <h1>GroupBuy Admin</h1>
        <p className="admin-login-subtitle">Вход в панель администратора</p>

        {error && <div className="admin-login-error">{error}</div>}

        <form className="admin-login-form" onSubmit={handleSubmit}>
          <div className="admin-form-group">
            <label htmlFor="admin-username">Имя пользователя</label>
            <input
              id="admin-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
              disabled={isLoading}
            />
          </div>

          <div className="admin-form-group">
            <label htmlFor="admin-password">Пароль</label>
            <input
              id="admin-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              disabled={isLoading}
            />
          </div>

          <button
            type="submit"
            className="admin-login-btn"
            disabled={isLoading}
          >
            {isLoading ? 'Вход...' : 'Войти'}
          </button>
        </form>

        <div className="admin-login-footer">
          <details className="admin-login-help">
            <summary>Как создать администратора?</summary>
            <ol>
              <li>Подключитесь к серверу по SSH</li>
              <li>
                Выполните команду:
                <pre><code>docker compose exec django-admin python manage.py createsuperuser</code></pre>
              </li>
              <li>Введите имя пользователя, email и пароль</li>
              <li>Войдите в панель с созданными данными</li>
            </ol>
            <p>
              Адрес панели: <strong>{window.location.origin}/admin-panel/</strong>
            </p>
          </details>
        </div>
      </div>
    </div>
  );
}
