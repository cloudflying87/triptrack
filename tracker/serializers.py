# serializers.py
from rest_framework import serializers
from .models import Vehicle, Event, Location, TodoItem, MaintenanceCategory, MaintenanceSchedule

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        exclude = ['owner', 'created_at', 'updated_at']
        read_only_fields = ['id']

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        exclude = ['created_by', 'created_at']
        read_only_fields = ['id']

class MaintenanceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceCategory
        fields = '__all__'
        read_only_fields = ['id']

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        exclude = ['user', 'created_at', 'updated_at']
        read_only_fields = ['id']

class TodoItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TodoItem
        exclude = ['created_at']
        read_only_fields = ['id']

class MaintenanceScheduleSerializer(serializers.ModelSerializer):
    maintenance_type_name = serializers.ReadOnlyField(source='maintenance_type.name')
    is_due = serializers.BooleanField(read_only=True)
    due_status = serializers.FloatField(source='get_due_status', read_only=True)
    
    class Meta:
        model = MaintenanceSchedule
        exclude = ['created_at', 'updated_at']
        read_only_fields = ['id']