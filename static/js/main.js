// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    // Toggle todo completion
    const todoCheckboxes = document.querySelectorAll('.todo-checkbox');

    todoCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const todoId = this.dataset.todoId;
            const todoItem = document.getElementById(`todo-item-${todoId}`);
            // Get CSRF token from cookie or meta tag
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            
            // Send AJAX request to toggle status
            fetch(`/todos/${todoId}/toggle/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.completed) {
                    todoItem.classList.add('completed');
                } else {
                    todoItem.classList.remove('completed');
                }
                
                // Move item in the list if needed
                const todoList = todoItem.parentElement;
                if (data.completed) {
                    todoList.appendChild(todoItem);
                } else {
                    const firstCompletedItem = document.querySelector('.todo-item.completed');
                    if (firstCompletedItem) {
                        todoList.insertBefore(todoItem, firstCompletedItem);
                    } else {
                        todoList.appendChild(todoItem);
                    }
                }
            })
            .catch(error => {
                console.error('Error toggling todo item:', error);
                
                // Handle offline case - store in IndexedDB for later sync
                if (!navigator.onLine) {
                    saveTodoForOfflineSync(todoId, !this.checked);
                    
                    // Update UI optimistically
                    if (this.checked) {
                        todoItem.classList.add('completed');
                    } else {
                        todoItem.classList.remove('completed');
                    }
                    
                    // Show offline indicator
                    showOfflineIndicator("Todo item will be updated when you're back online");
                } else {
                    // Revert checkbox state on error
                    this.checked = !this.checked;
                }
            });
        });
    });
        
    // Show/hide fields based on vehicle type
    const vehicleTypeField = document.getElementById('id_vehicle');
    
    // Only proceed if the vehicle field exists
    if (vehicleTypeField && vehicleTypeField.hasAttribute('data-toggle-fields')) {
        const milesFieldContainer = document.getElementById('id_miles');
        const hoursFieldContainer = document.getElementById('id_hours');
        
        // Function to update visible fields
        function updateVisibleFields() {
            const vehicleId = vehicleTypeField.value;
            
            if (vehicleId) {
                fetch(`/api/vehicles/${vehicleId}/`)
                    .then(response => response.json())
                    .then(data => {
                        // Find all vehicle-type-field elements
                        const typeFields = document.querySelectorAll('.vehicle-type-field');
                        
                        typeFields.forEach(field => {
                            const fieldVehicleType = field.getAttribute('data-vehicle-type');
                            const fieldContainer = field.closest('.mb-3') || field.parentElement;
                            
                            if (fieldVehicleType === 'car' && data.type === 'car') {
                                fieldContainer.style.display = 'block';
                                field.removeAttribute('disabled');
                            } else if (fieldVehicleType === 'boat' && data.type !== 'car') {
                                fieldContainer.style.display = 'block';
                                field.removeAttribute('disabled');
                            } else {
                                fieldContainer.style.display = 'none';
                                field.setAttribute('disabled', 'disabled');
                                field.value = '';  // Clear value when hidden
                            }
                        });
                    })
                    .catch(error => {
                        console.error('Error fetching vehicle type:', error);
                    });
            } else {
                // No vehicle selected, show both fields
                const typeFields = document.querySelectorAll('.vehicle-type-field');
                typeFields.forEach(field => {
                    const fieldContainer = field.closest('.mb-3') || field.parentElement;
                    fieldContainer.style.display = 'block';
                    field.removeAttribute('disabled');
                });
            }
        }
        
        vehicleTypeField.addEventListener('change', updateVisibleFields);
        
        // Initial call
        updateVisibleFields();
    }
    
    // Setup PWA install prompt
    let deferredPrompt;
    const installButton = document.getElementById('install-button');

    // Store the install prompt event for later use
    window.addEventListener('beforeinstallprompt', (e) => {
        // Prevent Chrome 67 and earlier from automatically showing the prompt
        e.preventDefault();
        // Stash the event so it can be triggered later
        deferredPrompt = e;
        
        // Show the install button if it exists
        if (installButton) {
            installButton.style.display = 'block';
            
            installButton.addEventListener('click', () => {
                // Show the install prompt
                deferredPrompt.prompt();
                
                // Wait for the user to respond to the prompt
                deferredPrompt.userChoice.then((choiceResult) => {
                    if (choiceResult.outcome === 'accepted') {
                        console.log('User accepted the A2HS prompt');
                        // Hide the button after installation
                        installButton.style.display = 'none';
                    } else {
                        console.log('User dismissed the A2HS prompt');
                    }
                    deferredPrompt = null;
                });
            });
        }
    });

    // Handle online/offline status
    setupOnlineStatusHandling();
    
    // Register service worker
    registerServiceWorker();
});

// Service Worker Registration
function registerServiceWorker() {
    // Only register service worker in production (HTTPS)
    if ('serviceWorker' in navigator && window.location.protocol === 'https:') {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/service-worker.js')
                .then(registration => {
                    console.log('Service Worker registered with scope:', registration.scope);
                    
                    // Setup update handling
                    setupServiceWorkerUpdates(registration);
                })
                .catch(error => {
                    console.error('Service Worker registration failed:', error);
                });
        });
    } else if ('serviceWorker' in navigator && window.location.protocol === 'http:') {
        console.log('Service Worker not registered - running on HTTP (development)');
    }
}

// Handle service worker updates
function setupServiceWorkerUpdates(registration) {
    // When a new service worker is waiting to be activated
    registration.addEventListener('updatefound', () => {
        const newWorker = registration.installing;
        
        newWorker.addEventListener('statechange', () => {
            // When the new service worker is installed and waiting to activate
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                console.log('New service worker is waiting to activate');
                
                // Create update notification
                showUpdateNotification();
            }
        });
    });

    // Handle controller changes (when the new service worker takes over)
    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (!refreshing) {
            refreshing = true;
            console.log('New service worker activated, reloading page');
            window.location.reload();
        }
    });
}

// Show update notification to user
function showUpdateNotification() {
    // Create notification container if it doesn't exist
    let notificationContainer = document.getElementById('app-update-notification');
    
    if (!notificationContainer) {
        notificationContainer = document.createElement('div');
        notificationContainer.id = 'app-update-notification';
        notificationContainer.className = 'update-notification';
        notificationContainer.innerHTML = `
            <div class="update-notification-content">
                <div class="update-icon">
                    <i class="bi bi-arrow-clockwise"></i>
                </div>
                <div class="update-message">
                    A new version is available!
                </div>
                <button class="btn btn-sm btn-primary update-button">
                    Update Now
                </button>
                <button class="btn btn-sm btn-outline-secondary dismiss-button">
                    Later
                </button>
            </div>
        `;
        
        document.body.appendChild(notificationContainer);
        
        // Add update button listener
        const updateButton = notificationContainer.querySelector('.update-button');
        updateButton.addEventListener('click', () => {
            // Skip waiting and activate the new service worker
            if (navigator.serviceWorker.controller) {
                navigator.serviceWorker.ready.then(registration => {
                    registration.waiting.postMessage({action: 'skipWaiting'});
                });
            }
            
            // Hide notification
            notificationContainer.style.display = 'none';
        });
        
        // Add dismiss button listener
        const dismissButton = notificationContainer.querySelector('.dismiss-button');
        dismissButton.addEventListener('click', () => {
            notificationContainer.style.display = 'none';
        });
    }
    
    // Show the notification
    notificationContainer.style.display = 'block';
}

// Update UI based on online status
function updateOnlineStatus() {
    const offlineIndicator = document.getElementById('offline-indicator');
    
    if (!offlineIndicator) return; // Exit if indicator doesn't exist yet
    
    if (navigator.onLine) {
        // We're online - make sure indicator is hidden
        offlineIndicator.classList.remove('visible');
        document.body.classList.remove('offline-mode');
        
        // Find and remove all offline warning messages
        const offlineWarnings = document.querySelectorAll('.offline-warning');
        offlineWarnings.forEach(warning => {
            warning.remove();
        });
    } else {
        // We're offline - show indicator
        offlineIndicator.classList.add('visible');
        document.body.classList.add('offline-mode');
        
        // Add offline warnings to forms
        addOfflineWarningsToForms();
    }
}

// Check network status more reliably
function checkNetworkStatus() {
    // Perform a lightweight fetch to verify actual connectivity
    return fetch('/health/', { 
        method: 'HEAD',
        cache: 'no-store',
        headers: { 'Cache-Control': 'no-cache' }
    })
    .then(() => {
        // We have connectivity
        const offlineIndicator = document.getElementById('offline-indicator');
        if (offlineIndicator) {
            offlineIndicator.classList.remove('visible');
            document.body.classList.remove('offline-mode');
        }
        return true;
    })
    .catch(() => {
        // No connectivity
        const offlineIndicator = document.getElementById('offline-indicator');
        if (offlineIndicator) {
            offlineIndicator.classList.add('visible');
            document.body.classList.add('offline-mode');
        }
        return false;
    });
}

// Handle online/offline status changes
function setupOnlineStatusHandling() {
    // Create offline indicator
    const offlineIndicator = document.createElement('div');
    offlineIndicator.id = 'offline-indicator';
    offlineIndicator.className = 'offline-indicator';
    offlineIndicator.style.opacity = '0'; // Start hidden
    offlineIndicator.innerHTML = `
        <div class="offline-indicator-content">
            <i class="bi bi-cloud-slash offline-icon"></i>
            <span class="offline-text">You are offline</span>
        </div>
    `;
    document.body.appendChild(offlineIndicator);
    
    // Initial check using standard property
    updateOnlineStatus();
    
    // Secondary check to verify actual connectivity (more reliable)
    setTimeout(() => {
        checkNetworkStatus();
    }, 1000);
    
    // Listen for changes
    window.addEventListener('online', () => {
        updateOnlineStatus();
        checkNetworkStatus();
        
        // If we're back online, attempt to sync offline data
        if ('serviceWorker' in navigator && 'SyncManager' in window) {
            navigator.serviceWorker.ready.then(registration => {
                // Register syncs for different data types
                registration.sync.register('sync-todos');
                registration.sync.register('sync-events');
            });
        } else {
            // Otherwise, do a manual sync
            syncOfflineData();
        }
    });
    
    window.addEventListener('offline', updateOnlineStatus);
    
    // Recheck periodically
    setInterval(checkNetworkStatus, 30000); // Check every 30 seconds
}

// Add offline warnings to forms when offline
function addOfflineWarningsToForms() {
    // Only add warnings to forms that don't already have them
    document.querySelectorAll('form').forEach(form => {
        if (!form.querySelector('.offline-warning')) {
            const warning = document.createElement('div');
            warning.className = 'alert alert-warning offline-warning';
            warning.innerHTML = `
                <i class="bi bi-cloud-slash me-2"></i>
                You're offline. Some actions may not work until you're back online.
            `;
            
            // Insert at the top of the form
            form.insertBefore(warning, form.firstChild);
        }
    });
}

// Show temporary offline indicator with custom message
function showOfflineIndicator(message) {
    const container = document.createElement('div');
    container.className = 'offline-toast';
    container.innerHTML = `
        <div class="offline-toast-content">
            <i class="bi bi-cloud-slash me-2"></i>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(container);
    
    // Show the toast
    setTimeout(() => {
        container.classList.add('visible');
    }, 10);
    
    // Hide after a delay
    setTimeout(() => {
        container.classList.remove('visible');
        setTimeout(() => {
            container.remove();
        }, 300);
    }, 3000);
}

