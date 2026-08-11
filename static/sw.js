const CACHE_NAME = 'bachitouch-v1';
const ASSETS = [
  '/static/index.html',
  '/static/app.js',
  '/static/style.css',
  '/static/icon.png',
  '/static/usb-lost.svg',
  '/static/wifi-lost.svg',
  '/static/wifi-reconnect.svg'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((resp) => resp || fetch(event.request))
  );
});
