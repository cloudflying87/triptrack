from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill
import logging

logger = logging.getLogger(__name__)

class Vehicle(models.Model):
    TYPE_CHOICES = [
        ('car', 'Car (miles)'),
        ('boat', 'Boat (hours)'),
        ('other', 'Other'),
    ]
    
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vehicles')
    name = models.CharField(max_length=100)
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.PositiveIntegerField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='car')
    image = ProcessedImageField(
        upload_to='vehicle_images/',
        processors=[ResizeToFill(800, 600)],
        format='JPEG',
        options={'quality': 85},
        null=True, 
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.year} {self.make} {self.model} ({self.name})"
    
    def get_unit(self):
        return "miles" if self.type == 'car' else "hours"
    
    def get_latest_miles_or_hours(self):
        latest_event = self.events.order_by('-date').first()
        if not latest_event:
            return 0
            
        if self.type == 'car' and latest_event.miles:
            return latest_event.miles
        elif self.type != 'car' and latest_event.hours:
            return latest_event.hours
        return 0


class Location(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='locations')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class MaintenanceCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Maintenance Categories"


class Trip(models.Model):
    """Renamed from Event to better match the TripTracker name"""
    TRIP_TYPES = [
        ('maintenance', 'Maintenance'),
        ('gas', 'Gas Fill-up'),
        ('outing', 'Outing'),
    ]
    
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='trips')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trips')
    trip_type = models.CharField(max_length=15, choices=TRIP_TYPES)
    date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    
    # Fields for tracking distance/time
    miles = models.DecimalField(max_digits=10, decimal_places=1, null=True, blank=True,
                               validators=[MinValueValidator(Decimal('0.0'))])
    hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                               validators=[MinValueValidator(Decimal('0.0'))])
    
    # Gas fill-up specific fields
    gallons = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    price_per_gallon = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True)
    total_cost = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Maintenance specific fields
    maintenance_category = models.ForeignKey(MaintenanceCategory, on_delete=models.SET_NULL, 
                                           null=True, blank=True)
    
    # Outing specific fields
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.get_trip_type_display()} - {self.vehicle} - {self.date}"

    def save(self, *args, **kwargs):
        # Calculate total cost if gallons and price_per_gallon are provided
        if self.gallons and self.price_per_gallon and not self.total_cost:
            self.total_cost = self.gallons * self.price_per_gallon
        
        # Check for maintenance schedules to mark as completed
        if self.trip_type == 'maintenance' and self.maintenance_category:
            try:
                schedules = MaintenanceSchedule.objects.filter(
                    vehicle=self.vehicle,
                    maintenance_type=self.maintenance_category,
                    is_active=True
                )
                
                for schedule in schedules:
                    # Update the last performed data
                    schedule.last_performed = self.date
                    if self.miles:
                        schedule.last_miles = self.miles
                    if self.hours:
                        schedule.last_hours = self.hours
                    schedule.save()
                    
                    logger.info(f"Updated maintenance schedule for {self.vehicle}: {self.maintenance_category}")
            except Exception as e:
                logger.error(f"Error updating maintenance schedule: {e}")
                
        super().save(*args, **kwargs)
    
    def get_mpg(self):
        if self.trip_type == 'gas' and self.miles and self.gallons:
            return round(self.miles / self.gallons, 2)
        return None
    
    class Meta:
        indexes = [
            models.Index(fields=['vehicle', 'date']),
            models.Index(fields=['trip_type']),
            models.Index(fields=['user', 'date']),
        ]


class TodoItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todo_items')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='todo_items', null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    priority = models.IntegerField(default=0)  # 0=normal, 1=medium, 2=high
    shared_with = models.ManyToManyField(User, related_name='shared_todos', blank=True)
    
    class Meta:
        ordering = ['completed', '-priority', 'due_date', 'created_at']
        indexes = [
            models.Index(fields=['user', 'completed']),
            models.Index(fields=['vehicle', 'completed']),
        ]
    
    def __str__(self):
        return self.title


class MaintenanceSchedule(models.Model):
    """Model for scheduling recurring maintenance"""
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='maintenance_schedules')
    maintenance_type = models.ForeignKey(MaintenanceCategory, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    
    # Recurrence intervals (at least one should be set)
    interval_miles = models.PositiveIntegerField(null=True, blank=True, 
        help_text="Miles between maintenance")
    interval_hours = models.PositiveIntegerField(null=True, blank=True,
        help_text="Hours between maintenance")
    interval_days = models.PositiveIntegerField(null=True, blank=True,
        help_text="Days between maintenance")
    
    # Last maintenance records
    last_performed = models.DateField(null=True, blank=True)
    last_miles = models.PositiveIntegerField(null=True, blank=True)
    last_hours = models.PositiveIntegerField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.vehicle}"
    
    def is_due(self):
        """Check if maintenance is due based on miles, hours, or days"""
        from datetime import date, timedelta
        
        # If no last performance data, it's due
        if not self.last_performed:
            return True
            
        # Check based on days
        if self.interval_days and self.last_performed:
            days_since = (date.today() - self.last_performed).days
            if days_since >= self.interval_days:
                return True
                
        # Check based on miles (for cars)
        if self.interval_miles and self.last_miles and self.vehicle.type == 'car':
            current_miles = self.vehicle.get_latest_miles_or_hours()
            if current_miles - self.last_miles >= self.interval_miles:
                return True
                
        # Check based on hours (for boats/other)
        if self.interval_hours and self.last_hours and self.vehicle.type != 'car':
            current_hours = self.vehicle.get_latest_miles_or_hours()
            if current_hours - self.last_hours >= self.interval_hours:
                return True
                
        return False