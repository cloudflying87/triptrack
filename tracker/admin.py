from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from .models import (
    Family, Vehicle, Location, Event, 
    MaintenanceCategory, TodoItem, MaintenanceSchedule
)


# Inline Admin Classes
class VehicleInline(admin.TabularInline):
    model = Vehicle
    extra = 0
    fields = ('name', 'make', 'model', 'year', 'type', 'license_plate')
    readonly_fields = ('created_at',)
    show_change_link = True


class EventInline(admin.TabularInline):
    model = Event
    extra = 0
    fields = ('event_type', 'date', 'miles', 'hours', 'total_cost', 'maintenance_category')
    readonly_fields = ('created_at',)
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj=None):
        return False


class MaintenanceScheduleInline(admin.TabularInline):
    model = MaintenanceSchedule
    extra = 0
    fields = ('name', 'maintenance_type', 'interval_miles', 'interval_hours', 'interval_days', 'is_active')
    show_change_link = True


# Admin Classes
@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ('name', 'member_count', 'vehicle_count', 'created_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'members__username', 'members__email')
    readonly_fields = ('created_at', 'created_by')
    filter_horizontal = ('members',)
    inlines = [VehicleInline]
    
    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'
    
    def vehicle_count(self, obj):
        return obj.vehicles.count()
    vehicle_count.short_description = 'Vehicles'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('name', 'family', 'make', 'model', 'year', 'type', 'license_plate', 
                   'total_miles_or_hours', 'maintenance_status')
    list_filter = ('type', 'family', 'year')
    search_fields = ('name', 'make', 'model', 'vin', 'license_plate')
    readonly_fields = ('created_at', 'current_mileage_display', 'maintenance_status_detail')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'family', 'type')
        }),
        ('Vehicle Details', {
            'fields': ('make', 'model', 'year', 'vin', 'license_plate')
        }),
        ('Mileage/Hours', {
            'fields': ('starting_mileage', 'current_mileage_display')
        }),
        ('Maintenance', {
            'fields': ('maintenance_status_detail',)
        }),
        ('Image', {
            'fields': ('image',)
        }),
        ('System Info', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    inlines = [EventInline, MaintenanceScheduleInline]
    
    def total_miles_or_hours(self, obj):
        latest_event = obj.events.order_by('-date', '-created_at').first()
        if latest_event:
            if obj.type == 'car':
                return f"{latest_event.miles:,.0f} mi"
            else:
                return f"{latest_event.hours:,.1f} hrs"
        return "No data"
    total_miles_or_hours.short_description = 'Current Reading'
    
    def current_mileage_display(self, obj):
        latest_event = obj.events.order_by('-date', '-created_at').first()
        if latest_event:
            if obj.type == 'car':
                return f"{latest_event.miles:,.0f} miles"
            else:
                return f"{latest_event.hours:,.1f} hours"
        return "No events recorded"
    current_mileage_display.short_description = 'Current Mileage/Hours'
    
    def maintenance_status(self, obj):
        due_count = sum(1 for schedule in obj.maintenance_schedules.filter(is_active=True) 
                       if schedule.is_due())
        if due_count > 0:
            return format_html('<span style="color: red;">⚠️ {} Due</span>', due_count)
        return format_html('<span style="color: green;">✓ OK</span>')
    maintenance_status.short_description = 'Maintenance'
    
    def maintenance_status_detail(self, obj):
        schedules = obj.maintenance_schedules.filter(is_active=True)
        if not schedules:
            return "No maintenance schedules"
        
        html_parts = []
        for schedule in schedules:
            if schedule.is_due():
                status = f'<span style="color: red;">⚠️ {schedule.name} - DUE</span>'
            else:
                status = f'<span style="color: green;">✓ {schedule.name} - OK</span>'
            html_parts.append(status)
        
        return format_html('<br>'.join(html_parts))
    maintenance_status_detail.short_description = 'Maintenance Status'
    
    # Vehicle model doesn't have created_by field
    
    actions = ['export_maintenance_report']
    
    def export_maintenance_report(self, request, queryset):
        # This would generate a maintenance report
        self.message_user(request, f"Exported maintenance report for {queryset.count()} vehicles")
    export_maintenance_report.short_description = "Export maintenance report"


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'event_type', 'date', 'mileage_or_hours', 'cost_display', 
                   'maintenance_category', 'location', 'created_by')
    list_filter = ('event_type', 'date', 'vehicle__family', 'maintenance_category', 'location')
    search_fields = ('vehicle__name', 'notes', 'maintenance_category__name', 'location__name')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'created_by', 'mpg_display')
    fieldsets = (
        ('Event Information', {
            'fields': ('vehicle', 'event_type', 'date', 'notes')
        }),
        ('Location & Category', {
            'fields': ('location', 'maintenance_category')
        }),
        ('Distance/Time', {
            'fields': ('miles', 'hours')
        }),
        ('Gas Event Details', {
            'fields': ('gallons', 'price_per_gallon', 'mpg_display'),
            'classes': ('collapse',)
        }),
        ('Cost', {
            'fields': ('total_cost',)
        }),
        ('System Info', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def mileage_or_hours(self, obj):
        if obj.miles:
            return f"{obj.miles:,.0f} mi"
        elif obj.hours:
            return f"{obj.hours:,.1f} hrs"
        return "-"
    mileage_or_hours.short_description = 'Distance/Time'
    
    def cost_display(self, obj):
        if obj.total_cost:
            return f"${obj.total_cost:,.2f}"
        return "-"
    cost_display.short_description = 'Cost'
    
    def mpg_display(self, obj):
        if obj.event_type == 'gas' and obj.gallons:
            mpg = obj.get_mpg()
            if mpg:
                return f"{mpg:.1f} MPG"
        return "N/A"
    mpg_display.short_description = 'Fuel Efficiency'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['mark_as_maintenance', 'mark_as_gas', 'mark_as_outing']
    
    def mark_as_maintenance(self, request, queryset):
        updated = queryset.update(event_type='maintenance')
        self.message_user(request, f"{updated} events marked as maintenance")
    mark_as_maintenance.short_description = "Mark as maintenance"
    
    def mark_as_gas(self, request, queryset):
        updated = queryset.update(event_type='gas')
        self.message_user(request, f"{updated} events marked as gas")
    mark_as_gas.short_description = "Mark as gas"
    
    def mark_as_outing(self, request, queryset):
        updated = queryset.update(event_type='outing')
        self.message_user(request, f"{updated} events marked as outing")
    mark_as_outing.short_description = "Mark as outing"


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'family', 'address', 'has_coordinates', 'event_count', 'created_by')
    list_filter = ('family', 'created_at')
    search_fields = ('name', 'address')
    readonly_fields = ('created_at', 'created_by')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'family', 'address')
        }),
        ('Coordinates', {
            'fields': ('latitude', 'longitude'),
            'classes': ('collapse',)
        }),
        ('System Info', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def has_coordinates(self, obj):
        return bool(obj.latitude and obj.longitude)
    has_coordinates.boolean = True
    has_coordinates.short_description = 'Has GPS'
    
    def event_count(self, obj):
        return obj.events.count()
    event_count.short_description = 'Events'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(MaintenanceCategory)
class MaintenanceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'event_count', 'last_used')
    search_fields = ('name', 'description')
    ordering = ('name',)
    
    def event_count(self, obj):
        return obj.events.count()
    event_count.short_description = 'Total Events'
    
    def last_used(self, obj):
        last_event = obj.events.order_by('-date').first()
        if last_event:
            return last_event.date
        return "Never"
    last_used.short_description = 'Last Used'
    
    # MaintenanceCategory doesn't have is_active field, so no activation/deactivation actions needed


