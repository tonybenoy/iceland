/* Offline support. Much of the ring road has no signal, so the app shell and
   all trip data are precached, and map tiles are cached as you look at them. */
const VERSION = 'iceland-v1';
const SHELL = `${VERSION}-shell`;
const TILES = `${VERSION}-tiles`;
const MAX_TILES = 1200;

const PRECACHE = [
  './', './index.html', './assets/style.css', './assets/app.js',
  './manifest.webmanifest', './assets/icon-192.png', './assets/icon-512.png',
  './data/routes.json', './data/iceland_places_ranked.json',
  './data/iceland_campsites_all.json', './data/iceland_gas_stations.json',
  'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css',
  'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(SHELL);
    // don't let one bad URL fail the whole install
    await Promise.all(PRECACHE.map((u) => c.add(u).catch(() => {})));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

async function trimTiles() {
  const c = await caches.open(TILES);
  const keys = await c.keys();
  if (keys.length > MAX_TILES) {
    await Promise.all(keys.slice(0, keys.length - MAX_TILES).map((k) => c.delete(k)));
  }
}

self.addEventListener('fetch', (e) => {
  const { request } = e;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  // map tiles: cache first, then network, and keep what we've seen
  if (/tile\.openstreetmap\.org$/.test(url.hostname)) {
    e.respondWith((async () => {
      const c = await caches.open(TILES);
      const hit = await c.match(request);
      if (hit) return hit;
      try {
        const res = await fetch(request);
        if (res.ok) { await c.put(request, res.clone()); trimTiles(); }
        return res;
      } catch (_) {
        return new Response('', { status: 504 });
      }
    })());
    return;
  }

  // everything else: network first so edits show up, falling back to cache
  e.respondWith((async () => {
    const c = await caches.open(SHELL);
    try {
      const res = await fetch(request);
      if (res.ok && url.origin === self.location.origin) c.put(request, res.clone());
      return res;
    } catch (_) {
      const hit = await c.match(request) || await c.match('./index.html');
      if (hit) return hit;
      throw new Error('offline and not cached');
    }
  })());
});
