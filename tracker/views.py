from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LogoutView
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic.edit import FormView
from django.contrib import messages
from django.db.models import Sum, Count, Avg, F, Q, Max
from django.db.models.functions import TruncMonth, TruncYear
from datetime import datetime, timedelta
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import os
from .models import Vehicle, Event, Location, TodoItem, MaintenanceCategory, MaintenanceSchedule, Family
from .forms import (VehicleForm, MaintenanceEventForm, GasEventForm, 
                  OutingEventForm, TodoItemForm, LocationForm, UserRegisterForm,
                  FamilyForm, FamilyMemberForm,MaintenanceScheduleForm)

import logging
import json
logger = logging.getLogger('tracker')

def landing_page_view(request):
    logger.debug(f"Request headers: {request.headers}")
    logger.debug(f"Request META: {request.META}")
    
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
        
        # Count outings in last 30 days
        outing_count = Event.objects.filter(
            vehicle__in=vehicles,
            event_type='outing',
            date__gte=thirty_days_ago
        ).count()
        
        context['maintenance_cost'] = maintenance_cost
        context['gas_cost'] = gas_cost
        context['outing_count'] = outing_count
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
        
        # Get recent events for the main events tab
        context['events'] = vehicle.events.order_by('-date')[:5]
        context['todo_items'] = vehicle.todo_items.filter(completed=False)
        
        # Calculate statistics for the statistics tab
        all_events = vehicle.events.all()
        
        # Maintenance statistics
        maintenance_events = all_events.filter(event_type='maintenance')
        context['maintenance_count'] = maintenance_events.count()
        context['total_maintenance_cost'] = maintenance_events.aggregate(
            total=Sum('total_cost')
        )['total'] or 0
        
        # Gas statistics
        gas_events = all_events.filter(event_type='gas')
        context['total_spent_on_gas'] = gas_events.aggregate(
            total=Sum('total_cost')
        )['total'] or 0
        
        # Total cost (maintenance + gas)
        context['total_cost'] = context['total_maintenance_cost'] + context['total_spent_on_gas']
        
        # Fuel efficiency data for charts
        if vehicle.type == 'car':
            # MPG data for cars
            mpg_data = []
            gas_events_with_mpg = gas_events.filter(
                milespergallon__isnull=False
            ).order_by('date')
            
            for event in gas_events_with_mpg:
                mpg_data.append({
                    'date': event.date.strftime('%Y-%m-%d'),
                    'mpg': float(event.milespergallon)
                })
            
            context['mpg_data'] = json.dumps(mpg_data)
            
            # Calculate average MPG
            avg_mpg = gas_events.filter(
                milespergallon__isnull=False
            ).aggregate(avg=Avg('milespergallon'))['avg']
            context['avg_mpg'] = avg_mpg or 0
            
        elif vehicle.type == 'boat':
            # GPH data for boats
            gph_data = []
            gas_events_with_gph = gas_events.filter(
                gallonsperhour__isnull=False
            ).order_by('date')
            
            for event in gas_events_with_gph:
                gph_data.append({
                    'date': event.date.strftime('%Y-%m-%d'),
                    'gph': float(event.gallonsperhour)
                })
            
            context['gph_data'] = json.dumps(gph_data)
            
            # Calculate average GPH
            avg_gph = gas_events.filter(
                gallonsperhour__isnull=False
            ).aggregate(avg=Avg('gallonsperhour'))['avg']
            context['avg_gph'] = avg_gph or 0
        
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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        location = self.object

        # Get all events at this location
        all_events = Event.objects.filter(location=location)
        context['events'] = all_events.order_by('-date')[:20]  # Show last 20 events

        # Total visits
        context['total_visits'] = all_events.count()

        # Visits by year
        yearly_visits = (
            all_events
            .annotate(year=TruncYear('date'))
            .values('year')
            .annotate(visit_count=Count('id'))
            .order_by('-year')
        )
        context['yearly_visits'] = yearly_visits

        # Visits by month
        monthly_visits = (
            all_events
            .annotate(month=TruncMonth('date'))
            .values('month')
            .annotate(visit_count=Count('id'))
            .order_by('-month')
        )
        context['monthly_visits'] = monthly_visits

        # Vehicles that have visited this location
        vehicles_visited = (
            all_events
            .values('vehicle__id', 'vehicle__name', 'vehicle__make', 'vehicle__model')
            .annotate(visit_count=Count('id'))
            .order_by('-visit_count')
        )
        context['vehicles_visited'] = vehicles_visited

        return context

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

