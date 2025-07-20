from django.core.management.base import BaseCommand
from tracker.models import MaintenanceCategory, MaintenanceSchedule, Vehicle
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Creates default maintenance schedules for existing vehicles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            default=1,
            help='User ID to assign as creator of schedules (default: 1)'
        )

    def handle(self, *args, **options):
        user_id = options['user_id']
        
        try:
            creator = User.objects.get(id=user_id)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User with ID {user_id} not found'))
            return
        
        # Default car schedules (miles/months)
        car_defaults = [
            {'name': 'Oil Change', 'interval_miles': 5000, 'interval_days': 180, 'description': 'Regular oil and filter change'},
            {'name': 'Tire Rotation', 'interval_miles': 6000, 'interval_days': 180, 'description': 'Rotate tires for even wear'},
            {'name': 'Air Filter Replacement', 'interval_miles': 12000, 'interval_days': 365, 'description': 'Replace engine air filter'},
            {'name': 'Cabin Filter Replacement', 'interval_miles': 15000, 'interval_days': 365, 'description': 'Replace cabin air filter'},
            {'name': 'Brake Service', 'interval_miles': 25000, 'interval_days': 730, 'description': 'Inspect brakes and replace pads if needed'},
        ]
        
        # Default boat schedules (hours/months)
        boat_defaults = [
            {'name': 'Engine Oil Change', 'interval_hours': 50, 'interval_days': 180, 'description': 'Change engine oil and filter'},
            {'name': 'Lower Unit Oil Change', 'interval_hours': 100, 'interval_days': 365, 'description': 'Change lower unit gear oil'},
            {'name': 'Spark Plug Replacement', 'interval_hours': 100, 'interval_days': 365, 'description': 'Replace spark plugs'},
            {'name': 'Water Pump Impeller', 'interval_hours': 200, 'interval_days': 730, 'description': 'Replace water pump impeller'},
            {'name': 'Fuel Filter Replacement', 'interval_hours': 100, 'interval_days': 365, 'description': 'Replace fuel filter'},
        ]
        
        cars = Vehicle.objects.filter(type='car')
        boats = Vehicle.objects.filter(type='boat')
        
        self.stdout.write(f"Found {cars.count()} cars and {boats.count()} boats")
        
        created_count = 0
        
        # Create car schedules
        for vehicle in cars:
            for schedule_data in car_defaults:
                try:
                    category = MaintenanceCategory.objects.get(name=schedule_data['name'])
                    schedule, created = MaintenanceSchedule.objects.get_or_create(
                        vehicle=vehicle,
                        maintenance_type=category,
                        defaults={
                            'name': f"{schedule_data['name']} - {vehicle.name}",
                            'description': schedule_data['description'],
                            'interval_miles': schedule_data.get('interval_miles'),
                            'interval_days': schedule_data.get('interval_days'),
                            'created_by': creator
                        }
                    )
                    if created:
                        created_count += 1
                        self.stdout.write(f"Created: {schedule.name}")
                except MaintenanceCategory.DoesNotExist:
                    self.stdout.write(f"Category '{schedule_data['name']}' not found")
                except Exception as e:
                    self.stdout.write(f"Error creating schedule for {vehicle.name}: {e}")
        
        # Create boat schedules
        for vehicle in boats:
            for schedule_data in boat_defaults:
                try:
                    category = MaintenanceCategory.objects.get(name=schedule_data['name'])
                    schedule, created = MaintenanceSchedule.objects.get_or_create(
                        vehicle=vehicle,
                        maintenance_type=category,
                        defaults={
                            'name': f"{schedule_data['name']} - {vehicle.name}",
                            'description': schedule_data['description'],
                            'interval_hours': schedule_data.get('interval_hours'),
                            'interval_days': schedule_data.get('interval_days'),
                            'created_by': creator
                        }
                    )
                    if created:
                        created_count += 1
                        self.stdout.write(f"Created: {schedule.name}")
                except MaintenanceCategory.DoesNotExist:
                    self.stdout.write(f"Category '{schedule_data['name']}' not found")
                except Exception as e:
                    self.stdout.write(f"Error creating schedule for {vehicle.name}: {e}")
        
        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully created {created_count} maintenance schedules'))