// ponytail: no Workbox. Network-first with a cache fallback is the whole requirement —
// the app shell keeps working offline and health data is never served stale from cache.
// Ceiling: no precache manifest, so the very first visit must be online.
const CACHE = "nexuscoach-v1";

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  // Only shell navigation and static assets are cached; API calls always hit the network.
  if (request.method !== "GET" || new URL(request.url).origin !== location.origin) return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(request, copy));
        return response;
      })
      .catch(() => caches.match(request).then((hit) => hit ?? caches.match("/")))
  );
});
