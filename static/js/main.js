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
                // Revert checkbox state on error
                this.checked = !this.checked;
            });
        });
    });
        
    // Show/hide fields based on vehicle type - FIXED with null checks
    const vehicleTypeField = document.getElementById('id_vehicle');
    
    // Only proceed if the vehicle field exists
    if (vehicleTypeField) {
        const milesFieldContainer = document.getElementById('id_miles');
        const hoursFieldContainer = document.getElementById('id_hours');
        
        // Only proceed if we have both field containers
        if (milesFieldContainer && hoursFieldContainer) {
            const milesField = milesFieldContainer.closest('.mb-3') || milesFieldContainer.parentElement;
            const hoursField = hoursFieldContainer.closest('.mb-3') || hoursFieldContainer.parentElement;
            
            function updateVisibleFields() {
                const vehicleId = vehicleTypeField.value;
                
                if (vehicleId) {
                    fetch(`/api/vehicles/${vehicleId}/`)
                        .then(response => response.json())
                        .then(data => {
                            if (data.type === 'car') {
                                milesField.style.display = 'block';
                                hoursField.style.display = 'none';
                            } else {
                                milesField.style.display = 'none';
                                hoursField.style.display = 'block';
                            }
                        })
                        .catch(error => {
                            console.error('Error fetching vehicle type:', error);
                        });
                }
            }
            
            vehicleTypeField.addEventListener('change', updateVisibleFields);
            
            // Initial call
            if (vehicleTypeField.value) {
                updateVisibleFields();
            }
        }
    }
    
    // Enhanced Service Worker Registration
    if ('serviceWorker' in navigator) {
        // Unregister any existing service workers first
        navigator.serviceWorker.getRegistrations().then(registrations => {
            for(let registration of registrations) {
                registration.unregister().then(success => {
                    console.log('Service worker unregistered:', success);
                    
                    // Only register a new one if we want to use PWA features
                    const enablePWA = false; // Set to true when you're ready for PWA features
                    
                    if (enablePWA) {
                        // Register new service worker with proper error handling
                        navigator.serviceWorker.register('/sw.js')
                            .then(registration => {
                                console.log('Service Worker registered with scope:', registration.scope);
                                
                                // Handle updates
                                registration.addEventListener('updatefound', () => {
                                    const newWorker = registration.installing;
                                    
                                    newWorker.addEventListener('statechange', () => {
                                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                            // New service worker is waiting
                                            console.log('New service worker is waiting to activate');
                                            
                                            // Show update notification to user
                                            if (confirm('A new version is available. Reload to update?')) {
                                                window.location.reload();
                                            }
                                        }
                                    });
                                });
                            })
                            .catch(error => {
                                console.error('Service Worker registration failed:', error);
                            });
                        
                        // Handle service worker controller changes
                        let refreshing = false;
                        navigator.serviceWorker.addEventListener('controllerchange', () => {
                            if (!refreshing) {
                                refreshing = true;
                                console.log('New service worker activated, reloading page');
                                window.location.reload();
                            }
                        });
                    }
                });
            }
        });
    }
});