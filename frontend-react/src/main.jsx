import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/telegram.css';

/**
 * ErrorBoundary catches uncaught render-time errors and shows a user-friendly
 * message instead of leaving the page blank.
 *
 * In production React unmounts the whole tree on an uncaught render error,
 * resulting in a completely blank page.  This boundary intercepts those errors
 * so users see an actionable message rather than nothing.
 *
 * Must be a class component — React's functional-component API does not support
 * componentDidCatch / getDerivedStateFromError.
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary] Uncaught render error:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          padding: '24px',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          textAlign: 'center',
          color: '#333',
        }}>
          <h1 style={{ fontSize: '24px', marginBottom: '12px' }}>Что-то пошло не так</h1>
          <p style={{ color: '#666', marginBottom: '20px' }}>
            Произошла непредвиденная ошибка. Пожалуйста, обновите страницу.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '10px 24px',
              background: '#3390ec',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              fontSize: '16px',
              cursor: 'pointer',
            }}
          >
            Обновить страницу
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
