/* My Attendance Service Worker — caches only safe static assets */
const CACHE_VERSION = 'v1.0.0';
const STATIC_CACHE = `attendance-static-${CACHE_VERSION}`;

const STATIC_ASSETS = [
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/icons/logo.svg',
  '/static/icons/favicon.svg',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/manifest.webmanifest',
  '/offline'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k.startsWith('attendance-') && k !== STATIC_CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Never cache authenticated HTML, API, or form submissions
  if (
    event.request.method !== 'GET' ||
    url.pathname.startsWith('/check-') ||
    url.pathname.startsWith('/login') ||
    url.pathname.startsWith('/settings') ||
    url.pathname.startsWith('/manual') ||
    url.pathname.startsWith('/records') ||
    url.pathname.startsWith('/reports') ||
    url.pathname.startsWith('/export') ||
    url.pathname === '/' ||
    event.request.headers.get('Accept')?.includes('text/html')
  ) {
    // Network only for dynamic/auth content
    event.respondWith(
      fetch(event.request).catch(() => {
        if (event.request.headers.get('Accept')?.includes('text/html')) {
          return caches.match('/offline');
        }
        return new Response('Offline', { status: 503 });
      })
    );
    return;
  }

  // Cache-first for static assets
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (response.ok && url.pathname.startsWith('/static/')) {
          const clone = response.clone();
          caches.open(STATIC_CACHE).then((cache) => cache.put(event.request, clone));
        }
        return response;
      });
    }).catch(() => caches.match('/offline'))
  );
});
