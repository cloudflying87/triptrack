# views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Avg, F, Q
from datetime import datetime, timedelta
from django.http import JsonResponse

from .models import Vehicle, Event, Location, TodoItem, MaintenanceCategory
from .forms import (VehicleForm, MaintenanceEventForm, GasEventForm, 
                  OutingEventForm, TodoItemForm, LocationForm,UserRegisterForm)
from django.contrib.auth.models import User

# API Views for mobile access
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import (
    VehicleSerializer, EventSerializer, MaintenanceScheduleSerializer, 
    TodoItemSerializer, LocationSerializer
)

@login_required
def dashboard(request):
    vehicles = Vehicle.objects.filter(owner=request.user)
    
    # Recent events
    recent_events = Event.objects.filter(
        user=request.user
    ).order_by('-date')[:5]
    
    # Todos
    todos = TodoItem.objects.filter(
        Q(user=request.user) | Q(shared_with=request.user)
    ).distinct().order_by('completed', '-created_at')[:5]
    
    context = {
        'vehicles': vehicles,
        'recent_events': recent_events,
        'todos': todos,
    }
    return render(request, 'tracker/dashboard.html', context)

# Vehicle views
@login_required
def vehicle_list(request):
    vehicles = Vehicle.objects.filter(owner=request.user)
    return render(request, 'tracker/vehicle_list.html', {'vehicles': vehicles})

@login_required
def vehicle_detail(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk, owner=request.user)
    events = Event.objects.filter(vehicle=vehicle).order_by('-date')
    todos = TodoItem.objects.filter(vehicle=vehicle).order_by('completed', '-created_at')
    
    # Calculate stats
    maintenance_count = events.filter(event_type='maintenance').count()
    gas_events = events.filter(event_type='gas')
    total_spent_on_gas = gas_events.aggregate(Sum('total_cost'))['total_cost__sum'] or 0
    
    # MPG calculation
    mpg_data = []
    for event in gas_events.order_by('date'):
        if event.get_mpg():
            mpg_data.append({
                'date': event.date.strftime('%Y-%m-%d'),
                'mpg': event.get_mpg(),
            })
    
    context = {
        'vehicle': vehicle,
        'events': events,
        'todos': todos,
        'maintenance_count': maintenance_count,
        'total_spent_on_gas': total_spent_on_gas,
        'mpg_data': mpg_data,
    }
    return render(request, 'tracker/vehicle_detail.html', context)

@login_required
def vehicle_create(request):
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.owner = request.user
            vehicle.save()
            messages.success(request, 'Vehicle added successfully!')
            return redirect('vehicle_detail', pk=vehicle.pk)
    else:
        form = VehicleForm()
    
    return render(request, 'tracker/vehicle_form.html', {'form': form})

@login_required
def vehicle_update(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk, owner=request.user)
    
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES, instance=vehicle)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vehicle updated successfully!')
            return redirect('vehicle_detail', pk=vehicle.pk)
    else:
        form = VehicleForm(instance=vehicle)
    
    return render(request, 'tracker/vehicle_form.html', {'form': form, 'vehicle': vehicle})

@login_required
def vehicle_delete(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk, owner=request.user)
    
    if request.method == 'POST':
        vehicle.delete()
        messages.success(request, 'Vehicle deleted successfully!')
        return redirect('vehicle_list')
    
    return render(request, 'tracker/vehicle_confirm_delete.html', {'vehicle': vehicle})

# Event views
@login_required
def event_list(request):
    events = Event.objects.filter(user=request.user).order_by('-date')
    return render(request, 'tracker/event_list.html', {'events': events})

@login_required
def maintenance_create(request):
    if request.method == 'POST':
        form = MaintenanceEventForm(request.POST, user=request.user)
        if form.is_valid():
            event = form.save(commit=False)
            event.user = request.user
            event.event_type = 'maintenance'
            event.save()
            messages.success(request, 'Maintenance record added successfully!')
            return redirect('vehicle_detail', pk=event.vehicle.pk)
    else:
        vehicle_id = request.GET.get('vehicle')
        initial = {}
        if vehicle_id:
            initial['vehicle'] = vehicle_id
        form = MaintenanceEventForm(user=request.user, initial=initial)
    
    context = {
        'form': form,
        'event_type': 'maintenance',
    }
    return render(request, 'tracker/event_form.html', context)

@login_required
def gas_create(request):
    if request.method == 'POST':
        form = GasEventForm(request.POST, user=request.user)
        if form.is_valid():
            event = form.save(commit=False)
            event.user = request.user
            event.event_type = 'gas'
            event.save()
            messages.success(request, 'Gas fill-up record added successfully!')
            return redirect('vehicle_detail', pk=event.vehicle.pk)
    else:
        vehicle_id = request.GET.get('vehicle')
        initial = {}
        if vehicle_id:
            initial['vehicle'] = vehicle_id
        form = GasEventForm(user=request.user, initial=initial)
    
    context = {
        'form': form,
        'event_type': 'gas',
    }
    return render(request, 'tracker/event_form.html', context)

@login_required
def outing_create(request):
    if request.method == 'POST':
        form = OutingEventForm(request.POST, user=request.user)
        if form.is_valid():
            event = form.save(commit=False)
            event.user = request.user
            event.event_type = 'outing'
            event.save()
            messages.success(request, 'Outing record added successfully!')
            return redirect('vehicle_detail', pk=event.vehicle.pk)
    else:
        vehicle_id = request.GET.get('vehicle')
        initial = {}
        if vehicle_id:
            initial['vehicle'] = vehicle_id
        form = OutingEventForm(user=request.user, initial=initial)
    
    context = {
        'form': form,
        'event_type': 'outing',
    }
    return render(request, 'tracker/event_form.html', context)

