self.addEventListener("install", function () {
  self.skipWaiting();
});
self.addEventListener("activate", function (e) {
  e.waitUntil(self.clients.claim());
});
self.addEventListener("fetch", function (event) {
  var dest = event.request.destination;
  var mode = event.request.mode;
  var path = new URL(event.request.url).pathname;
  var fresh = mode === "navigate" || dest === "document" || dest === "manifest"
    || /\/(sw\.js|version\.json|index\.html|shared\.json)$/.test(path);
  if (fresh) {
    event.respondWith(fetch(event.request, { cache: "no-store" }));
  }
});