class VehicleReportView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
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
        
        # Group events by type (ordered by newest first)
        maintenance_events = events.filter(event_type='maintenance').order_by('-date')
        gas_events_raw = events.filter(event_type='gas').order_by('-date')
        outing_events = events.filter(event_type='outing').order_by('-date')

        # Enrich gas events with hours/miles between fill-ups and consumption rates
        gas_events = []
        gas_events_list = list(gas_events_raw)
        for i, event in enumerate(gas_events_list):
            event_data = {
                'event': event,
                'hours_between': None,
                'miles_between': None,
                'gallons_per_hour': None
            }

            # Calculate miles between fill-ups (for cars)
            if vehicle.type == 'car' and i < len(gas_events_list) - 1:
                next_event = gas_events_list[i + 1]
                if event.miles and next_event.miles:
                    miles_between = event.miles - next_event.miles
                    event_data['miles_between'] = miles_between

            # Calculate hours between fill-ups (for non-car vehicles)
            elif vehicle.type != 'car' and i < len(gas_events_list) - 1:
                next_event = gas_events_list[i + 1]
                if event.hours and next_event.hours:
                    hours_between = event.hours - next_event.hours
                    event_data['hours_between'] = hours_between

                    # Calculate gallons per hour
                    if event.gallons and hours_between > 0:
                        event_data['gallons_per_hour'] = event.gallons / hours_between

            gas_events.append(event_data)
        
        # Calculate statistics
        total_maintenance_cost = maintenance_events.aggregate(Sum('total_cost'))['total_cost__sum'] or 0
        total_gas_cost = gas_events_raw.aggregate(Sum('total_cost'))['total_cost__sum'] or 0
        
        # Calculate MPG
        mpg_data = []
        for event in gas_events_raw.order_by('date'):
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

        # Determine reading label based on vehicle type
        reading_label = 'Miles' if vehicle.type == 'car' else 'Hours'

        # Calculate monthly usage statistics with raw data
        monthly_stats_raw = (
            events
            .annotate(month=TruncMonth('date'))
            .values('month')
            .annotate(
                maintenance_cost=Sum('total_cost', filter=Q(event_type='maintenance')),
                gas_cost=Sum('total_cost', filter=Q(event_type='gas')),
                total_cost=Sum('total_cost'),
                max_miles=Max('miles'),
                max_hours=Max('hours'),
                outing_count=Count('id', filter=Q(event_type='outing'))
            )
            .order_by('-month')
        )

        # Calculate actual usage per month (hours/miles used during that month)
        monthly_stats = []
        monthly_list = list(monthly_stats_raw)

        for i, month_stat in enumerate(monthly_list):
            if i < len(monthly_list) - 1:
                next_month_stat = monthly_list[i + 1]

                if vehicle.type == 'car' and month_stat['max_miles'] and next_month_stat['max_miles']:
                    usage = month_stat['max_miles'] - next_month_stat['max_miles']
                    monthly_stats.append({
                        'month': month_stat['month'],
                        'maintenance_cost': month_stat['maintenance_cost'],
                        'gas_cost': month_stat['gas_cost'],
                        'total_cost': month_stat['total_cost'],
                        'usage': usage,
                        'outing_count': month_stat['outing_count']
                    })
                elif vehicle.type != 'car' and month_stat['max_hours'] and next_month_stat['max_hours']:
                    usage = month_stat['max_hours'] - next_month_stat['max_hours']
                    monthly_stats.append({
                        'month': month_stat['month'],
                        'maintenance_cost': month_stat['maintenance_cost'],
                        'gas_cost': month_stat['gas_cost'],
                        'total_cost': month_stat['total_cost'],
                        'usage': usage,
                        'outing_count': month_stat['outing_count']
                    })
                else:
                    monthly_stats.append({
                        'month': month_stat['month'],
                        'maintenance_cost': month_stat['maintenance_cost'],
                        'gas_cost': month_stat['gas_cost'],
                        'total_cost': month_stat['total_cost'],
                        'usage': None,
                        'outing_count': month_stat['outing_count']
                    })
            else:
                # First month (earliest) - can't calculate usage
                monthly_stats.append({
                    'month': month_stat['month'],
                    'maintenance_cost': month_stat['maintenance_cost'],
                    'gas_cost': month_stat['gas_cost'],
                    'total_cost': month_stat['total_cost'],
                    'usage': None,
                    'outing_count': month_stat['outing_count']
                })

        # Calculate yearly usage statistics
        yearly_stats = (
            events
            .annotate(year=TruncYear('date'))
            .values('year')
            .annotate(
                maintenance_cost=Sum('total_cost', filter=Q(event_type='maintenance')),
                gas_cost=Sum('total_cost', filter=Q(event_type='gas')),
                total_cost=Sum('total_cost'),
                max_miles=Max('miles'),
                max_hours=Max('hours'),
                outing_count=Count('id', filter=Q(event_type='outing'))
            )
            .order_by('-year')
        )

        # Calculate usage per year (miles/hours driven per year)
        yearly_usage = []
        for i, year_stat in enumerate(yearly_stats):
            if i < len(yearly_stats) - 1:
                next_year_stat = yearly_stats[i + 1]
                if vehicle.type == 'car' and year_stat['max_miles'] and next_year_stat['max_miles']:
                    usage = year_stat['max_miles'] - next_year_stat['max_miles']
                    yearly_usage.append({
                        'year': year_stat['year'],
                        'maintenance_cost': year_stat['maintenance_cost'],
                        'gas_cost': year_stat['gas_cost'],
                        'total_cost': year_stat['total_cost'],
                        'usage': usage,
                        'unit': 'miles',
                        'outing_count': year_stat['outing_count']
                    })
                elif vehicle.type != 'car' and year_stat['max_hours'] and next_year_stat['max_hours']:
                    usage = year_stat['max_hours'] - next_year_stat['max_hours']
                    yearly_usage.append({
                        'year': year_stat['year'],
                        'maintenance_cost': year_stat['maintenance_cost'],
                        'gas_cost': year_stat['gas_cost'],
                        'total_cost': year_stat['total_cost'],
                        'usage': usage,
                        'unit': 'hours',
                        'outing_count': year_stat['outing_count']
                    })
                else:
                    yearly_usage.append({
                        'year': year_stat['year'],
                        'maintenance_cost': year_stat['maintenance_cost'],
                        'gas_cost': year_stat['gas_cost'],
                        'total_cost': year_stat['total_cost'],
                        'usage': None,
                        'unit': reading_label.lower(),
                        'outing_count': year_stat['outing_count']
                    })
            else:
                yearly_usage.append({
                    'year': year_stat['year'],
                    'maintenance_cost': year_stat['maintenance_cost'],
                    'gas_cost': year_stat['gas_cost'],
                    'total_cost': year_stat['total_cost'],
                    'usage': None,
                    'unit': reading_label.lower(),
                    'outing_count': year_stat['outing_count']
                })

        # Get last recorded mileage or hours
        from datetime import date
        year_start = date(date.today().year, 1, 1)

        if vehicle.type == 'car':
            last_reading_event = events.filter(miles__isnull=False).order_by('-date', '-miles').first()
            last_reading = last_reading_event.miles if last_reading_event else None

            # Get start of year reading
            year_start_event = events.filter(
                miles__isnull=False,
                date__gte=year_start
            ).order_by('date', 'miles').first()

            year_start_reading = year_start_event.miles if year_start_event else None
            ytd_usage = (last_reading - year_start_reading) if (last_reading and year_start_reading) else None
        else:
            last_reading_event = events.filter(hours__isnull=False).order_by('-date', '-hours').first()
            last_reading = last_reading_event.hours if last_reading_event else None

            # Get start of year reading
            year_start_event = events.filter(
                hours__isnull=False,
                date__gte=year_start
            ).order_by('date', 'hours').first()

            year_start_reading = year_start_event.hours if year_start_event else None
            ytd_usage = (last_reading - year_start_reading) if (last_reading and year_start_reading) else None

        context.update({
            'maintenance_events': maintenance_events,
            'gas_events': gas_events,
            'outing_events': outing_events,
            'total_maintenance_cost': total_maintenance_cost,
            'total_gas_cost': total_gas_cost,
            'total_cost': total_maintenance_cost + total_gas_cost,
            'avg_mpg': avg_mpg,
            'mpg_data': mpg_data_json,  # Now a properly formatted JSON string
            'monthly_stats': monthly_stats,
            'yearly_usage': yearly_usage,
            'last_reading': last_reading,
            'reading_label': reading_label,
            'year_start_reading': year_start_reading,
            'ytd_usage': ytd_usage,
            'start_date': start_date,
            'end_date': end_date,
        })
        return context
    
    def test_func(self):
        vehicle = self.get_object()
        # Check if user is in the family that owns the vehicle
        return self.request.user.families.filter(id=vehicle.family.id).exists()

class VehicleUsageAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Vehicle
    template_name = 'tracker/vehicle_usage_analytics.html'
    context_object_name = 'vehicle'

    def get_context_data(self, **kwargs):
        import json
        from datetime import datetime
        context = super().get_context_data(**kwargs)
        vehicle = self.get_object()

        # Get filters from request
        selected_year = self.request.GET.get('year')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        # Get all events for this vehicle
        events = Event.objects.filter(vehicle=vehicle)

        # Get available years for the dropdown
        available_years = list(set([date.year for date in Event.objects.filter(vehicle=vehicle).dates('date', 'year')]))
        available_years.sort(reverse=True)

        # Apply filters
        if start_date and end_date:
            # Custom date range takes priority
            events = events.filter(date__gte=start_date, date__lte=end_date)
            all_outings = events.filter(event_type='outing').order_by('-date')
        elif selected_year and selected_year != 'all':
            # Filter by specific year
            events = events.filter(date__year=selected_year)
            all_outings = events.filter(event_type='outing').order_by('-date')
        elif selected_year == 'all':
            # Show all time - no year filter
            all_outings = events.filter(event_type='outing').order_by('-date')
        else:
            # Default to most recent year with data
            if available_years:
                selected_year = str(available_years[0])
                events = events.filter(date__year=selected_year)
            all_outings = events.filter(event_type='outing').order_by('-date')

        # Calculate monthly usage statistics (hours/miles used per month)
        monthly_stats_raw = (
            events
            .annotate(month=TruncMonth('date'))
            .values('month')
            .annotate(
                max_miles=Max('miles'),
                max_hours=Max('hours'),
                outing_count=Count('id', filter=Q(event_type='outing'))
            )
            .order_by('month')
        )

        # Calculate actual usage per month
        monthly_data = []
        monthly_list = list(monthly_stats_raw)

        for i, month_stat in enumerate(monthly_list):
            if i > 0:  # Start from second month to calculate difference
                prev_month_stat = monthly_list[i - 1]

                month_label = month_stat['month'].strftime('%Y-%m')
                outing_count = month_stat['outing_count']
                usage = None

                if vehicle.type == 'car' and month_stat['max_miles'] and prev_month_stat['max_miles']:
                    usage = month_stat['max_miles'] - prev_month_stat['max_miles']
                elif vehicle.type != 'car' and month_stat['max_hours'] and prev_month_stat['max_hours']:
                    usage = float(month_stat['max_hours'] - prev_month_stat['max_hours'])

                monthly_data.append({
                    'month': month_label,
                    'usage': usage if usage else 0,
                    'outings': outing_count
                })

        context.update({
            'monthly_data': json.dumps(monthly_data),
            'all_outings': all_outings,
            'reading_label': 'Miles' if vehicle.type == 'car' else 'Hours',
            'available_years': available_years,
            'selected_year': selected_year,
            'start_date': start_date,
            'end_date': end_date,
        })
        return context

    def test_func(self):
        vehicle = self.get_object()
        # Check if user is in the family that owns the vehicle
        return self.request.user.families.filter(id=vehicle.family.id).exists()

