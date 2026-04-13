/**
 * WASM Service - Provides high-performance Rust+WebAssembly functions
 * for client-side data processing.
 *
 * Functions gracefully fall back to JavaScript implementations
 * if WASM fails to load.
 */

let wasmModule = null;
let wasmReady = false;
let wasmLoadPromise = null;

/**
 * Initialize WASM module (lazy-loaded on first use)
 */
async function initWasm() {
  if (wasmReady) return wasmModule;
  if (wasmLoadPromise) return wasmLoadPromise;

  wasmLoadPromise = (async () => {
    try {
      const wasm = await import('../wasm-pkg/groupbuy_wasm.js');
      await wasm.default();
      wasmModule = wasm;
      wasmReady = true;
      return wasm;
    } catch (err) {
      console.warn('[WASM] Failed to load WebAssembly module, using JS fallbacks:', err.message);
      wasmReady = false;
      return null;
    }
  })();

  return wasmLoadPromise;
}

/**
 * Check if WASM is loaded and available
 */
export function isWasmReady() {
  return wasmReady;
}

/**
 * Ensure WASM is loaded. Call this early in the app lifecycle.
 */
export async function loadWasm() {
  return initWasm();
}

// ──────────────────────────────────────────────
// Validation functions
// ──────────────────────────────────────────────

export function validatePhone(phone) {
  if (wasmReady) {
    return wasmModule.validate_phone(phone);
  }
  // JS fallback
  const cleaned = phone.replace(/[^\d+]/g, '');
  if (!cleaned) return true;
  return /^\+\d{10,15}$/.test(cleaned);
}

export function validateEmail(email) {
  if (wasmReady) {
    return wasmModule.validate_email(email);
  }
  // JS fallback
  if (!email) return true;
  const parts = email.split('@');
  if (parts.length !== 2) return false;
  return parts[0].length > 0 && parts[1].includes('.') && parts[1].length > 2;
}

export function validateProcurementForm(title, description, city, targetAmount, deadlineMs) {
  if (wasmReady) {
    return JSON.parse(wasmModule.validate_procurement_form(title, description, city, targetAmount, deadlineMs));
  }
  // JS fallback
  const errors = {};
  if (!title.trim()) errors.title = 'Название обязательно';
  else if (title.length > 200) errors.title = 'Название не должно превышать 200 символов';
  if (!description.trim()) errors.description = 'Описание обязательно';
  if (!city.trim()) errors.city = 'Город обязателен';
  if (targetAmount <= 0) errors.target_amount = 'Целевая сумма должна быть положительной';
  if (deadlineMs <= Date.now()) errors.deadline = 'Дедлайн должен быть в будущем';
  return errors;
}

// ──────────────────────────────────────────────
// Formatting functions
// ──────────────────────────────────────────────

export function formatCurrency(amount) {
  if (wasmReady) {
    return wasmModule.format_currency(amount || 0);
  }
  // JS fallback
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount || 0);
}

export function calculateProgress(current, target) {
  if (wasmReady) {
    return wasmModule.calculate_progress(current, target);
  }
  // JS fallback
  if (target <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((current / target) * 100)));
}

export function daysUntil(deadlineMs) {
  if (wasmReady) {
    return wasmModule.days_until(deadlineMs);
  }
  // JS fallback
  const diff = deadlineMs - Date.now();
  return Math.max(0, Math.floor(diff / 86400000));
}

