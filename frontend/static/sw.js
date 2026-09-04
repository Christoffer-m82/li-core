const CACHE = 'li-shell-v12';
// Public fictional portraits are fetched only when displayed, never during shell installation.
const PORTRAITS = ['sofia', 'marco', 'elena', 'amelia', 'freja', 'oliver', 'james', 'victor', 'nora', 'milo', 'iris', 'clara', 'ada', 'theo', 'heimdall'].map((id) => `/assets/portraits/${id}.png`);
const SHELL = [
  '/assets/app.css',
  '/assets/privacy.css',
  '/assets/appearance.css',
  '/assets/themes.js',
  '/assets/specialists.js',
  '/assets/workspace.js',
  '/assets/specialists.css',
  '/assets/voice.js',
  '/assets/app.js',
  '/assets/icon.svg',
  '/assets/icon-192.png',
  '/assets/icon-512.png',
  '/assets/icon-maskable-192.png',
  '/assets/icon-maskable-512.png',
  '/manifest.webmanifest',
];
self.addEventListener('install', (event) => event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL))));
self.addEventListener('activate', (event) => event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith('li-shell-') && key !== CACHE).map((key) => caches.delete(key))))));
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // Never retain authentication URLs, private responses, or query-string values.
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.search || (!SHELL.includes(url.pathname) && !PORTRAITS.includes(url.pathname))) return;
  event.respondWith((async () => {
    // Portrait filenames are stable; bump CACHE when replacing a selected portrait.
    if (PORTRAITS.includes(url.pathname)) {
      try {
        const cache = await caches.open(CACHE);
        const cached = await cache.match(event.request);
        if (cached) return cached;
      } catch { /* A blocked cache must not prevent a network image from loading. */ }
    }
    let response;
    try {
      response = await fetch(event.request);
    } catch (error) {
      const cache = await caches.open(CACHE);
      const cached = await cache.match(event.request);
      if (cached) return cached;
      throw error;
    }
    if (response.ok && response.type === 'basic' && !response.redirected) {
      const copy = response.clone();
      event.waitUntil(caches.open(CACHE).then((cache) => cache.put(event.request, copy)).catch(() => {}));
    }
    return response;
  })());
});
