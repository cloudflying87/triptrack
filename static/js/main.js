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
    
    // Show/hide fields based on vehicle type
    const vehicleTypeField = document.getElementById('id_vehicle');
    const milesField = document.getElementById('id_miles').closest('.mb-3');
    const hoursField = document.getElementById('id_hours').closest('.mb-3');
    
    if (vehicleTypeField && milesField && hoursField) {
        function updateVisibleFields() {
            const vehicleId = vehicleTypeField.value;
            
            if (vehicleId) {
                fetch(`/api/vehicle/${vehicleId}/type/`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.type === 'car') {
                            milesField.style.display = 'block';
                            hoursField.style.display = 'none';
                        } else {
                            milesField.style.display = 'none';
                            hoursField.style.display = 'block';
                        }
                    });
            }
        }
        
        vehicleTypeField.addEventListener('change', updateVisibleFields);
        
        // Initial call
        if (vehicleTypeField.value) {
            updateVisibleFields();
        }
    }
    
    // MPG Chart
    const mpgChartCanvas = document.getElementById('mpgChart');
    
    if (mpgChartCanvas) {
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
    }
    
    // Register service worker for PWA
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then(reg => console.log('Service Worker registered', reg))
            .catch(err => console.log('Service Worker registration failed', err));
    }
});