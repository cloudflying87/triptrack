from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count, Q
from .models import Family, Vehicle, Event, TodoItem, MaintenanceSchedule
from django.utils import timezone


@staff_member_required
def admin_dashboard(request):
    """Custom admin dashboard view"""
    
    # Get statistics
    total_families = Family.objects.count()
    total_vehicles = Vehicle.objects.count()
    total_events = Event.objects.count()
    active_todos = TodoItem.objects.filter(completed=False).count()
    
    # Count maintenance schedules that are due
    maintenance_due = 0
    for schedule in MaintenanceSchedule.objects.filter(is_active=True):
        if schedule.is_due():
            maintenance_due += 1
    
    # Get recent events
    recent_events = Event.objects.select_related('vehicle').order_by('-date', '-created_at')[:10]
    
    context = {
        'total_families': total_families,
        'total_vehicles': total_vehicles,
        'total_events': total_events,
        'active_todos': active_todos,
        'maintenance_due': maintenance_due,
        'recent_events': recent_events,
    }
    
    return render(request, 'admin/dashboard.html', context)