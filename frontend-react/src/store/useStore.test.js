/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../services/wasm', () => ({
  batchProcessProcurements: (items) => items,
  generatePlatformUserId: () => 'mock-id',
}));

vi.mock('../services/websocket.js', () => ({
  registerFetchController: () => () => {},
  wsManager: { connect: vi.fn(), disconnect: vi.fn(), on: vi.fn(), off: vi.fn() },
}));

describe('useStore – session persistence across page reloads (issue #342)', () => {
  let useStore;

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('initializes user from JWT in localStorage on store creation', async () => {
    const payload = { sub: 'user-42', email: 'a@b.com', role: 'buyer' };
    const fakeJwt = `header.${btoa(JSON.stringify(payload))}.signature`;
    localStorage.setItem('authToken', fakeJwt);
    localStorage.setItem('userId', 'user-42');

    vi.resetModules();
    const mod = await import('./useStore.js');
    useStore = mod.useStore;

    const state = useStore.getState();
    expect(state.user).toEqual({ id: 'user-42', email: 'a@b.com', role: 'buyer' });
    expect(state.loginModalOpen).toBe(false);
  });

  it('initializes user as null when no token in localStorage', async () => {
    localStorage.clear();
    vi.resetModules();
    const mod = await import('./useStore.js');
    useStore = mod.useStore;

    expect(useStore.getState().user).toBeNull();
  });

  it('does not clear session on transient loadUser failure (non-401)', async () => {
    const payload = { sub: 'user-42', email: 'a@b.com', role: 'buyer' };
    const fakeJwt = `header.${btoa(JSON.stringify(payload))}.signature`;
    localStorage.setItem('authToken', fakeJwt);
    localStorage.setItem('refreshToken', 'ref-tok');
    localStorage.setItem('userId', 'user-42');

    vi.resetModules();
    const mod = await import('./useStore.js');
    useStore = mod.useStore;

    const mockFetch = vi.fn(() => Promise.resolve({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ message: 'Internal Server Error' }),
      headers: new Headers(),
    }));
    vi.stubGlobal('fetch', mockFetch);

    await useStore.getState().loadUser('user-42');

    expect(localStorage.getItem('authToken')).toBe(fakeJwt);
    expect(localStorage.getItem('userId')).toBe('user-42');
    expect(useStore.getState().user).toEqual({ id: 'user-42', email: 'a@b.com', role: 'buyer' });
    expect(useStore.getState().loginModalOpen).toBe(false);
  });

  it('clears session on 401 loadUser failure (expired token)', async () => {
    const payload = { sub: 'user-42', email: 'a@b.com', role: 'buyer' };
    const fakeJwt = `header.${btoa(JSON.stringify(payload))}.signature`;
    localStorage.setItem('authToken', fakeJwt);
    localStorage.setItem('userId', 'user-42');

    vi.resetModules();
    const mod = await import('./useStore.js');
    useStore = mod.useStore;

    const mockFetch = vi.fn(() => Promise.resolve({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ message: 'Unauthorized' }),
      headers: new Headers(),
    }));
    vi.stubGlobal('fetch', mockFetch);

    await useStore.getState().loadUser('user-42');

    expect(localStorage.getItem('authToken')).toBeNull();
    expect(localStorage.getItem('userId')).toBeNull();
    expect(useStore.getState().user).toBeNull();
    expect(useStore.getState().loginModalOpen).toBe(true);
  });
});

describe('useStore – session token separation (issue #338)', () => {
  let useStore;

  beforeEach(async () => {
    localStorage.clear();
    vi.resetModules();
    const mod = await import('./useStore.js');
    useStore = mod.useStore;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('loadUser stores WS token under wsToken key, not authToken', async () => {
    const REAL_AUTH_TOKEN = 'real-api-jwt-token';
    const WS_TOKEN = 'ws-specific-jwt-token';
    const USER_ID = 'user-123';

    localStorage.setItem('authToken', REAL_AUTH_TOKEN);
    localStorage.setItem('userId', USER_ID);

    const mockFetch = vi.fn((url) => {
      if (url.includes(`/users/${USER_ID}/ws_token/`)) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ token: WS_TOKEN }),
        });
      }
      if (url.includes(`/users/${USER_ID}/`)) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ id: USER_ID, email: 'test@test.com', role: 'buyer' }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    vi.stubGlobal('fetch', mockFetch);

    await useStore.getState().loadUser(USER_ID);

    // Wait for fire-and-forget getWsToken to settle
    await new Promise((r) => setTimeout(r, 50));

    expect(localStorage.getItem('authToken')).toBe(REAL_AUTH_TOKEN);
    expect(localStorage.getItem('wsToken')).toBe(WS_TOKEN);
  });

  it('logout clears wsToken along with other auth keys', async () => {
    localStorage.setItem('authToken', 'tok');
    localStorage.setItem('refreshToken', 'ref');
    localStorage.setItem('wsToken', 'ws');
    localStorage.setItem('userId', 'u1');

    const mockFetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
    vi.stubGlobal('fetch', mockFetch);

    await useStore.getState().logout();

    expect(localStorage.getItem('authToken')).toBeNull();
    expect(localStorage.getItem('refreshToken')).toBeNull();
    expect(localStorage.getItem('wsToken')).toBeNull();
    expect(localStorage.getItem('userId')).toBeNull();
  });
});
