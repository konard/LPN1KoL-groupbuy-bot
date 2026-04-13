/**
 * Utility helpers - powered by Rust+WebAssembly when available,
 * with automatic JavaScript fallbacks.
 */
import {
  formatCurrency as wasmFormatCurrency,
  getInitials as wasmGetInitials,
  getAvatarColor as wasmGetAvatarColor,
  escapeHtml as wasmEscapeHtml,
  formatMessageText as wasmFormatMessageText,
  isWasmReady,
} from '../services/wasm';

/**
 * Format date to Telegram-like format
 */
export function formatTime(date) {
  const d = new Date(date);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();

  if (isToday) {
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  }

  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) {
    return 'Вчера';
  }

  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
}

/**
 * Format date for message dividers
 */
export function formatMessageDate(date) {
  const d = new Date(date);
  const now = new Date();
  const diff = now - d;

  if (diff < 86400000) return 'Сегодня';
  if (diff < 172800000) return 'Вчера';

  return d.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}

/**
 * Format currency - uses WASM when available
 */
export function formatCurrency(amount) {
  return wasmFormatCurrency(amount);
}

/**
 * Get initials from name - uses WASM when available
 */
export function getInitials(firstName, lastName = '') {
  return wasmGetInitials(firstName, lastName);
}

/**
 * Generate avatar background color based on name - uses WASM when available
 */
export function getAvatarColor(name) {
  return wasmGetAvatarColor(name);
}

/**
 * Get status display text
 */
export function getStatusText(status) {
  const statuses = {
    draft: 'Черновик',
    active: 'Активная',
    stopped: 'Остановлена',
    payment: 'Оплата',
    completed: 'Завершена',
    cancelled: 'Отменена',
  };
  return statuses[status] || status;
}

/**
 * Get role display text
 */
export function getRoleText(role) {
  const roles = {
    buyer: 'Покупатель',
    organizer: 'Организатор',
    supplier: 'Поставщик',
  };
  return roles[role] || role;
}

/**
 * Escape HTML to prevent XSS - uses WASM when available
 */
export function escapeHtml(text) {
  return wasmEscapeHtml(text);
}

/**
 * Format message text with URL detection - uses WASM when available
 */
export function formatMessageTextHelper(text) {
  return wasmFormatMessageText(text);
}

/**
 * Debounce function
 */
export function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
