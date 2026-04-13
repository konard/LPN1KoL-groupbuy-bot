/**
 * BannedPage — shown immediately after the server emits a `user_banned` WebSocket event.
 *
 * Scenario A (issue #282 Part II §5):
 *  - All localStorage / sessionStorage is already cleared before this page renders
 *  - The page shows the ban reason (if provided) and prevents navigation back to the app
 */
import React from 'react';
import { useLocation } from 'react-router-dom';

function BannedPage() {
  const { state } = useLocation();
  const reason = state?.reason || 'Your account has been suspended.';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        padding: '2rem',
        textAlign: 'center',
        background: 'var(--tg-bg, #fff)',
        color: 'var(--text-primary, #111)',
      }}
    >
      <div
        style={{
          fontSize: '4rem',
          marginBottom: '1rem',
          lineHeight: 1,
        }}
      >
        🚫
      </div>
      <h1
        style={{
          fontSize: '1.75rem',
          fontWeight: 700,
          marginBottom: '0.75rem',
          color: 'var(--tg-error, #e53e3e)',
        }}
      >
        Account Suspended
      </h1>
      <p
        style={{
          fontSize: '1rem',
          color: 'var(--text-secondary, #666)',
          maxWidth: 420,
          marginBottom: '1.5rem',
        }}
      >
        {reason}
      </p>
      <p
        style={{
          fontSize: '0.85rem',
          color: 'var(--text-secondary, #888)',
        }}
      >
        If you believe this is a mistake, please contact support.
      </p>
    </div>
  );
}

export default BannedPage;