// Save todo item for offline sync
async function saveTodoForOfflineSync(todoId, completed) {
    if ('indexedDB' in window) {
        try {
            const db = await openDatabase();
            await db.add('offlineTodos', {
                id: Date.now(), // Temporary ID for storage
                todoId: todoId,
                completed: completed,
                timestamp: new Date().toISOString()
            });
            console.log('Todo saved for offline sync');
        } catch (error) {
            console.error('Error saving todo for offline sync:', error);
        }
    }
}

// Save event for offline sync
async function saveEventForOfflineSync(eventData) {
    if ('indexedDB' in window) {
        try {
            const db = await openDatabase();
            await db.add('offlineEvents', {
                ...eventData,
                id: Date.now(), // Temporary ID for storage
                timestamp: new Date().toISOString()
            });
            console.log('Event saved for offline sync');
        } catch (error) {
            console.error('Error saving event for offline sync:', error);
        }
    }
}

// Manual sync of offline data
async function syncOfflineData() {
    // Get CSRF token
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    
    if (!csrfToken) {
        console.error('CSRF token not found, cannot sync');
        return;
    }
    
    try {
        const db = await openDatabase();
        
        // Sync todos
        const offlineTodos = await db.getAll('offlineTodos');
        for (const todo of offlineTodos) {
            try {
                const response = await fetch(`/todos/${todo.todoId}/toggle/`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    credentials: 'same-origin'
                });
                
                if (response.ok) {
                    await db.delete('offlineTodos', todo.id);
                    console.log('Successfully synced todo', todo.todoId);
                }
            } catch (error) {
                console.error('Failed to sync todo:', error);
            }
        }
        
        // Sync events
        const offlineEvents = await db.getAll('offlineEvents');
        for (const event of offlineEvents) {
            try {
                const response = await fetch('/api/events/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify(event)
                });
                
                if (response.ok) {
                    await db.delete('offlineEvents', event.id);
                    console.log('Successfully synced event');
                }
            } catch (error) {
                console.error('Failed to sync event:', error);
            }
        }
    } catch (error) {
        console.error('Error syncing offline data:', error);
    }
}