class EventImportView(LoginRequiredMixin, View):
    template_name = 'tracker/event_import.html'

    def get(self, request):
        # Get all vehicles in families the user belongs to
        user_families = request.user.families.all()
        vehicles = Vehicle.objects.filter(family__in=user_families)

        return render(request, self.template_name, {'vehicles': vehicles})

    def post(self, request):
        import csv
        from io import TextIOWrapper
        from datetime import datetime
        from decimal import Decimal

        if 'csv_file' not in request.FILES:
            messages.error(request, 'No file uploaded.')
            return redirect('event_import')

        csv_file = request.FILES['csv_file']
        vehicle_id = request.POST.get('vehicle')

        if not vehicle_id:
            messages.error(request, 'Please select a vehicle.')
            return redirect('event_import')

        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
            # Check if user has access to this vehicle
            if not request.user.families.filter(id=vehicle.family.id).exists():
                messages.error(request, 'You do not have access to this vehicle.')
                return redirect('event_import')
        except Vehicle.DoesNotExist:
            messages.error(request, 'Vehicle not found.')
            return redirect('event_import')

        try:
            # Read CSV file
            decoded_file = TextIOWrapper(csv_file.file, encoding='utf-8')
            csv_reader = csv.DictReader(decoded_file)

            imported_count = 0
            skipped_count = 0
            errors = []

            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    # Parse date
                    date_str = row.get('date', '').strip()
                    if not date_str:
                        errors.append(f"Row {row_num}: Missing date")
                        continue

                    # Try multiple date formats
                    date_obj = None
                    for date_format in ['%m/%d/%y', '%m/%d/%Y', '%Y-%m-%d']:
                        try:
                            date_obj = datetime.strptime(date_str, date_format).date()
                            break
                        except ValueError:
                            continue

                    if not date_obj:
                        errors.append(f"Row {row_num}: Invalid date format '{date_str}'")
                        continue

                    # Parse hours/miles
                    hours = row.get('hours', '').strip()
                    miles = row.get('miles', '').strip()

                    # Parse gallons (use Decimal for precision)
                    gallons = row.get('gallons', '').strip()

                    # Get location
                    location_name = row.get('location', '').strip()
                    location = None
                    if location_name:
                        location, _ = Location.objects.get_or_create(
                            name=location_name,
                            family=vehicle.family,
                            defaults={'created_by': request.user}
                        )

                    # Get notes
                    notes = row.get('notes', '').strip()

                    # Get event type (default to 'outing')
                    event_type = row.get('event_type', 'outing').strip().lower()
                    if event_type not in ['outing', 'gas', 'maintenance']:
                        event_type = 'outing'

                    # Check for duplicates (same vehicle, date, and event_type)
                    existing_event = Event.objects.filter(
                        vehicle=vehicle,
                        date=date_obj,
                        event_type=event_type
                    ).first()

                    if existing_event:
                        skipped_count += 1
                        continue

                    # Create event
                    event = Event.objects.create(
                        vehicle=vehicle,
                        event_type=event_type,
                        date=date_obj,
                        hours=Decimal(hours) if hours else None,
                        miles=float(miles) if miles else None,
                        gallons=Decimal(gallons) if gallons else None,
                        location=location,
                        notes=notes,
                        created_by=request.user
                    )
                    imported_count += 1

                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")

            if imported_count > 0:
                messages.success(request, f'Successfully imported {imported_count} events.')

            if skipped_count > 0:
                messages.info(request, f'Skipped {skipped_count} duplicate events.')

            if errors:
                for error in errors[:10]:  # Show first 10 errors
                    messages.warning(request, error)
                if len(errors) > 10:
                    messages.warning(request, f'... and {len(errors) - 10} more errors')

            return redirect('event_list')

        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('event_import')

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
    db_error = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as e:
        db_ok = False
        db_error = str(e)
    
    # Check Redis connection
    redis_ok = True
    redis_error = None
    try:
        redis_client = Redis.from_url(settings.CACHES['default']['LOCATION'])
        redis_client.ping()
    except Exception as e:
        redis_ok = False
        redis_error = str(e)
    
    status = db_ok and redis_ok
    
    data = {
        'status': 'ok' if status else 'error',
        'database': 'ok' if db_ok else 'error',
        'cache': 'ok' if redis_ok else 'error',
        'hostname': socket.gethostname(),
        'debug': settings.DEBUG,
    }
    
    # Include error details if something is wrong
    if not db_ok:
        data['database_error'] = db_error
    if not redis_ok:
        data['cache_error'] = redis_error
    
    return JsonResponse(data, status=200 if status else 500)

