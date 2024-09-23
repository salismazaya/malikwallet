importScripts("/static/js/beams.js");

var staticCacheName = "django-pwa-v" + new Date().getTime();
var filesToCache = [
    '/offline/',
    '/static/css/django-pwa-app.css',
    '/static/js/alpine.js',
    '/static/js/beams.js',
    '/static/js/html5-qrcode.js',
    '/static/js/flowbite.min.js',
    '/static/js/sweetalert2.js',
    '/static/js/push-notifications-cdn.js',
    '/static/images/icons/icon-72x72.png',
    '/static/images/icons/icon-96x96.png',
    '/static/images/icons/icon-128x128.png',
    '/static/images/icons/icon-144x144.png',
    '/static/images/icons/icon-152x152.png',
    '/static/images/icons/icon-192x192.png',
    '/static/images/icons/icon-384x384.png',
    '/static/images/icons/icon-512x512.png',
    '/static/images/icons/splash-640x1136.png',
    '/static/images/icons/splash-750x1334.png',
    '/static/images/icons/splash-1242x2208.png',
    '/static/images/icons/splash-1125x2436.png',
    '/static/images/icons/splash-828x1792.png',
    '/static/images/icons/splash-1242x2688.png',
    '/static/images/icons/splash-1536x2048.png',
    '/static/images/icons/splash-1668x2224.png',
    '/static/images/icons/splash-1668x2388.png',
    '/static/images/icons/splash-2048x2732.png'
];

// Cache on install
self.addEventListener("install", async (event) => {
    this.skipWaiting();
    event.waitUntil(
        caches.open(staticCacheName)
            .then(cache => {
                return cache.addAll(filesToCache);
            })
    )
});


self.addEventListener('sync', async (event) => {
    console.log(event)
    if (event.tag === 'kase1') {
        kase1();
    }
})

// Clear cache on activate
self.addEventListener('activate', async (event) => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames
                    .filter(cacheName => (cacheName.startsWith("django-pwa-")))
                    .filter(cacheName => (cacheName !== staticCacheName))
                    .map(cacheName => caches.delete(cacheName))
            );
        })
    );
});

// Serve from Cache
self.addEventListener("fetch", event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                return response || fetch(event.request);
            })
            .catch(() => {
                return caches.match('/offline/');
            })
    )
});

self.addEventListener('notificationclick', function (event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow('/')
    );
});

// setTimeout(async () => {
//     var pusher = new Pusher('871a1d438b0bb82d702f', {
//         cluster: 'ap1'
//     });
//     console.log(pusher);
//     const response = await fetch('/pk/');
//     const pk = await response.text()

//     var channel = pusher.subscribe(`keren_${pk}`);
//     channel.bind('moneyin', async function (data) {
//         console.log(data);
//         const { name, amount } = data;
//         // document.querySelector('.ohhh').innerHTML = name;
//         self.registration.showNotification("UANG MASUK", {
//             body: `Uang masuk sebesar Rp. ${amount} dari ${name}`,
//         });
//     });
// }, 0)