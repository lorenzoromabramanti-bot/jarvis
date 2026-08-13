// JARVIS Mail — Service Worker (offline shell + installabilité PWA)
const CACHE = 'jmail-v1';
const ASSETS = [
  './', './index.html', './style.css', './app.js',
  './manifest.webmanifest', './icon-192.png', './icon-512.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  // API : réseau d'abord (données fraîches), cache en secours
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    return;
  }
  // Shell : cache d'abord
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