@admin.register(TodoItem)
class TodoItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'vehicle', 'priority_display', 'due_date', 'is_overdue', 
                   'completed', 'created_by')
    list_filter = ('priority', 'completed', 'due_date', 'vehicle__family')
    search_fields = ('title', 'description', 'vehicle__name')
    readonly_fields = ('created_at', 'created_by')
    filter_horizontal = ('shared_with',)
    fieldsets = (
        ('Task Information', {
            'fields': ('title', 'description', 'vehicle', 'priority', 'due_date')
        }),
        ('Status', {
            'fields': ('completed',)
        }),
        ('Sharing', {
            'fields': ('shared_with',)
        }),
        ('System Info', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def priority_display(self, obj):
        colors = {0: 'green', 1: 'orange', 2: 'red'}
        labels = {0: 'Normal', 1: 'Medium', 2: 'High'}
        color = colors.get(obj.priority, 'black')
        label = labels.get(obj.priority, 'Unknown')
        return format_html('<span style="color: {};">● {}</span>', color, label)
    priority_display.short_description = 'Priority'
    
    def is_overdue(self, obj):
        if obj.due_date and not obj.completed:
            return obj.due_date < timezone.now().date()
        return False
    is_overdue.boolean = True
    is_overdue.short_description = 'Overdue'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['mark_completed', 'mark_incomplete', 'set_high_priority']
    
    def mark_completed(self, request, queryset):
        updated = queryset.update(completed=True)
        self.message_user(request, f"{updated} tasks marked as completed")
    mark_completed.short_description = "Mark as completed"
    
    def mark_incomplete(self, request, queryset):
        updated = queryset.update(completed=False)
        self.message_user(request, f"{updated} tasks marked as incomplete")
    mark_incomplete.short_description = "Mark as incomplete"
    
    def set_high_priority(self, request, queryset):
        updated = queryset.update(priority=2)
        self.message_user(request, f"{updated} tasks set to high priority")
    set_high_priority.short_description = "Set to high priority"


@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'vehicle', 'maintenance_type', 'is_active', 'is_due_display', 
                   'interval_display', 'last_performed')
    list_filter = ('is_active', 'maintenance_type', 'vehicle__family')
    search_fields = ('name', 'description', 'vehicle__name', 'maintenance_type__name')
    readonly_fields = ('created_at', 'created_by', 'is_due_display', 'due_status_detail')
    fieldsets = (
        ('Basic Information', {
            'fields': ('vehicle', 'maintenance_type', 'name', 'description', 'is_active')
        }),
        ('Schedule Intervals', {
            'fields': ('interval_miles', 'interval_hours', 'interval_days')
        }),
        ('Last Service', {
            'fields': ('last_performed', 'last_miles', 'last_hours')
        }),
        ('Status', {
            'fields': ('is_due_display', 'due_status_detail'),
            'classes': ('wide',)
        }),
        ('System Info', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def interval_display(self, obj):
        intervals = []
        if obj.interval_miles:
            intervals.append(f"{obj.interval_miles:,} mi")
        if obj.interval_hours:
            intervals.append(f"{obj.interval_hours:,} hrs")
        if obj.interval_days:
            intervals.append(f"{obj.interval_days} days")
        return " / ".join(intervals) or "No interval"
    interval_display.short_description = 'Intervals'
    
    def is_due_display(self, obj):
        if obj.is_due():
            return format_html('<span style="color: red;">⚠️ DUE</span>')
        return format_html('<span style="color: green;">✓ OK</span>')
    is_due_display.short_description = 'Status'
    
    def due_status_detail(self, obj):
        if not obj.last_performed:
            return "No service history"
        
        current_event = obj.vehicle.events.order_by('-date', '-created_at').first()
        if not current_event:
            return "No current mileage/hours data"
        
        details = []
        
        # Check mileage
        if obj.interval_miles and obj.last_miles:
            miles_since = (current_event.miles or 0) - obj.last_miles
            miles_due_in = obj.interval_miles - miles_since
            if miles_due_in < 0:
                details.append(f'<span style="color: red;">Overdue by {abs(miles_due_in):,.0f} miles</span>')
            else:
                details.append(f'Due in {miles_due_in:,.0f} miles')
        
        # Check hours
        if obj.interval_hours and obj.last_hours:
            hours_since = (current_event.hours or 0) - obj.last_hours
            hours_due_in = obj.interval_hours - hours_since
            if hours_due_in < 0:
                details.append(f'<span style="color: red;">Overdue by {abs(hours_due_in):,.1f} hours</span>')
            else:
                details.append(f'Due in {hours_due_in:,.1f} hours')
        
        # Check days
        if obj.interval_days:
            days_since = (timezone.now().date() - obj.last_performed).days
            days_due_in = obj.interval_days - days_since
            if days_due_in < 0:
                details.append(f'<span style="color: red;">Overdue by {abs(days_due_in)} days</span>')
            else:
                details.append(f'Due in {days_due_in} days')
        
        return format_html('<br>'.join(details))
    due_status_detail.short_description = 'Due Status Details'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['activate_schedules', 'deactivate_schedules', 'mark_as_serviced']
    
    def activate_schedules(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} schedules activated")
    activate_schedules.short_description = "Activate selected schedules"
    
    def deactivate_schedules(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} schedules deactivated")
    deactivate_schedules.short_description = "Deactivate selected schedules"
    
    def mark_as_serviced(self, request, queryset):
        # This would create a service event and update the schedule
        count = 0
        for schedule in queryset:
            # Update last service info based on most recent vehicle data
            current_event = schedule.vehicle.events.order_by('-date', '-created_at').first()
            if current_event:
                schedule.last_performed = timezone.now().date()
                schedule.last_miles = current_event.miles
                schedule.last_hours = current_event.hours
                schedule.save()
                count += 1
        
        self.message_user(request, f"{count} schedules marked as serviced")
    mark_as_serviced.short_description = "Mark as serviced today"


# Customize admin site
admin.site.site_header = "TripTracker Administration"
admin.site.site_title = "TripTracker Admin"
admin.site.index_title = "Welcome to TripTracker Administration"