import { expect, test, vi } from 'vitest';
import { request } from './api.js';
test('401 expiration identifies the request token so newer sessions are protected', async () => {
  const listener = vi.fn(); window.addEventListener('devsphere:auth-expired', listener);
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401, text: async () => '{"detail":"Expired"}' }));
  try { await expect(request('/api/projects', 'old-session')).rejects.toThrow('HTTP 401'); expect(listener.mock.calls[0][0].detail.token).toBe('old-session'); }
  finally { window.removeEventListener('devsphere:auth-expired', listener); vi.unstubAllGlobals(); }
});
test('204 responses and authorization headers are handled', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, status: 204, text: async () => '' }); vi.stubGlobal('fetch', fetch);
  try { await expect(request('/api/projects/p1', 'current', { method: 'DELETE' })).resolves.toEqual({}); expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer current'); }
  finally { vi.unstubAllGlobals(); }
});
