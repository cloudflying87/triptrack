from django.core.management.base import BaseCommand
from tracker.models import MaintenanceCategory

class Command(BaseCommand):
    help = 'Updates maintenance categories with appropriate vehicle types'

    def handle(self, *args, **options):
        # Car-specific maintenance
        car_maintenance = {
            'Oil Change': ['car'],
            'Brake Service': ['car'],
            'Tire Rotation': ['car'],
            'Tire Replacement': ['car'],
            'Air Filter Replacement': ['car'],
            'Cabin Filter Replacement': ['car'],
            'Transmission Service': ['car'],
            'Cooling System Service': ['car'],
            'Spark Plug Replacement': ['car'],
            'Fuel System Service': ['car'],
            'Timing Belt Replacement': ['car'],
            'Suspension Service': ['car'],
            'Wheel Alignment': ['car'],
            'Engine Tune-up': ['car'],
            'State Inspection': ['car'],
            'Wiper Blade Replacement': ['car'],
        }
        
        # Universal maintenance
        universal_maintenance = {
            'Registration Renewal': ['all'],
            'Battery Replacement': ['all'],
            'Light Bulb Replacement': ['all'],
        }
        
        # Boat-specific maintenance
        boat_maintenance = {
            'Engine Oil Change': ['boat'],
            'Lower Unit Oil Change': ['boat'],
            'Fuel Filter Replacement': ['boat'],
            'Water Pump Impeller': ['boat'],
            'Propeller Inspection': ['boat'],
            'Hull Cleaning': ['boat'],
            'Winterization': ['boat'],
            'Cooling System Flush': ['boat'],
            'Trim/Tilt Service': ['boat'],
        }
        
        # Update existing categories
        updated = 0
        created = 0
        
        all_categories = {**car_maintenance, **universal_maintenance, **boat_maintenance}
        
        for name, vehicle_types in all_categories.items():
            category, is_created = MaintenanceCategory.objects.get_or_create(
                name=name,
                defaults={'vehicle_types': vehicle_types}
            )
            
            if is_created:
                created += 1
                self.stdout.write(f"Created: {name} for {vehicle_types}")
            else:
                category.vehicle_types = vehicle_types
                category.save()
                updated += 1
                self.stdout.write(f"Updated: {name} for {vehicle_types}")
        
        self.stdout.write(self.style.SUCCESS(
            f'\nSuccessfully updated {updated} and created {created} maintenance categories'
        ))