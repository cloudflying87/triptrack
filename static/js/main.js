// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    // Toggle todo completion
    const todoCheckboxes = document.querySelectorAll('.todo-checkbox');
    
    todoCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const todoId = this.dataset.todoId;
            const todoItem = document.getElementById(`todo-item-${todoId}`);
            
            // Send AJAX request to toggle status
            fetch(`/todos/${todoId}/toggle/`, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                }
            })
            .then(response => response.json())
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
    
    // MPG Chart - Added check for Chart global
    const mpgChartCanvas = document.getElementById('mpgChart');
    
    if (mpgChartCanvas && typeof Chart !== 'undefined') {
        try {
            const mpgData = JSON.parse(mpgChartCanvas.dataset.mpgData || '[]');
            
            if (mpgData.length > 0) {
                new Chart(mpgChartCanvas, {
                    type: 'line',
                    data: {
                        labels: mpgData.map(item => item.date),
                        datasets: [{
                            label: 'MPG',
                            data: mpgData.map(item => item.mpg),
                            borderColor: '#4285f4',
                            tension: 0.1,
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: {
                                beginAtZero: false
                            }
                        }
                    }
                });
            }
        } catch (error) {
            console.error('Error creating MPG chart:', error);
        }
    }
    
    // Register service worker for PWA
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/sw.js')  // Updated path to match static files location
            .then(reg => console.log('Service Worker registered', reg))
            .catch(err => console.log('Service Worker registration failed', err));
    }
});