# tracker/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# DRF Router
router = DefaultRouter()
router.register(r'api/vehicles', views.VehicleViewSet, basename='vehicle-api')
router.register(r'api/trips', views.EventViewSet, basename='trip-api')
router.register(r'api/todos', views.TodoItemViewSet, basename='todo-api')

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    
    # System
    path('health/', views.health_check, name='health_check'),
    
    # Vehicles
    path('vehicles/', views.vehicle_list, name='vehicle_list'),
    path('vehicles/add/', views.vehicle_create, name='vehicle_create'),
    path('vehicles/<int:pk>/', views.vehicle_detail, name='vehicle_detail'),
    path('vehicles/<int:pk>/update/', views.vehicle_update, name='vehicle_update'),
    path('vehicles/<int:pk>/delete/', views.vehicle_delete, name='vehicle_delete'),
    
    # Events (now called Trips)
    path('events/', views.event_list, name='event_list'),
    path('events/maintenance/add/', views.maintenance_create, name='maintenance_create'),
    path('events/gas/add/', views.gas_create, name='gas_create'),
    path('events/outing/add/', views.outing_create, name='outing_create'),
    path('events/<int:pk>/update/', views.event_update, name='event_update'),
    path('events/<int:pk>/delete/', views.event_delete, name='event_delete'),
    
    # Locations
    path('locations/', views.location_list, name='location_list'),
    path('locations/add/', views.location_create, name='location_create'),
    
    # Todos
    path('todos/', views.todo_list, name='todo_list'),
    path('todos/add/', views.todo_create, name='todo_create'),
    path('todos/<int:pk>/toggle/', views.todo_toggle, name='todo_toggle'),
    
    # Maintenance Schedules
    path('maintenance-schedules/', views.maintenance_schedule_list, name='maintenance_schedule_list'),
    path('maintenance-schedules/add/', views.maintenance_schedule_create, name='maintenance_schedule_create'),
    
    # Reports
    path('reports/', views.reports, name='reports'),
    path('reports/vehicle/<int:pk>/', views.vehicle_report, name='vehicle_report'),
    
    # Export Data
    path('export/vehicle/<int:pk>/', views.export_data, {'type': 'vehicle'}, name='export_vehicle_data'),
    path('export/vehicles/', views.export_data, {'type': 'vehicles'}, name='export_vehicles_data'),
    path('export/maintenance/', views.export_data, {'type': 'maintenance'}, name='export_maintenance_data'),
    
    # API Routes
    path('', include(router.urls)),
    
    # Authentication
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/register/', views.register, name='register'),
]