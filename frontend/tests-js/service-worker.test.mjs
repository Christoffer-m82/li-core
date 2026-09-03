import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('../static/sw.js', import.meta.url), 'utf8');
function worker({ offline = false, ok = true, redirected = false, type = 'basic', writeFails = false } = {}) {
  const handlers = new Map();
  const writes = [];
  const deleted = [];
  const cached = { cached: true };
  const response = { ok, redirected, type, clone() { return this; } };
  const cache = {
    async match() { return cached; },
    async put(request) { if (writeFails) throw new Error('quota'); writes.push(request.url); },
    async addAll(paths) { writes.push(...paths); },
  };
  vm.runInNewContext(source, {
    URL,
    self: { location: { origin: 'https://li.test' }, addEventListener: (name, handler) => handlers.set(name, handler) },
    caches: {
      async open(name) { assert.equal(name, 'li-shell-v7'); return cache; },
      async keys() { return ['li-shell-v6', 'li-shell-v7', 'other-app']; },
      async delete(name) { deleted.push(name); },
    },
    async fetch() { if (offline) throw new Error('offline'); return response; },
  });
  return {
    writes, deleted, cached, response,
    async dispatch(name, path = '/assets/app.js', method = 'GET') {
      let result;
      const pending = [];
      handlers.get(name)({
        request: { url: new URL(path, 'https://li.test').href, method },
        respondWith(value) { result = value; },
        waitUntil(value) { pending.push(value); },
      });
      const value = await result;
      await Promise.all(pending);
      return value;
    },
  };
}

test('private, authentication, query, cross-origin and mutation requests bypass the cache', async () => {
  const app = worker();
  for (const path of ['/', '/auth/login', '/auth/callback?code=synthetic', '/api/session', '/api', '/unknown', '/assets/app.js?code=synthetic', 'https://other.test/assets/app.js']) {
    assert.equal(await app.dispatch('fetch', path), undefined);
  }
  assert.equal(await app.dispatch('fetch', '/assets/app.js', 'POST'), undefined);
  assert.deepEqual(app.writes, []);
});

test('only successful nonredirected same-origin static responses are stored', async () => {
  const app = worker();
  assert.equal(await app.dispatch('fetch'), app.response);
  assert.deepEqual(app.writes, ['https://li.test/assets/app.js']);
  for (const options of [{ ok: false }, { redirected: true }, { type: 'opaque' }]) {
    const denied = worker(options);
    assert.equal(await denied.dispatch('fetch'), denied.response);
    assert.deepEqual(denied.writes, []);
  }
});

test('offline assets use the current cache and cache-write failure preserves the network response', async () => {
  const offline = worker({ offline: true });
  assert.equal(await offline.dispatch('fetch'), offline.cached);
  const quota = worker({ writeFails: true });
  assert.equal(await quota.dispatch('fetch'), quota.response);
});

test('installation caches static assets only and activation preserves unrelated caches', async () => {
  const app = worker();
  await app.dispatch('install');
  assert.ok(app.writes.includes('/assets/privacy.css'));
  assert.ok(!app.writes.includes('/'));
  assert.ok(app.writes.every(path => path.startsWith('/assets/') || path === '/manifest.webmanifest'));
  await app.dispatch('activate');
  assert.deepEqual(app.deleted, ['li-shell-v6']);
});
