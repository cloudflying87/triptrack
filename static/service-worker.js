// service-worker.js
const CACHE_NAME = 'triptracker-v1';

// App Shell - Critical assets that make the app work offline
const APP_SHELL = [
  '/',
  '/dashboard/',
  '/static/css/bootstrap.min.css',
  '/static/css/styles.css',
  '/static/js/main.js',
  '/static/js/charts.js',
  '/static/images/icon-192x192.png',
  '/static/images/icon-512x512.png',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css',
  'https://cdn.jsdelivr.net/npm/chart.js@4.3.0/dist/chart.umd.min.js'
];

// Dynamic content - Cache strategy: network first, fall back to cache
const DYNAMIC_ROUTES = [
  '/vehicles/',
  '/events/',
  '/todos/',
  '/locations/',
  '/families/',
  '/maintenance-schedules/',
  '/reports/',
];

// Install event - Pre-cache App Shell with improved error handling
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Caching app shell');
        
        // Use individual fetch requests instead of addAll to handle individual failures
        const cachePromises = APP_SHELL.map(url => {
          return fetch(url)
            .then(response => {
              if (!response.ok) {
                throw new Error(`Failed to cache ${url}: ${response.status} ${response.statusText}`);
              }
              return cache.put(url, response);
            })
            .catch(error => {
              console.error(`Caching failed for ${url}:`, error);
              // Continue despite the error
              return Promise.resolve();
            });
        });
        
        return Promise.all(cachePromises);
      })
      .then(() => {
        console.log('App shell cached successfully');
        return self.skipWaiting(); // Activate new service worker immediately
      })
      .catch(error => {
        console.error('Service worker installation failed:', error);
        // Continue installing even if caching failed
        return self.skipWaiting();
      })
  );
});

// Activate event - Clean up old caches
self.addEventListener('activate', event => {
  const currentCaches = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return cacheNames.filter(cacheName => !currentCaches.includes(cacheName));
    }).then(cachesToDelete => {
      return Promise.all(cachesToDelete.map(cacheToDelete => {
        return caches.delete(cacheToDelete);
      }));
    }).then(() => self.clients.claim()) // Take control of all clients
  );
});

// Helper function to check if a URL matches any dynamic route pattern
function matchesDynamicRoute(url) {
  const pathname = new URL(url).pathname;
  return DYNAMIC_ROUTES.some(route => pathname.startsWith(route));
}

// Helper function to check if a request is for an API endpoint
function isApiRequest(url) {
  const pathname = new URL(url).pathname;
  return pathname.startsWith('/api/');
}

// Helper function to check if a request is for an authentication endpoint
function isAuthRequest(url) {
  const pathname = new URL(url).pathname;
  return pathname.startsWith('/accounts/');
}

// Fetch event - Custom fetch strategy based on request type
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);

  // Skip cross-origin requests
  if (url.origin !== self.location.origin) {
    return;
  }

  // Handle API requests - Network only with timeout fallback
  if (isApiRequest(request.url)) {
    event.respondWith(
      fetch(request)
        .catch(error => {
          console.error('API fetch failed:', error);
          return caches.match(request)
            .then(cachedResponse => {
              if (cachedResponse) {
                return cachedResponse;
              }
              // If no cached response, return an offline JSON response
              return new Response(
                JSON.stringify({ 
                  error: 'You are currently offline. Please try again when you have a network connection.' 
                }),
                { 
                  headers: { 'Content-Type': 'application/json' } 
                }
              );
            });
        })
    );
    return;
  }

  // Handle authentication requests - Network first, never cache
  if (isAuthRequest(request.url)) {
    event.respondWith(
      fetch(request)
        .catch(() => {
          // For auth requests that fail, redirect to login page
          return caches.match('/');
        })
    );
    return;
  }

  // Handle dynamic routes - Network first, fall back to cache, then offline page
  if (matchesDynamicRoute(request.url)) {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Cache a copy of the response
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(request, responseClone);
          });
          return response;
        })
        .catch(() => {
          return caches.match(request)
            .then(cachedResponse => {
              if (cachedResponse) {
                return cachedResponse;
              }
              // If no cached version, return the offline page
              return caches.match('/offline.html') || caches.match('/');
            });
        })
    );
    return;
  }

  // Default strategy - Cache first, fall back to network
  event.respondWith(
    caches.match(request)
      .then(cachedResponse => {
        if (cachedResponse) {
          // Return cached response and update cache in the background
          const fetchPromise = fetch(request).then(networkResponse => {
            caches.open(CACHE_NAME).then(cache => {
              cache.put(request, networkResponse.clone());
            });
          }).catch(() => {
            console.log('Background fetch failed, but we have a cached version');
          });
          
          // Return cached response immediately
          return cachedResponse;
        }

        // No cache match, go to network
        return fetch(request)
          .then(response => {
            // Cache a copy of the response
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(request, responseClone);
            });
            return response;
          })
          .catch(() => {
            // For HTML requests, return the offline page
            if (request.headers.get('Accept')?.includes('text/html')) {
              return caches.match('/offline.html') || caches.match('/');
            }
            
            // For other types, just fail
            console.error('Fetch failed and no cached version available');
            return new Response('Network error occurred', {
              status: 503,
              statusText: 'Service Unavailable'
            });
          });
      })
  );
});

// Handle message events (e.g., skipWaiting)
self.addEventListener('message', event => {
  if (event.data && event.data.action === 'skipWaiting') {
    self.skipWaiting();
  }
});

// Basic background sync
self.addEventListener('sync', event => {
  if (event.tag === 'sync-todos') {
    event.waitUntil(syncTodos());
  } else if (event.tag === 'sync-events') {
    event.waitUntil(syncEvents());
  }
});

// Sync todo items when back online (simplified implementation)
async function syncTodos() {
  console.log('Background sync for todos initiated');
  // Actual implementation would involve IndexedDB
  // This is a placeholder
}

// Sync events when back online (simplified implementation)
async function syncEvents() {
  console.log('Background sync for events initiated');
  // Actual implementation would involve IndexedDB
  // This is a placeholder
}