// IndexedDB helper
function openDatabase() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('triptracker-offline', 1);
        
        request.onupgradeneeded = event => {
            const db = event.target.result;
            
            // Create offline storage for todos
            if (!db.objectStoreNames.contains('offlineTodos')) {
                db.createObjectStore('offlineTodos', { keyPath: 'id' });
            }
            
            // Create offline storage for events
            if (!db.objectStoreNames.contains('offlineEvents')) {
                db.createObjectStore('offlineEvents', { keyPath: 'id' });
            }
        };
        
        request.onsuccess = event => {
            const db = event.target.result;
            const dbWrapper = {
                get: (storeName, key) => {
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction(storeName, 'readonly');
                        const store = transaction.objectStore(storeName);
                        const request = store.get(key);
                        
                        request.onsuccess = () => resolve(request.result);
                        request.onerror = () => reject(request.error);
                    });
                },
                getAll: (storeName) => {
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction(storeName, 'readonly');
                        const store = transaction.objectStore(storeName);
                        const request = store.getAll();
                        
                        request.onsuccess = () => resolve(request.result);
                        request.onerror = () => reject(request.error);
                    });
                },
                add: (storeName, item) => {
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction(storeName, 'readwrite');
                        const store = transaction.objectStore(storeName);
                        const request = store.add(item);
                        
                        request.onsuccess = () => resolve(request.result);
                        request.onerror = () => reject(request.error);
                    });
                },
                delete: (storeName, key) => {
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction(storeName, 'readwrite');
                        const store = transaction.objectStore(storeName);
                        const request = store.delete(key);
                        
                        request.onsuccess = () => resolve();
                        request.onerror = () => reject(request.error);
                    });
                }
            };
            
            resolve(dbWrapper);
        };
        
        request.onerror = event => {
            reject(event.target.error);
        };
    });
}