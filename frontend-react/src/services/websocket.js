/**
 * WebSocketManager — Centrifugo-backed real-time connection.
 *
 * Key guarantees (per issue #282):
 *  - Exponential backoff reconnection (max 32 s) to avoid thundering herd
 *  - Event deduplication via eventId — prevents double-processing on reconnect
 *  - `user_banned` event → immediate forced logout + redirect to /banned
 *  - AbortController-based cleanup when component unmounts
 *  - All pending fetch requests are aborted on ban
 */

// Global AbortController registry — populated by api.js interceptor
const pendingFetchControllers = new Set();

export function registerFetchController(controller) {
  pendingFetchControllers.add(controller);
  return () => pendingFetchControllers.delete(controller);
}

function abortAllPendingFetches() {
  for (const ctrl of pendingFetchControllers) {
    try { ctrl.abort(); } catch (_) {}
  }
  pendingFetchControllers.clear();
}

class WebSocketManager {
  constructor() {
    this.connection = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.baseDelay = 1000; // 1 s
    this.maxDelay = 32000; // 32 s cap
    this.listeners = new Map();
    this.seenEventIds = new Set(); // deduplication window (cleared on reconnect)
    this._reconnectTimer = null;
    this._currentProcurementId = null;
  }

  connect(procurementId) {
    this._currentProcurementId = procurementId;
    const token = localStorage.getItem('wsToken') || localStorage.getItem('authToken') || '';
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/procurement/${procurementId}/?token=${token}`;

    this.connection = new WebSocket(wsUrl);

    this.connection.onopen = () => {
      console.log('[WS] connected');
      this.reconnectAttempts = 0;
      // Do NOT clear seenEventIds on reconnect — keep the window to deduplicate
      // messages that may be re-delivered by the broker
      this.emit('connected');
    };

    this.connection.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this._handleMessage(data);
      } catch (error) {
        console.error('[WS] message parse error:', error);
      }
    };

    this.connection.onclose = (ev) => {
      console.log('[WS] disconnected', ev.code, ev.reason);
      this.emit('disconnected');
      // 1000 = normal close (e.g. forced on ban/logout) — do not reconnect
      if (ev.code !== 1000) {
        this._scheduleReconnect(procurementId);
      }
    };

    this.connection.onerror = (error) => {
      console.error('[WS] error:', error);
      this.emit('error', error);
    };
  }

  disconnect() {
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this.connection) {
      // Close with 1000 (normal) so onclose won't trigger reconnect
      this.connection.close(1000, 'client disconnect');
      this.connection = null;
    }
    this._currentProcurementId = null;
  }

  send(data) {
    if (this.connection && this.connection.readyState === WebSocket.OPEN) {
      this.connection.send(JSON.stringify(data));
    }
  }

  /**
   * Deduplicate by eventId.
   * Centrifugo can re-deliver messages on reconnect; we track IDs in a
   * sliding window (max 500 entries) to drop duplicates silently.
   */
  _isDuplicate(data) {
    const eventId = data.id || data.event_id || data.eventId;
    if (!eventId) return false;
    if (this.seenEventIds.has(eventId)) return true;
    this.seenEventIds.add(eventId);
    // Keep window bounded
    if (this.seenEventIds.size > 500) {
      const first = this.seenEventIds.values().next().value;
      this.seenEventIds.delete(first);
    }
    return false;
  }

  _handleMessage(data) {
    // Deduplicate before dispatching
    if (this._isDuplicate(data)) {
      console.debug('[WS] duplicate event dropped:', data.id || data.event_id);
      return;
    }

    switch (data.type) {
      case 'user_banned':
        // CRITICAL: Scenario A — immediate forced logout on ban
        this._handleBan(data);
        break;
      case 'message':
        this.emit('message', data);
        break;
      case 'message_edited':
        this.emit('message_edited', data);
        break;
      case 'message_deleted':
        this.emit('message_deleted', data);
        break;
      case 'typing':
        this.emit('typing', data);
        break;
      case 'user_joined':
        this.emit('user_joined', data.user || data);
        break;
      case 'user_left':
        this.emit('user_left', data.user || data);
        break;
      case 'user_invited':
        this.emit('user_invited', data);
        break;
      case 'vote_cast':
      case 'vote_changed':
        this.emit('vote_update', data);
        break;
      case 'voting_closed':
        this.emit('voting_closed', data);
        break;
      case 'supplier_document_sent':
        this.emit('supplier_document_sent', data);
        break;
      case 'chat_deleted':
        this.emit('chat_deleted', data);
        break;
      default:
        this.emit(data.type, data);
    }
  }

  /**
   * Scenario A (issue #282 Part II §2):
   * On `user_banned`:
   *  1. Terminate WebSocket with normal close (no reconnect)
   *  2. Abort all in-flight fetch requests
   *  3. Clear all local storage and session storage
   *  4. Emit `banned` event so React components can show modal/redirect
   */
  _handleBan(data) {
    console.warn('[WS] user_banned event received — forcing logout');

    // 1. Close WebSocket (code 1000 = normal, won't trigger reconnect)
    if (this.connection) {
      this.connection.close(1000, 'user banned');
      this.connection = null;
    }

    // 2. Abort all in-flight requests
    abortAllPendingFetches();

    // 3. Clear storage
    localStorage.clear();
    sessionStorage.clear();

    // 4. Notify listeners
    this.emit('banned', {
      reason: data.reason || data.ban_reason || 'Your account has been suspended.',
    });
  }

  /**
   * Exponential backoff reconnect: delay = min(base * 2^attempt, maxDelay) + jitter
   */
  _scheduleReconnect(procurementId) {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn('[WS] max reconnect attempts reached');
      this.emit('max_reconnect_reached');
      return;
    }
    this.reconnectAttempts += 1;
    const expDelay = Math.min(
      this.baseDelay * Math.pow(2, this.reconnectAttempts - 1),
      this.maxDelay,
    );
    // Add up to 20% jitter to spread reconnect storms
    const jitter = Math.random() * expDelay * 0.2;
    const delay = Math.round(expDelay + jitter);
    console.log(`[WS] reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
    this._reconnectTimer = setTimeout(() => this.connect(procurementId), delay);
  }

  sendTyping(isTyping = true) {
    this.send({ type: 'typing', is_typing: isTyping });
  }

  sendMessage(text) {
    this.send({ type: 'message', text });
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);
    return () => this.off(event, callback);
  }

  off(event, callback) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.delete(callback);
    }
  }

  emit(event, data) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach((callback) => {
        try { callback(data); } catch (err) {
          console.error(`[WS] listener error for event "${event}":`, err);
        }
      });
    }
  }
}

export const wsManager = new WebSocketManager();