export function formatRelativeTime(timestampMs) {
  if (wasmReady) {
    return wasmModule.format_relative_time(timestampMs);
  }
  // JS fallback
  const diff = Math.floor((Date.now() - timestampMs) / 1000);
  if (diff < 60) return 'только что';
  if (diff < 3600) return `${Math.floor(diff / 60)} мин. назад`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} ч. назад`;
  const days = Math.floor(diff / 86400);
  if (days === 1) return 'вчера';
  return `${days} дн. назад`;
}

export function getAvatarColor(name) {
  if (wasmReady) {
    return wasmModule.get_avatar_color(name || '');
  }
  // JS fallback
  const colors = ['#e17076', '#faa774', '#a695e7', '#7bc862', '#6ec9cb', '#65aadd', '#ee7aae', '#f5a623'];
  let hash = 0;
  const str = name || '';
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export function getInitials(firstName, lastName = '') {
  if (wasmReady) {
    return wasmModule.get_initials(firstName || '', lastName || '');
  }
  // JS fallback
  const first = firstName ? firstName.charAt(0).toUpperCase() : '';
  const last = lastName ? lastName.charAt(0).toUpperCase() : '';
  return first + last || '?';
}

export function escapeHtml(text) {
  if (wasmReady) {
    return wasmModule.escape_html(text);
  }
  // JS fallback
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

export function formatMessageText(text) {
  if (wasmReady) {
    return wasmModule.format_message_text(text || '');
  }
  // JS fallback
  if (!text) return '';
  let formatted = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  formatted = formatted.replace(
    /(https?:\/\/[^\s]+)/g,
    '<a href="$1" target="_blank" rel="noopener">$1</a>'
  );
  formatted = formatted.replace(/\n/g, '<br>');
  return formatted;
}

export function generatePlatformUserId() {
  if (wasmReady) {
    return wasmModule.generate_platform_user_id();
  }
  // JS fallback
  return `web_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// ──────────────────────────────────────────────
// High-performance batch processing functions
// ──────────────────────────────────────────────

/**
 * Batch-process procurements: compute progress, days left, format currency in one WASM pass.
 * Falls back to JS-based processing if WASM is not available.
 */
export function batchProcessProcurements(procurements) {
  if (wasmReady && Array.isArray(procurements) && procurements.length > 0) {
    try {
      const result = wasmModule.batch_process_procurements(JSON.stringify(procurements));
      return JSON.parse(result);
    } catch (err) {
      console.warn('[WASM] batch_process_procurements failed, using JS fallback:', err.message);
    }
  }
  // JS fallback
  const now = Date.now();
  return (procurements || []).map(p => {
    const current = p.current_amount || 0;
    const target = p.target_amount || 0;
    const progress = target > 0 ? Math.min(100, Math.max(0, Math.round((current / target) * 100))) : 0;
    let daysLeft = null;
    if (p.deadline) {
      const diff = new Date(p.deadline).getTime() - now;
      daysLeft = Math.max(0, Math.ceil(diff / 86400000));
    }
    return {
      ...p,
      progress,
      days_left: daysLeft,
      formatted_current: formatCurrency(current),
      formatted_target: formatCurrency(target),
    };
  });
}

/**
 * Fuzzy search procurements by query string.
 * Returns array of { id, score } sorted by relevance.
 */
export function searchProcurements(procurements, query) {
  if (wasmReady && Array.isArray(procurements) && procurements.length > 0 && query) {
    try {
      return JSON.parse(wasmModule.search_procurements(JSON.stringify(procurements), query));
    } catch (err) {
      console.warn('[WASM] search_procurements failed, using JS fallback:', err.message);
    }
  }
  // JS fallback
  if (!query || !query.trim()) return [];
  const words = query.toLowerCase().split(/\s+/);
  const results = [];
  for (const p of (procurements || [])) {
    let score = 0;
    const title = (p.title || '').toLowerCase();
    const desc = (p.description || '').toLowerCase();
    const city = (p.city || '').toLowerCase();
    for (const word of words) {
      if (title.includes(word)) score += 10;
      if (city.includes(word)) score += 5;
      if (desc.includes(word)) score += 2;
    }
    if (score > 0) results.push({ id: p.id, score });
  }
  results.sort((a, b) => b.score - a.score);
  return results;
}

/**
 * Sort procurements by field.
 * Returns array of sorted procurement IDs.
 */
