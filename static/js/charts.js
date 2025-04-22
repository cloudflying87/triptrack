// Initialize charts when document is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Look for chart containers
    initializeCharts();
  });
  
  function initializeCharts() {
    // Vehicle events chart (pie chart)
    const eventsChartEl = document.getElementById('vehicleEventsChart');
    if (eventsChartEl) {
      const vehicleId = eventsChartEl.dataset.vehicleId;
      fetchVehicleEventsData(vehicleId, eventsChartEl);
    }
    
    // Mileage chart (line chart)
    const mileageChartEl = document.getElementById('vehicleMileageChart');
    if (mileageChartEl) {
      const vehicleId = mileageChartEl.dataset.vehicleId;
      fetchVehicleMileageData(vehicleId, mileageChartEl);
    }
    
    // MPG chart (line chart)
    const mpgChartEl = document.getElementById('vehicleMpgChart');
    if (mpgChartEl) {
      const vehicleId = mpgChartEl.dataset.vehicleId;
      fetchVehicleMpgData(vehicleId, mpgChartEl);
    }
  }
  
  // Fetch data for vehicle events chart
  function fetchVehicleEventsData(vehicleId, chartElement) {
    fetch(`/api/vehicle/${vehicleId}/events/`)
      .then(response => response.json())
      .then(data => {
        createPieChart(chartElement, data.labels, data.data);
      })
      .catch(error => console.error('Error fetching vehicle events data:', error));
  }
  
  // Fetch data for vehicle mileage chart
  function fetchVehicleMileageData(vehicleId, chartElement) {
    fetch(`/api/vehicle/${vehicleId}/mileage/`)
      .then(response => response.json())
      .then(data => {
        createLineChart(chartElement, data.labels, data.data, 'Vehicle Mileage', data.unit);
      })
      .catch(error => console.error('Error fetching vehicle mileage data:', error));
  }
  
  // Fetch data for MPG chart
  function fetchVehicleMpgData(vehicleId, chartElement) {
    fetch(`/api/vehicle/${vehicleId}/fuel-efficiency/`)
      .then(response => response.json())
      .then(data => {
        createLineChart(chartElement, data.labels, data.data, 'Fuel Efficiency', 'MPG');
      })
      .catch(error => console.error('Error fetching MPG data:', error));
  }
  
  // Create a pie chart
  function createPieChart(element, labels, data) {
    const ctx = element.getContext('2d');
    new Chart(ctx, {
      type: 'pie',
      data: {
        labels: labels.map(label => label.charAt(0).toUpperCase() + label.slice(1)),
        datasets: [{
          data: data,
          backgroundColor: [
            '#4285f4', // Primary blue
            '#34a853', // Green
            '#fbbc05', // Yellow
            '#ea4335'  // Red
          ],
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: 'bottom'
          }
        }
      }
    });
  }
  
  // Create a line chart
  function createLineChart(element, labels, data, label, unit) {
    const ctx = element.getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: label,
          data: data,
          borderColor: '#1a73e8',
          backgroundColor: 'rgba(26, 115, 232, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.3
        }]
      },
      options: {
        responsive: true,
        scales: {
          y: {
            beginAtZero: false,
            title: {
              display: true,
              text: unit
            }
          },
          x: {
            ticks: {
              maxRotation: 45,
              minRotation: 45
            }
          }
        }
      }
    });
  }