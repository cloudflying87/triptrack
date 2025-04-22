// Service Worker for TripTracker PWA
const APP_VERSION = 'triptracker-v3';
const STATIC_CACHE = `${APP_VERSION}-static`;
const DYNAMIC_CACHE = `${APP_VERSION}-dynamic`;
const API_CACHE = `${APP_VERSION}-api`;

// Resources to cache during installation
const STATIC_RESOURCES = [
  '/',
  '/dashboard/',
  '/static/css/bootstrap.min.css',
  '/static/css/styles.css',
  '/static/js/bootstrap.bundle.min.js',
  '/static/js/main.js',
  '/static/images/icon-192x192.png',
  '/static/images/icon-512x512.png',
  '/static/manifest.json',
  '/offline/' // You'll need to create this offline fallback page
];

// Install event - cache static resources
self.addEventListener('install', event => {
  console.log('[Service Worker] Installing...');
  
  // Skip waiting to activate immediately
  self.skipWaiting();
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        console.log('[Service Worker] Pre-caching static resources');
        return cache.addAll(STATIC_RESOURCES);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('[Service Worker] Activating...');
  
  // Claim clients to take control immediately
  event.waitUntil(clients.claim());
  
  // Clean up old caches
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (
            cacheName !== STATIC_CACHE && 
            cacheName !== DYNAMIC_CACHE && 
            cacheName !== API_CACHE
          ) {
            console.log('[Service Worker] Removing old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  
  return self.clients.claim();
});

// Helper function to determine if a request is for an API
const isApiRequest = (url) => {
  return url.pathname.startsWith('/api/');
};

// Helper function to determine if a request is for a static asset
const isStaticAsset = (url) => {
  return url.pathname.startsWith('/static/');
};

// Fetch event - handle network requests
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  
  // Don't handle non-GET requests except for navigation
  if (event.request.method !== 'GET' && event.request.mode !== 'navigate') {
    return;
  }
  
  // Strategy 1: Cache-first for static assets
  if (isStaticAsset(url)) {
    event.respondWith(
      caches.match(event.request)
        .then(response => {
          if (response) {
            return response;
          }
          
          return fetch(event.request)
            .then(networkResponse => {
              // Cache a copy of the response
              const responseToCache = networkResponse.clone();
              caches.open(STATIC_CACHE)
                .then(cache => {
                  cache.put(event.request, responseToCache);
                });
              
              return networkResponse;
            });
        })
    );
    return;
  }
  
  // Strategy 2: Network-first with cache fallback for API requests
  if (isApiRequest(url)) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // Cache a copy of the response
          const responseToCache = response.clone();
          caches.open(API_CACHE)
            .then(cache => {
              cache.put(event.request, responseToCache);
            });
          
          return response;
        })
        .catch(() => {
          return caches.match(event.request);
        })
    );
    return;
  }
  
  // Strategy 3: Network-first for navigation requests
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request, { 
        redirect: 'follow',
        credentials: 'same-origin'
      })
        .then(response => {
          // Don't cache redirects or error responses
          if (response.redirected || !response.ok) {
            return response;
          }
          
          // Cache a copy of the response
          const responseToCache = response.clone();
          caches.open(DYNAMIC_CACHE)
            .then(cache => {
              cache.put(event.request, responseToCache);
            });
          
          return response;
        })
        .catch(() => {
          // If offline, try to return cached page
          return caches.match(event.request)
            .then(response => {
              if (response) {
                return response;
              }
              // If no cached page, return offline page
              return caches.match('/offline/');
            });
        })
    );
    return;
  }
  
  // Strategy 4: Stale-while-revalidate for everything else
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Use cached response if available
        const fetchPromise = fetch(event.request)
          .then(networkResponse => {
            // Update the cache
            caches.open(DYNAMIC_CACHE)
              .then(cache => {
                cache.put(event.request, networkResponse.clone());
              });
            
            return networkResponse;
          })
          .catch(() => {
            // If network fetch fails and we have no cached response, 
            // there's nothing we can do
            console.log('[Service Worker] Fetch failed and no cache available');
          });
        
        return response || fetchPromise;
      })
  );
});

// Background sync for offline updates
self.addEventListener('sync', event => {
  console.log('[Service Worker] Background Sync', event.tag);
  
  if (event.tag === 'sync-events') {
    event.waitUntil(
      // Implement logic to send cached events to server
      // This would sync any vehicle events created while offline
      console.log('[Service Worker] Syncing events...')
      // You would need to implement this using IndexedDB
    );
  }
});

// Push notification handler
self.addEventListener('push', event => {
  console.log('[Service Worker] Push notification received:', event);
  
  let notification = {
    title: 'TripTracker',
    body: 'Something happened with your vehicle',
    icon: '/static/images/icon-192x192.png',
    badge: '/static/images/badge-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      url: '/'
    }
  };
  
  if (event.data) {
    notification = Object.assign(notification, event.data.json());
  }
  
  event.waitUntil(
    self.registration.showNotification(notification.title, notification)
  );
});

// Notification click handler
self.addEventListener('notificationclick', event => {
  event.notification.close();
  
  event.waitUntil(
    clients.matchAll({ type: 'window' })
      .then(windowClients => {
        // If a window client is already open, focus it
        for (let client of windowClients) {
          if (client.url === event.notification.data.url && 'focus' in client) {
            return client.focus();
          }
        }
        
        // Otherwise open a new window
        if (clients.openWindow) {
          return clients.openWindow(event.notification.data.url);
        }
      })
  );
});