@login_required
def event_update(request, pk):
    event = get_object_or_404(Event, pk=pk, user=request.user)
    
    if request.method == 'POST':
        if event.event_type == 'maintenance':
            form = MaintenanceEventForm(request.POST, instance=event, user=request.user)
        elif event.event_type == 'gas':
            form = GasEventForm(request.POST, instance=event, user=request.user)
        else:  # outing
            form = OutingEventForm(request.POST, instance=event, user=request.user)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'{event.event_type.title()} record updated successfully!')
            return redirect('vehicle_detail', pk=event.vehicle.pk)
    else:
        if event.event_type == 'maintenance':
            form = MaintenanceEventForm(instance=event, user=request.user)
        elif event.event_type == 'gas':
            form = GasEventForm(instance=event, user=request.user)
        else:  # outing
            form = OutingEventForm(instance=event, user=request.user)
    
    context = {
        'form': form,
        'event': event,
        'event_type': event.event_type,
    }
    return render(request, 'tracker/event_form.html', context)

@login_required
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk, user=request.user)
    vehicle_pk = event.vehicle.pk
    
    if request.method == 'POST':
        event.delete()
        messages.success(request, f'{event.event_type.title()} record deleted successfully!')
        return redirect('vehicle_detail', pk=vehicle_pk)
    
    return render(request, 'tracker/event_confirm_delete.html', {'event': event})

# Location views
@login_required
def location_list(request):
    locations = Location.objects.filter(created_by=request.user)
    return render(request, 'tracker/location_list.html', {'locations': locations})

@login_required
def location_create(request):
    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            location = form.save(commit=False)
            location.created_by = request.user
            location.save()
            messages.success(request, 'Location added successfully!')
            return redirect('location_list')
    else:
        form = LocationForm()
    
    return render(request, 'tracker/location_form.html', {'form': form})

# Todo views
@login_required
def todo_list(request):
    todos = TodoItem.objects.filter(
        Q(user=request.user) | Q(shared_with=request.user)
    ).distinct().order_by('completed', '-created_at')
    return render(request, 'tracker/todo_list.html', {'todos': todos})

@login_required
def todo_create(request):
    if request.method == 'POST':
        form = TodoItemForm(request.POST, user=request.user)
        if form.is_valid():
            todo = form.save(commit=False)
            todo.user = request.user
            todo.save()
            
            # Save the many-to-many relationships
            form.save_m2m()
            
            messages.success(request, 'Todo item added successfully!')
            return redirect('todo_list')
    else:
        form = TodoItemForm(user=request.user)
    
    return render(request, 'tracker/todo_form.html', {'form': form})

@login_required
def todo_toggle(request, pk):
    todo = get_object_or_404(
        Q(user=request.user) | Q(shared_with=request.user),
        TodoItem, 
        pk=pk,
        
    )
    
    # Only the owner can toggle completion
    if todo.user == request.user:
        todo.completed = not todo.completed
        todo.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'completed': todo.completed})
    
    return redirect('todo_list')

# Reports
@login_required
def reports(request):
    vehicles = Vehicle.objects.filter(owner=request.user)
    
    context = {
        'vehicles': vehicles,
    }
    return render(request, 'tracker/reports.html', context)

@login_required
def vehicle_report(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk, owner=request.user)
    
    # Date range filtering
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    events = Event.objects.filter(vehicle=vehicle)
    
    if start_date:
        events = events.filter(date__gte=start_date)
    
    if end_date:
        events = events.filter(date__lte=end_date)
    
    # Group events by type
    maintenance_events = events.filter(event_type='maintenance')
    gas_events = events.filter(event_type='gas')
    outing_events = events.filter(event_type='outing')
    
    # Calculate statistics
    total_maintenance_cost = maintenance_events.aggregate(Sum('total_cost'))['total_cost__sum'] or 0
    total_gas_cost = gas_events.aggregate(Sum('total_cost'))['total_cost__sum'] or 0
    
    # Calculate MPG
    mpg_data = []
    for event in gas_events.order_by('date'):
        if event.get_mpg():
            mpg_data.append({
                'date': event.date.strftime('%Y-%m-%d'),
                'mpg': event.get_mpg(),
            })
    
    # Calculate average MPG
    if mpg_data:
        avg_mpg = sum(item['mpg'] for item in mpg_data) / len(mpg_data)
    else:
        avg_mpg = 0
    
    context = {
        'vehicle': vehicle,
        'maintenance_events': maintenance_events,
        'gas_events': gas_events,
        'outing_events': outing_events,
        'total_maintenance_cost': total_maintenance_cost,
        'total_gas_cost': total_gas_cost,
        'avg_mpg': avg_mpg,
        'mpg_data': mpg_data,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'tracker/vehicle_report.html', context)

# Add these to the existing views.py file

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
    """API endpoint for events"""
    serializer_class = EventSerializer
    
    def get_queryset(self):
        """Return events filtered by the current user"""
        return Event.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Save the event with the current user"""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent events"""
        recent_events = self.get_queryset().order_by('-date')[:5]
        serializer = self.get_serializer(recent_events, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get events filtered by type"""
        event_type = request.query_params.get('type')
        if event_type:
            events = self.get_queryset().filter(event_type=event_type)
            serializer = self.get_serializer(events, many=True)
            return Response(serializer.data)
        return Response({'error': 'Type parameter is required'}, status=400)
    
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
    

def register(request):
    """View for user registration"""
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'registration/register.html', {'form': form})


from django.template.loader import get_template
from django.http import HttpResponse
def debug_templates(request):
    """Debug view to check template loading"""
    try:
        template = get_template('registration/login.html')
        return HttpResponse(f"Template found at: {template.origin.name}")
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}")