def debug_info(request):
    """Debug information view - only accessible to superusers"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    from django.conf import settings
    import sys
    import os
    
    data = {
        'debug': settings.DEBUG,
        'python_version': sys.version,
        'django_version': __import__('django').get_version(),
        'allowed_hosts': settings.ALLOWED_HOSTS,
        'database_url': os.environ.get('DATABASE_URL', 'Not set'),
        'redis_url': os.environ.get('REDIS_URL', 'Not set'),
        'db_settings': {
            'ENGINE': settings.DATABASES['default'].get('ENGINE', 'Not set'),
            'NAME': settings.DATABASES['default'].get('NAME', 'Not set'),
            'USER': settings.DATABASES['default'].get('USER', 'Not set'),
            'HOST': settings.DATABASES['default'].get('HOST', 'Not set'),
            'PORT': settings.DATABASES['default'].get('PORT', 'Not set'),
        },
        'environment_vars': {
            'DEBUG': os.environ.get('DEBUG'),
            'SECRET_KEY': 'SET' if os.environ.get('SECRET_KEY') else 'NOT SET',
            'ALLOWED_HOSTS': os.environ.get('ALLOWED_HOSTS'),
        },
        'migrations_status': {},
    }
    
    # Check migration status
    from django.core.management import execute_from_command_line
    from io import StringIO
    import sys
    
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        execute_from_command_line(['manage.py', 'showmigrations', '--verbosity=0'])
        migration_output = sys.stdout.getvalue()
        data['migrations_output'] = migration_output
    except Exception as e:
        data['migrations_error'] = str(e)
    finally:
        sys.stdout = old_stdout
    
    return JsonResponse(data, json_dumps_params={'indent': 2})

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


class VehicleDetailAPIView(LoginRequiredMixin, APIView):
    """
    API endpoint to get vehicle details (for JavaScript)
    """
    def get(self, request, pk):
        try:
            # Check if user has access to this vehicle
            user_families = request.user.families.all()
            vehicle = Vehicle.objects.get(pk=pk, family__in=user_families)
            
            # Return vehicle data
            data = {
                'id': vehicle.id,
                'name': vehicle.name,
                'type': vehicle.type,
                'make': vehicle.make,
                'model': vehicle.model,
                'year': vehicle.year,
            }
            return Response(data)
        
        except Vehicle.DoesNotExist:
            return Response(
                {'error': 'Vehicle not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )


@login_required
@require_GET
def maintenance_categories_api(request):
    """API endpoint to get maintenance categories filtered by vehicle type"""
    vehicle_id = request.GET.get('vehicle')
    
    if not vehicle_id:
        return JsonResponse({'categories': []})
    
    try:
        # Get the vehicle and check user access
        user_families = request.user.families.all()
        vehicle = Vehicle.objects.get(pk=vehicle_id, family__in=user_families)
        
        # Get categories that apply to this vehicle type
        from .models import MaintenanceCategory
        categories = MaintenanceCategory.objects.filter(
            vehicle_types__contains=[vehicle.type]
        ).values('id', 'name', 'description')
        
        return JsonResponse({
            'categories': list(categories),
            'vehicle_type': vehicle.type
        })
        
    except Vehicle.DoesNotExist:
        return JsonResponse({'error': 'Vehicle not found or access denied'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)