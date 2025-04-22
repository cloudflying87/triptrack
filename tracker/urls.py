from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views


urlpatterns = [
    # Landing page (no navbar, login/register options)
    path('', views.LandingPageView.as_view(), name='landing_page'),
    
    # Dashboard (home page for logged-in users)
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Family URLs
    path('families/', views.FamilyListView.as_view(), name='family_list'),
    path('families/create/', views.FamilyCreateView.as_view(), name='family_create'),
    path('families/<int:pk>/', views.FamilyDetailView.as_view(), name='family_detail'),
    path('families/<int:pk>/update/', views.FamilyUpdateView.as_view(), name='family_update'),
    path('families/<int:pk>/delete/', views.FamilyDeleteView.as_view(), name='family_delete'),
    path('families/<int:pk>/members/add/', views.FamilyMemberAddView.as_view(), name='family_member_add'),
    path('families/<int:family_pk>/members/<int:user_pk>/remove/',
        views.FamilyMemberRemoveView.as_view(), name='family_member_remove'),
    
    # Vehicle URLs
    path('vehicles/', views.VehicleListView.as_view(), name='vehicle_list'),
    path('vehicles/create/', views.VehicleCreateView.as_view(), name='vehicle_create'),
    path('vehicles/<int:pk>/', views.VehicleDetailView.as_view(), name='vehicle_detail'),
    path('vehicles/<int:pk>/update/', views.VehicleUpdateView.as_view(), name='vehicle_update'),
    path('vehicles/<int:pk>/delete/', views.VehicleDeleteView.as_view(), name='vehicle_delete'),
    
    # Event URLs
    path('events/', views.EventListView.as_view(), name='event_list'),
    path('events/create/', views.EventCreateView.as_view(), name='event_create'),
    path('events/maintenance/create/', views.MaintenanceCreateView.as_view(), name='maintenance_create'),
    path('events/gas/create/', views.GasCreateView.as_view(), name='gas_create'),
    path('events/outing/create/', views.OutingCreateView.as_view(), name='outing_create'),
    path('events/<int:pk>/', views.EventDetailView.as_view(), name='event_detail'),
    path('events/<int:pk>/update/', views.EventUpdateView.as_view(), name='event_update'),
    path('events/<int:pk>/delete/', views.EventDeleteView.as_view(), name='event_delete'),
    
    # Todo URLs
    path('todos/', views.TodoListView.as_view(), name='todo_list'),
    path('todos/create/', views.TodoCreateView.as_view(), name='todo_create'),
    path('todos/<int:pk>/', views.TodoDetailView.as_view(), name='todo_detail'),
    path('todos/<int:pk>/update/', views.TodoUpdateView.as_view(), name='todo_update'),
    path('todos/<int:pk>/delete/', views.TodoDeleteView.as_view(), name='todo_delete'),
    path('todos/<int:pk>/toggle/', views.TodoToggleView.as_view(), name='todo_toggle'),
    
    # Location URLs
    path('locations/', views.LocationListView.as_view(), name='location_list'),
    path('locations/create/', views.LocationCreateView.as_view(), name='location_create'),
    path('locations/<int:pk>/', views.LocationDetailView.as_view(), name='location_detail'),
    path('locations/<int:pk>/update/', views.LocationUpdateView.as_view(), name='location_update'),
    path('locations/<int:pk>/delete/', views.LocationDeleteView.as_view(), name='location_delete'),
    
    # Reports
    path('reports/', views.ReportsView.as_view(), name='reports'),
    path('reports/vehicle/<int:pk>/', views.VehicleReportView.as_view(), name='vehicle_report'),
    
    # Maintenance Schedules
    path('maintenance-schedules/', views.MaintenanceScheduleListView.as_view(), name='maintenance_schedule_list'),
    path('maintenance-schedules/create/', views.MaintenanceScheduleCreateView.as_view(), name='maintenance_schedule_create'),
    path('maintenance-schedules/<int:pk>/update/', views.MaintenanceScheduleUpdateView.as_view(), name='maintenance_schedule_update'),
    path('maintenance-schedules/<int:pk>/delete/', views.MaintenanceScheduleDeleteView.as_view(), name='maintenance_schedule_delete'),
    
    # Data Export
    path('export/<str:type>/', views.ExportDataView.as_view(), name='export_data'),
    path('export/<str:type>/<int:pk>/', views.ExportDataView.as_view(), name='export_data_with_pk'),
    
    # API URLs for charts and data
    path('api/vehicle/<int:vehicle_id>/events/', views.vehicle_events_api, name='vehicle_events_api'),
    path('api/vehicle/<int:vehicle_id>/mileage/', views.vehicle_mileage_api, name='vehicle_mileage_api'),
    path('api/vehicle/<int:vehicle_id>/fuel-efficiency/', views.vehicle_fuel_efficiency_api, name='vehicle_fuel_efficiency_api'),
    
    # Health check
    path('health/', views.health_check, name='health_check'),
    
    # Authentication
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/register/', views.register, name='register'),
    path('accounts/logout/', views.CustomLogoutView.as_view(), name='logout'),
]