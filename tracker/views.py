from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LogoutView
from django.contrib.auth.models import User
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic.edit import FormView
from django.contrib import messages
from django.db.models import Sum, Count, Avg, F, Q
from datetime import datetime, timedelta
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.conf import settings
import os
from .models import Vehicle, Event, Location, TodoItem, MaintenanceCategory, MaintenanceSchedule, Family
from .forms import (VehicleForm, MaintenanceEventForm, GasEventForm, 
                  OutingEventForm, TodoItemForm, LocationForm, UserRegisterForm,
                  FamilyForm, FamilyMemberForm,MaintenanceScheduleForm)

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'tracker/dashboard.html'
    login_url = 'login'  # Redirect to login page if not authenticated
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get all families the user belongs to
        user_families = user.families.all()
        
        # Get all vehicles in these families
        vehicles = Vehicle.objects.filter(family__in=user_families)
        
        # Get all locations in these families
        locations = Location.objects.filter(family__in=user_families)
        
        # Get counts for dashboard
        context['family_count'] = user_families.count()
        context['vehicle_count'] = vehicles.count()
        context['location_count'] = locations.count()  # Added location count
        
        # Get recent events
        context['recent_events'] = Event.objects.filter(
            vehicle__in=vehicles
        ).order_by('-date')[:5]
        
        # Get upcoming to-do items
        context['todo_items'] = TodoItem.objects.filter(
            Q(vehicle__in=vehicles) | Q(shared_with=user),
            completed=False
        ).order_by('due_date')[:5]
        
        # Get maintenance due
        maintenance_due = []
        for vehicle in vehicles:
            for schedule in vehicle.maintenance_schedules.filter(is_active=True):
                if schedule.is_due():
                    maintenance_due.append({
                        'vehicle': vehicle,
                        'schedule': schedule,
                    })
        
        context['maintenance_due'] = maintenance_due[:5]
        
        # Get statistics for the last 30 days
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        
        # Total maintenance cost in last 30 days
        maintenance_cost = Event.objects.filter(
            vehicle__in=vehicles,
            event_type='maintenance',
            date__gte=thirty_days_ago
        ).aggregate(total=Sum('total_cost'))['total'] or 0
        
        # Total gas cost in last 30 days
        gas_cost = Event.objects.filter(
            vehicle__in=vehicles,
            event_type='gas',
            date__gte=thirty_days_ago
        ).aggregate(total=Sum('total_cost'))['total'] or 0
        
        context['maintenance_cost'] = maintenance_cost
        context['gas_cost'] = gas_cost
        context['total_cost'] = maintenance_cost + gas_cost
        
        # Get events by type for pie chart
        events_by_type = Event.objects.filter(
            vehicle__in=vehicles
        ).values('event_type').annotate(count=Count('id')).order_by('-count')
        
        context['events_by_type'] = events_by_type
        
        # Get families with their vehicle count and location count
        families_with_counts = []
        for family in user_families:
            families_with_counts.append({
                'family': family,
                'vehicle_count': family.vehicles.count(),
                'location_count': family.locations.count(),  # Added location count
                'member_count': family.members.count(),
            })
            
        context['families'] = families_with_counts
        return context
    
class FamilyMemberRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        # For views with pk in kwargs (for Family objects)
        if 'pk' in self.kwargs:
            obj = self.get_object()
            if hasattr(obj, 'family'):
                # For Vehicle objects
                return self.request.user.families.filter(id=obj.family.id).exists()
            elif isinstance(obj, Family):
                # For Family objects
                return self.request.user.families.filter(id=obj.id).exists()
            
        # For views with family_id in kwargs
        if 'family_id' in self.kwargs:
            family_id = self.kwargs.get('family_id')
            return self.request.user.families.filter(id=family_id).exists()
            
        return False

# Family Views
class FamilyListView(LoginRequiredMixin, ListView):
    model = Family
    context_object_name = 'families'
    template_name = 'tracker/family_list.html'
    
    def get_queryset(self):
        return self.request.user.families.all()

class FamilyDetailView(LoginRequiredMixin, FamilyMemberRequiredMixin, DetailView):
    model = Family
    context_object_name = 'family'
    template_name = 'tracker/family_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        family = self.get_object()
        context['vehicles'] = family.vehicles.all()
        context['locations'] = family.locations.all()  # Added locations
        context['members'] = family.members.all()
        return context

