from django.contrib import admin
from .models import (
    Family, Vehicle, Location, Event, 
    MaintenanceCategory, TodoItem, MaintenanceSchedule
)

# Register your models here.
admin.site.register(Family)
admin.site.register(Vehicle)
admin.site.register(Location)
admin.site.register(Event)
admin.site.register(MaintenanceCategory)
admin.site.register(TodoItem)
admin.site.register(MaintenanceSchedule)
