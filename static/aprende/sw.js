/* PWA mínima: permite “Instalar” en el celular. Sin caché offline de cursos. */
self.addEventListener('install', function (event) {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
});