class FamilyCreateView(LoginRequiredMixin, CreateView):
    model = Family
    form_class = FamilyForm
    template_name = 'tracker/family_form.html'
    success_url = reverse_lazy('family_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        # Add creator as a member
        self.object.members.add(self.request.user)
        messages.success(self.request, f"Family '{self.object.name}' created successfully.")
        return response


class FamilyUpdateView(LoginRequiredMixin, FamilyMemberRequiredMixin, UpdateView):
    model = Family
    form_class = FamilyForm
    template_name = 'tracker/family_form.html'
    
    def get_success_url(self):
        return reverse_lazy('family_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Family '{self.object.name}' updated successfully.")
        return response


class FamilyDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Family
    template_name = 'tracker/family_confirm_delete.html'
    success_url = reverse_lazy('family_list')
    
    def test_func(self):
        family = self.get_object()
        return self.request.user == family.created_by
    
    def delete(self, request, *args, **kwargs):
        family = self.get_object()
        messages.success(request, f"Family '{family.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)


class FamilyMemberAddView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = FamilyMemberForm
    template_name = 'tracker/family_member_form.html'
    
    def test_func(self):
        family = get_object_or_404(Family, pk=self.kwargs.get('pk'))
        print(f"Family ID from kwargs: {self.kwargs.get('pk')}")  # Debug print
        return self.request.user == family.created_by
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        family_pk = self.kwargs.get('pk')
        family = get_object_or_404(Family, pk=family_pk)
        context['family'] = family
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        print(f"Family PK from kwargs: {self.kwargs.get('pk')}")  # Debug print
        family = get_object_or_404(Family, pk=self.kwargs.get('pk'))
        print(f"Retrieved family: {family} with ID: {family.pk}")  # Debug print
        kwargs['family'] = family
        return kwargs
    
    def form_valid(self, form):
        print(f"Form data: {form.cleaned_data}")  # Debug print
        family_pk = self.kwargs.get('pk')
        print(f"Family PK from kwargs: {family_pk}")  # Debug print
        
        family = get_object_or_404(Family, pk=family_pk)
        print(f"Retrieved family: {family} with ID: {family.pk}")
        family = get_object_or_404(Family, pk=self.kwargs.get('pk'))
        email = form.cleaned_data['email']
        
        try:
            user = User.objects.get(email=email)
            if user in family.members.all():
                messages.warning(self.request, f"{user.username} is already a member of this family.")
            else:
                family.members.add(user)
                messages.success(self.request, f"{user.username} added to the family.")
        except User.DoesNotExist:
            messages.error(self.request, f"No user found with email {email}.")
        
        return redirect('family_detail', pk=family.pk)


class FamilyMemberRemoveView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    template_name = 'tracker/family_member_confirm_remove.html'
    
    def test_func(self):
        family = get_object_or_404(Family, pk=self.kwargs.get('family_pk'))
        return self.request.user == family.created_by
    
    def get_object(self):
        family = get_object_or_404(Family, pk=self.kwargs.get('family_pk'))
        user = get_object_or_404(User, pk=self.kwargs.get('user_pk'))
        
        # Check if user is family creator - can't remove creator
        if user == family.created_by:
            messages.error(self.request, "Cannot remove the family creator.")
            return None
            
        return {'family': family, 'user': user}
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object:
            context['family'] = self.object['family']
            context['member'] = self.object['user']
        return context
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object:
            return redirect('family_detail', pk=self.kwargs.get('family_pk'))
            
        family = self.object['family']
        user = self.object['user']
        
        family.members.remove(user)
        messages.success(request, f"{user.username} has been removed from the family.")
        
        return redirect('family_detail', pk=family.pk)
    
    def get_success_url(self):
        return reverse_lazy('family_detail', kwargs={'pk': self.kwargs.get('family_pk')})

class VehicleListView(LoginRequiredMixin, ListView):
    model = Vehicle
    context_object_name = 'vehicles'
    template_name = 'tracker/vehicle_list.html'
    
    def get_queryset(self):
        # Get vehicles from all families the user belongs to
        user_families = self.request.user.families.all()
        return Vehicle.objects.filter(family__in=user_families)


class VehicleDetailView(LoginRequiredMixin, FamilyMemberRequiredMixin, DetailView):
    model = Vehicle
    context_object_name = 'vehicle'
    template_name = 'tracker/vehicle_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vehicle = self.get_object()
        context['events'] = vehicle.events.order_by('-date')[:5]
        context['todo_items'] = vehicle.todo_items.filter(completed=False)
        return context

class VehicleCreateView(LoginRequiredMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'tracker/vehicle_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Vehicle '{self.object.name}' created successfully.")
        return response
    
    def get_success_url(self):
        # Redirect to the vehicle list to avoid permission issues
        return reverse_lazy('vehicle_list')

class VehicleUpdateView(LoginRequiredMixin, FamilyMemberRequiredMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'tracker/vehicle_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Vehicle '{self.object.name}' updated successfully.")
        return response
    
    def get_success_url(self):
        return reverse_lazy('vehicle_detail', kwargs={'pk': self.object.pk})

class VehicleDeleteView(LoginRequiredMixin, FamilyMemberRequiredMixin, DeleteView):
    model = Vehicle
    template_name = 'tracker/vehicle_confirm_delete.html'
    success_url = reverse_lazy('vehicle_list')
    
    def delete(self, request, *args, **kwargs):
        vehicle = self.get_object()
        messages.success(request, f"Vehicle '{vehicle.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)
    
class EventListView(LoginRequiredMixin, ListView):
    model = Event
    context_object_name = 'events'
    template_name = 'tracker/event_list.html'
    
    def get_queryset(self):
        # Get events from all vehicles in families the user belongs to
        user_families = self.request.user.families.all()
        vehicles = Vehicle.objects.filter(family__in=user_families)
        return Event.objects.filter(vehicle__in=vehicles).order_by('-date')

class EventDetailView(LoginRequiredMixin, DetailView):
    model = Event
    context_object_name = 'event'
    template_name = 'tracker/event_detail.html'
    
    def test_func(self):
        event = self.get_object()
        # Check if user is in the family that owns the vehicle
        return self.request.user.families.filter(id=event.vehicle.family.id).exists()

class EventCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'tracker/event_type_select.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['vehicle_id'] = self.request.GET.get('vehicle')
        return context

class MaintenanceCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = MaintenanceEventForm
    template_name = 'tracker/event_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        vehicle_id = self.request.GET.get('vehicle')
        if vehicle_id:
            initial['vehicle'] = vehicle_id
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event_type'] = 'maintenance'
        return context
    
    def form_valid(self, form):
        event = form.save(commit=False)
        event.created_by = self.request.user
        event.event_type = 'maintenance'
        event.save()
        messages.success(self.request, 'Maintenance record added successfully!')
        return redirect('vehicle_detail', pk=event.vehicle.pk)

class GasCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = GasEventForm
    template_name = 'tracker/event_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        vehicle_id = self.request.GET.get('vehicle')
        
        if not vehicle_id:
            # Try to find most recently used vehicle
            try:
                last_event = Event.objects.filter(
                    user=self.request.user
                ).order_by('-date', '-created_at').first()
                
                if last_event and last_event.vehicle:
                    initial['vehicle'] = last_event.vehicle.id
            except Exception:
                pass
        else:
            initial['vehicle'] = vehicle_id
            
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event_type'] = 'gas'
        return context
    
    def form_valid(self, form):
        event = form.save(commit=False)
        event.created_by = self.request.user
        event.event_type = 'gas'
        
        event.save()
        messages.success(self.request, 'Gas fill-up record added successfully!')
        return redirect('event_list')

class OutingCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = OutingEventForm
    template_name = 'tracker/event_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        vehicle_id = self.request.GET.get('vehicle')
        if vehicle_id:
            initial['vehicle'] = vehicle_id
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event_type'] = 'outing'
        return context
    
    def form_valid(self, form):
        event = form.save(commit=False)
        event.created_by = self.request.user
        event.event_type = 'outing'
        event.save()
        messages.success(self.request, 'Outing record added successfully!')
        return redirect('event_list')

class EventUpdateView(LoginRequiredMixin, UpdateView):
    model = Event
    template_name = 'tracker/event_form.html'
    
    def get_form_class(self):
        event = self.get_object()
        if event.event_type == 'maintenance':
            return MaintenanceEventForm
        elif event.event_type == 'gas':
            return GasEventForm
        else:  # outing
            return OutingEventForm
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.get_object()
        context['event_type'] = event.event_type
        context['event'] = event
        return context
    
    def form_valid(self, form):
        event = form.save()
        messages.success(self.request, f'{event.event_type.title()} record updated successfully!')
        return redirect('vehicle_detail', pk=event.vehicle.pk)
    
    def test_func(self):
        event = self.get_object()
        # Check if user is in the family that owns the vehicle
        return self.request.user.families.filter(id=event.vehicle.family.id).exists()

class EventDeleteView(LoginRequiredMixin, DeleteView):
    model = Event
    template_name = 'tracker/event_confirm_delete.html'
    
    def get_success_url(self):
        return reverse_lazy('vehicle_detail', kwargs={'pk': self.object.vehicle.pk})
    
    def delete(self, request, *args, **kwargs):
        event = self.get_object()
        messages.success(request, f'{event.event_type.title()} record deleted successfully!')
        return super().delete(request, *args, **kwargs)
    
    def test_func(self):
        event = self.get_object()
        # Check if user is in the family that owns the vehicle
        return self.request.user.families.filter(id=event.vehicle.family.id).exists()

class TodoPermissionMixin:
    """Mixin to handle consistent permissions for TodoItem views"""
    
    def get_queryset(self):
        """Return todos the user has access to"""
        return TodoItem.objects.filter(
            Q(created_by=self.request.user) | 
            Q(shared_with=self.request.user) |
            Q(vehicle__family__members=self.request.user)
        ).distinct()
    
    def has_permission(self, todo_item):
        """Check if user has permission for a specific todo item"""
        # Get the vehicle's family (if the todo is associated with a vehicle)
        vehicle_family = todo_item.vehicle.family if todo_item.vehicle else None
        
        # Check the permission cases
        is_family_member = vehicle_family and self.request.user.families.filter(id=vehicle_family.id).exists()
        return (todo_item.created_by == self.request.user or 
                self.request.user in todo_item.shared_with.all() or
                is_family_member)
    
    def has_change_permission(self, todo_item):
        """Check if user can modify a todo item (toggle, update, delete)"""
        # For editing, we'll apply the same rule as for viewing
        # Any family member, creator, or shared user can modify
        return self.has_permission(todo_item)

class TodoCreateView(LoginRequiredMixin, CreateView):
    model = TodoItem
    form_class = TodoItemForm
    template_name = 'tracker/todo_form.html'
    success_url = reverse_lazy('todo_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Todo item added successfully!')
        return super().form_valid(form)
        
class TodoListView(LoginRequiredMixin, TodoPermissionMixin, ListView):
    model = TodoItem
    context_object_name = 'todos'
    template_name = 'tracker/todo_list.html'
    
    def get_queryset(self):
        # Use the mixin's get_queryset and add ordering
        return super().get_queryset().order_by('completed', '-created_at')

class TodoDetailView(LoginRequiredMixin, TodoPermissionMixin, DetailView):
    model = TodoItem
    context_object_name = 'todo'
    template_name = 'tracker/todo_detail.html'
    
    # No need to override get_queryset - it's in the mixin

class TodoUpdateView(LoginRequiredMixin, TodoPermissionMixin, UpdateView):
    model = TodoItem
    form_class = TodoItemForm
    template_name = 'tracker/todo_form.html'
    success_url = reverse_lazy('todo_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_queryset(self):
        # Only allow those with change permission to update
        base_queryset = super().get_queryset()
        # Filter further if needed - for example, if you still want to 
        # restrict updates to only the creator, uncomment the next line
        # return base_queryset.filter(created_by=self.request.user)
        return base_queryset
    
    def form_valid(self, form):
        messages.success(self.request, 'Todo item updated successfully!')
        return super().form_valid(form)

class TodoDeleteView(LoginRequiredMixin, TodoPermissionMixin, DeleteView):
    model = TodoItem
    template_name = 'tracker/todo_confirm_delete.html'
    success_url = reverse_lazy('todo_list')
    
    def get_queryset(self):
        # Only allow those with change permission to delete
        base_queryset = super().get_queryset()
        # Filter further if needed - for example, if you want to
        # restrict deletions to only the creator, uncomment the next line
        # return base_queryset.filter(created_by=self.request.user)
        return base_queryset
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Todo item deleted successfully!')
        return super().delete(request, *args, **kwargs)

class TodoToggleView(LoginRequiredMixin, TodoPermissionMixin, View):
    def post(self, request, pk):
        try:
            todo_item = get_object_or_404(self.get_queryset(), pk=pk)
            
            if self.has_change_permission(todo_item):
                todo_item.completed = not todo_item.completed
                todo_item.save()
                messages.success(request, "Todo item status updated successfully.")
            else:
                messages.error(request, "You don't have permission to update this todo item.")
                
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'completed': todo_item.completed,
                    'message': "Status updated successfully."
                })
                
        except TodoItem.DoesNotExist:
            messages.error(request, "This todo item doesn't exist or has been deleted.")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': "This todo item doesn't exist or has been deleted."
                }, status=404)
                
        return redirect('todo_list')

class LocationListView(LoginRequiredMixin, ListView):
    model = Location
    context_object_name = 'locations'
    template_name = 'tracker/location_list.html'
    
    def get_queryset(self):
        # Get all locations in families the user belongs to
        user_families = self.request.user.families.all()
        return Location.objects.filter(family__in=user_families)

class LocationDetailView(LoginRequiredMixin, DetailView):
    model = Location
    context_object_name = 'location'
    template_name = 'tracker/location_detail.html'
    
    def get_queryset(self):
        # Get all locations in families the user belongs to
        user_families = self.request.user.families.all()
        return Location.objects.filter(family__in=user_families)

class LocationCreateView(LoginRequiredMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'tracker/location_form.html'
    success_url = reverse_lazy('location_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Limit family choices to only families the user belongs to
        form.fields['family'].queryset = self.request.user.families.all()
        return form
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'Location added successfully!')
        return response

class LocationUpdateView(LoginRequiredMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'tracker/location_form.html'
    success_url = reverse_lazy('location_list')
    
    def get_queryset(self):
        # Get all locations in families the user belongs to
        user_families = self.request.user.families.all()
        return Location.objects.filter(family__in=user_families)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Limit family choices to only families the user belongs to
        form.fields['family'].queryset = self.request.user.families.all()
        return form
    
    def form_valid(self, form):
        messages.success(self.request, 'Location updated successfully!')
        return super().form_valid(form)

class LocationDeleteView(LoginRequiredMixin, DeleteView):
    model = Location
    template_name = 'tracker/location_confirm_delete.html'
    success_url = reverse_lazy('location_list')
    
    def get_queryset(self):
        # Get all locations in families the user belongs to
        user_families = self.request.user.families.all()
        return Location.objects.filter(family__in=user_families)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Location deleted successfully!')
        return super().delete(request, *args, **kwargs)
    model = Location
    template_name = 'tracker/location_confirm_delete.html'
    success_url = reverse_lazy('location_list')
    
    def get_queryset(self):
        return Location.objects.filter(created_by=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Location deleted successfully!')
        return super().delete(request, *args, **kwargs)

class ReportsView(LoginRequiredMixin, TemplateView):
    template_name = 'tracker/reports.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all vehicles in families the user belongs to
        user_families = self.request.user.families.all()
        vehicles = Vehicle.objects.filter(family__in=user_families)
        
        # Get vehicle types and count
        vehicle_types = {}
        for vehicle in vehicles:
            vehicle_type = vehicle.get_type_display()
            if vehicle_type in vehicle_types:
                vehicle_types[vehicle_type] += 1
            else:
                vehicle_types[vehicle_type] = 1
        
        # Get maintenance and gas event counts and costs
        maintenance_events = Event.objects.filter(
            vehicle__in=vehicles,
            event_type='maintenance'
        )
        
        gas_events = Event.objects.filter(
            vehicle__in=vehicles,
            event_type='gas'
        )
        
        # Calculate maintenance statistics
        maintenance_count = maintenance_events.count()
        maintenance_cost = maintenance_events.aggregate(
            total=Sum('total_cost')
        )['total'] or 0
        
        # Calculate gas statistics
        gas_count = gas_events.count()
        gas_cost = gas_events.aggregate(
            total=Sum('total_cost')
        )['total'] or 0
        
        # Get due maintenance schedules
        due_maintenance = []
        for vehicle in vehicles:
            for schedule in vehicle.maintenance_schedules.filter(is_active=True):
                if schedule.is_due():
                    due_maintenance.append(schedule)
        
        # Add all data to context
        context['vehicles'] = vehicles
        context['vehicle_types'] = vehicle_types
        context['maintenance_count'] = maintenance_count
        context['maintenance_cost'] = maintenance_cost
        context['gas_count'] = gas_count
        context['gas_cost'] = gas_cost
        context['due_maintenance'] = due_maintenance
        
        return context

class VehicleReportView(LoginRequiredMixin, DetailView):
    model = Vehicle
    template_name = 'tracker/vehicle_report.html'
    context_object_name = 'vehicle'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vehicle = self.get_object()
        
        # Date range filtering
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
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
            mpg = event.get_mpg()
            if mpg:
                mpg_data.append({
                    'date': event.date.strftime('%Y-%m-%d'),
                    'mpg': float(mpg),  # Convert to float to ensure JSON serialization
                })
        
        # Convert mpg_data to a JSON string
        import json
        mpg_data_json = json.dumps(mpg_data)
        
        # Calculate average MPG
        if mpg_data:
            avg_mpg = sum(item['mpg'] for item in mpg_data) / len(mpg_data)
        else:
            avg_mpg = 0
        
        context.update({
            'maintenance_events': maintenance_events,
            'gas_events': gas_events,
            'outing_events': outing_events,
            'total_maintenance_cost': total_maintenance_cost,
            'total_gas_cost': total_gas_cost,
            'total_cost': total_maintenance_cost + total_gas_cost,
            'avg_mpg': avg_mpg,
            'mpg_data': mpg_data_json,  # Now a properly formatted JSON string
            'start_date': start_date,
            'end_date': end_date,
        })
        return context
    
    def test_func(self):
        vehicle = self.get_object()
        # Check if user is in the family that owns the vehicle
        return self.request.user.families.filter(id=vehicle.family.id).exists()

class MaintenanceScheduleListView(LoginRequiredMixin, ListView):
    model = MaintenanceSchedule
    template_name = 'tracker/maintenance_schedule_list.html'
    context_object_name = 'schedules'
    
    def get_queryset(self):
        # Get all vehicles in families the user belongs to
        user_families = self.request.user.families.all()
        vehicles = Vehicle.objects.filter(family__in=user_families)
        
        return MaintenanceSchedule.objects.filter(
            vehicle__in=vehicles,
            is_active=True
        ).order_by('vehicle', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        schedules = self.get_queryset()
        
        # Find due schedules
        due_schedules = [schedule for schedule in schedules if schedule.is_due()]
        
        # Group by vehicle
        user_families = self.request.user.families.all()
        vehicles = Vehicle.objects.filter(family__in=user_families)
        vehicle_schedules = {}
        
        for vehicle in vehicles:
            vehicle_schedules[vehicle] = schedules.filter(vehicle=vehicle)
        
        context.update({
            'due_schedules': due_schedules,
            'vehicle_schedules': vehicle_schedules,
        })
        
        return context

class MaintenanceScheduleCreateView(LoginRequiredMixin, CreateView):
    model = MaintenanceSchedule
    form_class = MaintenanceScheduleForm
    template_name = 'tracker/maintenance_schedule_form.html'
    success_url = reverse_lazy('maintenance_schedule_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        vehicle_id = self.request.GET.get('vehicle')
        if vehicle_id:
            initial['vehicle'] = vehicle_id
        return initial
    
    def form_valid(self, form):
        schedule = form.save(commit=False)
        schedule.created_by = self.request.user
        schedule.save()
        messages.success(self.request, 'Maintenance schedule created successfully!')
        return super().form_valid(form)

class MaintenanceScheduleUpdateView(LoginRequiredMixin, UpdateView):
    model = MaintenanceSchedule
    form_class = MaintenanceScheduleForm
    template_name = 'tracker/maintenance_schedule_form.html'
    success_url = reverse_lazy('maintenance_schedule_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, 'Maintenance schedule updated successfully!')
        return super().form_valid(form)
    
    def test_func(self):
        schedule = self.get_object()
        # Check if user is in the family that owns the vehicle
        return self.request.user.families.filter(id=schedule.vehicle.family.id).exists()

class MaintenanceScheduleDeleteView(LoginRequiredMixin, DeleteView):
    model = MaintenanceSchedule
    template_name = 'tracker/maintenance_schedule_confirm_delete.html'
    success_url = reverse_lazy('maintenance_schedule_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Maintenance schedule deleted successfully!')
        return super().delete(request, *args, **kwargs)
    
    def test_func(self):
        schedule = self.get_object()
        # Check if user is in the family that owns the vehicle
        return self.request.user.families.filter(id=schedule.vehicle.family.id).exists()


class ExportDataView(LoginRequiredMixin, View):
    def get(self, request, type, pk=None):
        """Export data to CSV format"""
        import csv
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{type}_export.csv"'
        
        writer = csv.writer(response)
        
        # Get all vehicles in families the user belongs to
        user_families = self.request.user.families.all()
        vehicles = Vehicle.objects.filter(family__in=user_families)
        
        if type == 'vehicle' and pk:
            # Export single vehicle data
            vehicle = get_object_or_404(Vehicle, pk=pk)
            
            # Ensure user has access to this vehicle
            if vehicle.family not in user_families:
                return redirect('reports')
            
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
                vehicle__in=vehicles,
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


# API Views for charts and data
class VehicleEventsApiView(LoginRequiredMixin, View):
    def get(self, request, vehicle_id):
        # Get vehicle and check access
        user_families = request.user.families.all()
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
        
        if vehicle.family not in user_families:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get events and format for chart
        events = Event.objects.filter(vehicle=vehicle).values('event_type').annotate(count=Count('id'))
        
        # Format data for charts
        data = {
            'labels': [event['event_type'] for event in events],
            'data': [event['count'] for event in events],
        }
        
        return JsonResponse(data)


class VehicleMileageApiView(LoginRequiredMixin, View):
    def get(self, request, vehicle_id):
        # Get vehicle and check access
        user_families = request.user.families.all()
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
        
        if vehicle.family not in user_families:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get events with mileage/hours data
        if vehicle.type == 'car':
            events = Event.objects.filter(
                vehicle=vehicle, 
                miles__isnull=False
            ).order_by('date').values('date', 'miles')
            
            # Format data for charts
            data = {
                'labels': [event['date'].strftime('%Y-%m-%d') for event in events],
                'data': [float(event['miles']) for event in events],
                'unit': 'miles',
            }
        else:
            events = Event.objects.filter(
                vehicle=vehicle, 
                hours__isnull=False
            ).order_by('date').values('date', 'hours')
            
            # Format data for charts
            data = {
                'labels': [event['date'].strftime('%Y-%m-%d') for event in events],
                'data': [float(event['hours']) for event in events],
                'unit': 'hours',
            }
        
        return JsonResponse(data)


class VehicleFuelEfficiencyApiView(LoginRequiredMixin, View):
    def get(self, request, vehicle_id):
        # Get vehicle and check access
        user_families = request.user.families.all()
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
        
        if vehicle.family not in user_families:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Only for cars
        if vehicle.type != 'car':
            return JsonResponse({'error': 'Not applicable for this vehicle type'}, status=400)
        
        # Get gas events
        gas_events = Event.objects.filter(
            vehicle=vehicle,
            event_type='gas',
            gallons__isnull=False
        ).order_by('date')
        
        # Calculate MPG for each event
        mpg_data = []
        for event in gas_events:
            mpg = event.get_mpg()
            if mpg:
                mpg_data.append({
                    'date': event.date.strftime('%Y-%m-%d'),
                    'mpg': mpg,
                })
        
        # Format data for charts
        data = {
            'labels': [item['date'] for item in mpg_data],
            'data': [item['mpg'] for item in mpg_data],
        }
        
        return JsonResponse(data)


def vehicle_events_api(request, vehicle_id):
    """Function-based view for backward compatibility"""
    view = VehicleEventsApiView.as_view()
    return view(request, vehicle_id=vehicle_id)


def vehicle_mileage_api(request, vehicle_id):
    """Function-based view for backward compatibility"""
    view = VehicleMileageApiView.as_view()
    return view(request, vehicle_id=vehicle_id)


def vehicle_fuel_efficiency_api(request, vehicle_id):
    """Function-based view for backward compatibility"""
    view = VehicleFuelEfficiencyApiView.as_view()
    return view(request, vehicle_id=vehicle_id)


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


def service_worker(request):
    """View for service worker script"""
    
    path = os.path.join(settings.BASE_DIR, 'static/service-worker.js')
    print
    with open(path, 'r') as sw_file:
        content = sw_file.read()
    
    return HttpResponse(content, content_type='application/javascript')


def health_check(request):
    """Health check endpoint for monitoring"""
    from django.db import connection
    from django.conf import settings
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

class LandingPageView(TemplateView):
    """
    Landing page view that shows when users are not logged in.
    This page has no navbar and includes direct links to login and register.
    """
    template_name = 'tracker/landing_page.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Redirect to dashboard if user is already logged in
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

class CustomLogoutView(LogoutView):
    """
    Custom logout view that redirects to the landing page
    """
    next_page = reverse_lazy('landing_page')