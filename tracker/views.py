

@login_required
def health_check(request):
    """Health check endpoint for monitoring"""
    from django.db import connection
    from django.http import JsonResponse
    from redis import Redis
    import socket
    
    # Check database connection
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        db_ok = False
    
    # Check Redis connection
    redis_ok = True
    try:
        redis_client = Redis.from_url(settings.CACHES['default']['LOCATION'])
        redis_client.ping()
    except Exception:
        redis_ok = False
    
    status = db_ok and redis_ok
    
    data = {
        'status': 'ok' if status else 'error',
        'database': 'ok' if db_ok else 'error',
        'cache': 'ok' if redis_ok else 'error',
        'hostname': socket.gethostname(),
    }
    
    return JsonResponse(data, status=200 if status else 500)

@login_required
def maintenance_schedule_list(request):
    """View all maintenance schedules"""
    schedules = MaintenanceSchedule.objects.filter(
        vehicle__owner=request.user,
        is_active=True
    ).order_by('vehicle', 'name')
    
    # Find due schedules
    due_schedules = [schedule for schedule in schedules if schedule.is_due()]
    
    # Group by vehicle
    vehicles = Vehicle.objects.filter(owner=request.user)
    vehicle_schedules = {}
    
    for vehicle in vehicles:
        vehicle_schedules[vehicle] = schedules.filter(vehicle=vehicle)
    
    context = {
        'schedules': schedules,
        'due_schedules': due_schedules,
        'vehicle_schedules': vehicle_schedules,
    }
    
    return render(request, 'tracker/maintenance_schedule_list.html', context)

@login_required
def maintenance_schedule_create(request):
    """Create a new maintenance schedule"""
    if request.method == 'POST':
        form = MaintenanceScheduleForm(request.POST, user=request.user)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.created_by = request.user
            schedule.save()
            messages.success(request, 'Maintenance schedule created successfully!')
            return redirect('maintenance_schedule_list')
    else:
        vehicle_id = request.GET.get('vehicle')
        initial = {}
        if vehicle_id:
            initial['vehicle'] = vehicle_id
        form = MaintenanceScheduleForm(user=request.user, initial=initial)
    
    context = {
        'form': form,
    }
    return render(request, 'tracker/maintenance_schedule_form.html', context)

@login_required
def export_data(request, type, pk=None):
    """Export data to CSV format"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{type}_export.csv"'
    
    writer = csv.writer(response)
    
    if type == 'vehicle' and pk:
        # Export single vehicle data
        vehicle = get_object_or_404(Vehicle, pk=pk, owner=request.user)
        
        # Header row
        writer.writerow(['Event Type', 'Date', 'Miles/Hours', 'Category', 'Location', 'Cost', 'Notes'])
        
        # Data rows
        events = Event.objects.filter(vehicle=vehicle).order_by('date')
        for event in events:
            distance = event.miles if vehicle.type == 'car' else event.hours
            category = event.maintenance_category.name if event.maintenance_category else ''
            location = event.location.name if event.location else ''
            cost = event.total_cost if event.total_cost else ''
            
            writer.writerow([
                event.get_event_type_display(),
                event.date.strftime('%Y-%m-%d'),
                distance,
                category,
                location,
                cost,
                event.notes
            ])
    
    elif type == 'vehicles':
        # Export all vehicle summary
        writer.writerow(['Name', 'Make', 'Model', 'Year', 'Type', 'Total Events'])
        
        vehicles = Vehicle.objects.filter(owner=request.user)
        for vehicle in vehicles:
            event_count = Event.objects.filter(vehicle=vehicle).count()
            
            writer.writerow([
                vehicle.name,
                vehicle.make,
                vehicle.model,
                vehicle.year,
                vehicle.get_type_display(),
                event_count
            ])
    
    elif type == 'maintenance':
        # Export maintenance records
        writer.writerow(['Vehicle', 'Date', 'Category', 'Miles/Hours', 'Cost', 'Notes'])
        
        events = Event.objects.filter(
            user=request.user,
            event_type='maintenance'
        ).select_related('vehicle', 'maintenance_category').order_by('date')
        
        for event in events:
            distance = event.miles if event.vehicle.type == 'car' else event.hours
            category = event.maintenance_category.name if event.maintenance_category else ''
            
            writer.writerow([
                str(event.vehicle),
                event.date.strftime('%Y-%m-%d'),
                category,
                distance,
                event.total_cost if event.total_cost else '',
                event.notes
            ])
    
    return response

# API Views for mobile access
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import (
    VehicleSerializer, EventSerializer, MaintenanceScheduleSerializer, 
    TodoItemSerializer, LocationSerializer
)

class VehicleViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleSerializer
    
    def get_queryset(self):
        return Vehicle.objects.filter(owner=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    @action(detail=True)
    def stats(self, request, pk=None):
        vehicle = self.get_object()
        
        # Calculate statistics
        event_count = Event.objects.filter(vehicle=vehicle).count()
        maintenance_count = Event.objects.filter(vehicle=vehicle, event_type='maintenance').count()
        gas_count = Event.objects.filter(vehicle=vehicle, event_type='gas').count()
        
        # Calculate costs
        from django.db.models import Sum
        total_maintenance_cost = Event.objects.filter(
            vehicle=vehicle, event_type='maintenance'
        ).aggregate(Sum('total_cost'))['total_cost__sum'] or 0
        
        total_gas_cost = Event.objects.filter(
            vehicle=vehicle, event_type='gas'
        ).aggregate(Sum('total_cost'))['total_cost__sum'] or 0
        
        # Get active maintenance schedules
        schedules = MaintenanceSchedule.objects.filter(
            vehicle=vehicle, is_active=True
        )
        
        due_schedules = [
            MaintenanceScheduleSerializer(s).data 
            for s in schedules if s.is_due()
        ]
        
        return Response({
            'event_count': event_count,
            'maintenance_count': maintenance_count,
            'gas_count': gas_count,
            'total_maintenance_cost': total_maintenance_cost,
            'total_gas_cost': total_gas_cost,
            'due_maintenance': due_schedules,
        })

class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    
    def get_queryset(self):
        return Event.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class TodoItemViewSet(viewsets.ModelViewSet):
    serializer_class = TodoItemSerializer
    
    def get_queryset(self):
        from django.db.models import Q
        return TodoItem.objects.filter(
            Q(user=self.request.user) | Q(shared_with=self.request.user)
        ).distinct()
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        todo = self.get_object()
        
        # Only the owner can toggle completion
        if todo.user == request.user:
            todo.completed = not todo.completed
            todo.save()
        
        serializer = self.get_serializer(todo)
        return Response(serializer.data)