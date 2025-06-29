from django.core.management.base import BaseCommand
from tracker.models import MaintenanceCategory

class Command(BaseCommand):
    help = 'Adds common maintenance categories to the database'

    def handle(self, *args, **options):
        categories = [
            {
                'name': 'Oil Change',
                'description': 'Regular oil and filter change to maintain engine performance',
                'vehicle_types': ['car', 'boat', 'other']
            },
            {
                'name': 'Brake Service',
                'description': 'Maintenance of brake pads, rotors, and fluid',
                'vehicle_types': ['car', 'other']
            },
            {
                'name': 'Tire Rotation',
                'description': 'Rotating tires to ensure even wear',
                'vehicle_types': ['car', 'other']
            },
            {
                'name': 'Tire Replacement',
                'description': 'Replacing tires when worn or damaged',
                'vehicle_types': ['car', 'other']
            },
            {
                'name': 'Air Filter Replacement',
                'description': 'Replacing engine air filter',
                'vehicle_types': ['car', 'boat', 'other']
            },
            {
                'name': 'Cabin Filter Replacement',
                'description': 'Replacing cabin air filter',
                'vehicle_types': ['car', 'other']
            },
            {
                'name': 'Battery Replacement',
                'description': 'Replacing vehicle battery',
                'vehicle_types': ['car', 'boat', 'other']
            },
            {
                'name': 'Transmission Service',
                'description': 'Fluid change and transmission maintenance',
                'vehicle_types': ['car', 'other']
            },
            {
                'name': 'Cooling System Service',
                'description': 'Coolant flush and radiator maintenance',
                'vehicle_types': ['car', 'boat', 'other']
            },
            {
                'name': 'Spark Plug Replacement',
                'description': 'Replacing spark plugs',
                'vehicle_types': ['car', 'boat', 'other']
            },
            {
                'name': 'Fuel System Service',
                'description': 'Cleaning or servicing fuel injectors and system',
                'vehicle_types': ['car', 'boat', 'other']
            },
            {
                'name': 'Timing Belt Replacement',
                'description': 'Replacing timing belt/chain',
                'vehicle_types': ['car', 'other']
            },
            {
                'name': 'Suspension Service',
                'description': 'Maintenance of shocks, struts and suspension components',
                'vehicle_types': ['car', 'other']
            },
            {
                'name': 'Wheel Alignment',
                'description': 'Aligning wheels for proper handling',
                'vehicle_types': ['car', 'other']
            },
            {
                'name': 'Wiper Blade Replacement',
                'description': 'Replacing windshield wiper blades',
                'vehicle_types': ['car', 'other']
            },
            {
                'name': 'Light Bulb Replacement',
                'description': 'Replacing headlights, taillights or other bulbs',
                'vehicle_types': ['car', 'boat', 'other']
            },
            {
                'name': 'Engine Tune-up',
                'description': 'General engine maintenance and tuning',
                'vehicle_types': ['car', 'boat', 'other']
            },
            {
                'name': 'State Inspection',
                'description': 'Annual/biannual state safety or emissions inspection',
                'vehicle_types': ['car', 'other']
            },
            {
                'name': 'Registration Renewal',
                'description': 'Renewing vehicle registration',
                'vehicle_types': ['car', 'boat', 'other']
            },
            # Boat-specific maintenance
            {
                'name': 'Hull Cleaning',
                'description': 'Cleaning barnacles and marine growth from hull',
                'vehicle_types': ['boat']
            },
            {
                'name': 'Propeller Service',
                'description': 'Maintenance and repair of propeller',
                'vehicle_types': ['boat']
            },
            {
                'name': 'Bilge Pump Service',
                'description': 'Maintenance of bilge pump system',
                'vehicle_types': ['boat']
            },
            {
                'name': 'Marine Electronics Service',
                'description': 'Maintenance of GPS, sonar, and other marine electronics',
                'vehicle_types': ['boat']
            },
            {
                'name': 'Winterization',
                'description': 'Preparing boat for winter storage',
                'vehicle_types': ['boat']
            },
            {
                'name': 'De-winterization',
                'description': 'Preparing boat for spring use',
                'vehicle_types': ['boat']
            },
        ]

        created_count = 0
        existing_count = 0

        for category_data in categories:
            category, created = MaintenanceCategory.objects.get_or_create(
                name=category_data['name'],
                defaults={
                    'description': category_data['description'],
                    'vehicle_types': category_data['vehicle_types']
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created category: {category.name}'))
            else:
                existing_count += 1
                self.stdout.write(self.style.WARNING(f'Category already exists: {category.name}'))
        
        self.stdout.write(self.style.SUCCESS(
            f'Finished adding maintenance categories: {created_count} created, {existing_count} already existed'
        ))