export function sortProcurements(procurements, sortBy, order = 'asc') {
  if (wasmReady && Array.isArray(procurements) && procurements.length > 0) {
    try {
      return JSON.parse(wasmModule.sort_procurements(JSON.stringify(procurements), sortBy, order));
    } catch (err) {
      console.warn('[WASM] sort_procurements failed, using JS fallback:', err.message);
    }
  }
  // JS fallback
  const sorted = [...(procurements || [])].sort((a, b) => {
    let cmp = 0;
    switch (sortBy) {
      case 'title': cmp = (a.title || '').localeCompare(b.title || ''); break;
      case 'amount': cmp = (a.current_amount || 0) - (b.current_amount || 0); break;
      case 'participants': cmp = (a.participant_count || 0) - (b.participant_count || 0); break;
      default: cmp = 0;
    }
    return order === 'desc' ? -cmp : cmp;
  });
  return sorted.map(p => p.id);
}

/**
 * Aggregate procurement statistics.
 * Returns object with total_count, active_count, total_amount, etc.
 */
export function aggregateProcurementStats(procurements) {
  if (wasmReady && Array.isArray(procurements) && procurements.length > 0) {
    try {
      return JSON.parse(wasmModule.aggregate_procurement_stats(JSON.stringify(procurements)));
    } catch (err) {
      console.warn('[WASM] aggregate_procurement_stats failed, using JS fallback:', err.message);
    }
  }
  // JS fallback
  const stats = {
    total_count: 0,
    active_count: 0,
    total_amount: 0,
    total_target: 0,
    overall_progress: 0,
    avg_participants: 0,
    cities: [],
    by_status: {},
  };
  for (const p of (procurements || [])) {
    stats.total_count++;
    if (p.status === 'active') stats.active_count++;
    stats.total_amount += p.current_amount || 0;
    stats.total_target += p.target_amount || 0;
    const status = p.status || 'unknown';
    stats.by_status[status] = (stats.by_status[status] || 0) + 1;
    if (p.city && !stats.cities.includes(p.city)) stats.cities.push(p.city);
  }
  if (stats.total_target > 0) {
    stats.overall_progress = Math.min(100, Math.round((stats.total_amount / stats.total_target) * 100));
  }
  if (stats.total_count > 0) {
    const totalPart = (procurements || []).reduce((s, p) => s + (p.participant_count || 0), 0);
    stats.avg_participants = Math.round(totalPart / stats.total_count * 10) / 10;
  }
  return stats;
}

/**
 * Batch-process messages: format text, compute date groups, format times in one WASM pass.
 */
export function batchProcessMessages(messages, currentUserId) {
  if (wasmReady && Array.isArray(messages) && messages.length > 0) {
    try {
      return JSON.parse(wasmModule.batch_process_messages(JSON.stringify(messages), BigInt(currentUserId || 0)));
    } catch (err) {
      console.warn('[WASM] batch_process_messages failed, using JS fallback:', err.message);
    }
  }
  // JS fallback — simple pass-through with basic formatting
  return (messages || []).map(msg => ({
    id: msg.id,
    text: msg.text || '',
    formatted_text: formatMessageText(msg.text),
    is_own: msg.user && msg.user.id === currentUserId,
    is_system: msg.message_type === 'system',
    formatted_time: msg.created_at ? new Date(msg.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) : '',
    sender_name: msg.user ? msg.user.first_name || '' : '',
  }));
}

/**
 * Search messages by text content.
 * Returns array of { index, id } for matching messages.
 */
export function searchMessages(messages, query) {
  if (wasmReady && Array.isArray(messages) && messages.length > 0 && query) {
    try {
      return JSON.parse(wasmModule.search_messages(JSON.stringify(messages), query));
    } catch (err) {
      console.warn('[WASM] search_messages failed, using JS fallback:', err.message);
    }
  }
  // JS fallback
  if (!query || !query.trim()) return [];
  const q = query.toLowerCase();
  return (messages || [])
    .map((msg, i) => ({ index: i, id: msg.id, text: msg.text }))
    .filter(m => (m.text || '').toLowerCase().includes(q))
    .map(({ index, id }) => ({ index, id }));
}

/**
 * Run WASM performance benchmark.
 * Returns elapsed time in ms or null if WASM is not available.
 */
export function runBenchmark(count = 1000) {
  if (wasmReady) {
    return wasmModule.benchmark_batch_processing(count);
  }
  return null;
}
