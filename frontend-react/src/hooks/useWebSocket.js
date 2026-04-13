/**
 * useWebSocket — subscribes to the WebSocketManager for a given procurementId.
 *
 * Handles (per issue #282):
 *  - `user_banned` event → forced logout, localStorage/sessionStorage clear, redirect /banned
 *  - `message_edited` / `message_deleted` → in-place store updates (no full reload)
 *  - Event deduplication is done inside WebSocketManager
 *  - All listeners are removed on unmount (no memory leaks)
 */
import { useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { wsManager } from '../services/websocket';
import { useStore } from '../store/useStore';

export function useWebSocket(procurementId) {
  const navigate = useNavigate();
  const { addMessage, updateMessage, removeMessage, logout } = useStore();

  // Stable ref to the navigate function so we don't retrigger the effect
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;

  useEffect(() => {
    if (!procurementId) return;

    wsManager.connect(procurementId);

    // ── Event subscriptions ───────────────────────────────────────────────
    const unsubMessage = wsManager.on('message', (data) => {
      addMessage(data);
    });

    const unsubEdited = wsManager.on('message_edited', (data) => {
      // Only update the specific message — no full list re-render
      if (data.id) {
        updateMessage(data.id, {
          content: data.content,
          is_edited: true,
          updated_at: data.ts ? new Date(data.ts * 1000).toISOString() : new Date().toISOString(),
        });
      }
    });

    const unsubDeleted = wsManager.on('message_deleted', (data) => {
      if (data.id) {
        updateMessage(data.id, {
          is_deleted: true,
          content: '',
          media_url: '',
        });
      }
    });

    // Scenario A (issue #282 Part II §5): user_banned → immediate forced logout
    const unsubBanned = wsManager.on('banned', ({ reason }) => {
      console.warn('[useWebSocket] banned event — forcing logout');
      // Disconnect WS (already closed by wsManager, but call for safety)
      wsManager.disconnect();
      // Clear store state (also removes localStorage keys via logout action)
      logout();
      // Redirect to /banned with reason in state
      navigateRef.current('/banned', { replace: true, state: { reason } });
    });

    return () => {
      unsubMessage();
      unsubEdited();
      unsubDeleted();
      unsubBanned();
      wsManager.disconnect();
    };
  }, [procurementId, addMessage, updateMessage, removeMessage, logout]);

  const sendMessage = useCallback((message) => {
    wsManager.sendMessage(message);
  }, []);

  const sendTyping = useCallback(() => {
    wsManager.sendTyping();
  }, []);

  return { sendMessage, sendTyping };
}
