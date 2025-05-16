from django.core.management.base import BaseCommand
from tracker.models import MaintenanceCategory

class Command(BaseCommand):
    help = 'Adds common maintenance categories to the database'

    def handle(self, *args, **options):
        categories = [
            {
                'name': 'Oil Change',
                'description': 'Regular oil and filter change to maintain engine performance'
            },
            {
                'name': 'Brake Service',
                'description': 'Maintenance of brake pads, rotors, and fluid'
            },
            {
                'name': 'Tire Rotation',
                'description': 'Rotating tires to ensure even wear'
            },
            {
                'name': 'Tire Replacement',
                'description': 'Replacing tires when worn or damaged'
            },
            {
                'name': 'Air Filter Replacement',
                'description': 'Replacing engine air filter'
            },
            {
                'name': 'Cabin Filter Replacement',
                'description': 'Replacing cabin air filter'
            },
            {
                'name': 'Battery Replacement',
                'description': 'Replacing vehicle battery'
            },
            {
                'name': 'Transmission Service',
                'description': 'Fluid change and transmission maintenance'
            },
            {
                'name': 'Cooling System Service',
                'description': 'Coolant flush and radiator maintenance'
            },
            {
                'name': 'Spark Plug Replacement',
                'description': 'Replacing spark plugs'
            },
            {
                'name': 'Fuel System Service',
                'description': 'Cleaning or servicing fuel injectors and system'
            },
            {
                'name': 'Timing Belt Replacement',
                'description': 'Replacing timing belt/chain'
            },
            {
                'name': 'Suspension Service',
                'description': 'Maintenance of shocks, struts and suspension components'
            },
            {
                'name': 'Wheel Alignment',
                'description': 'Aligning wheels for proper handling'
            },
            {
                'name': 'Wiper Blade Replacement',
                'description': 'Replacing windshield wiper blades'
            },
            {
                'name': 'Light Bulb Replacement',
                'description': 'Replacing headlights, taillights or other bulbs'
            },
            {
                'name': 'Engine Tune-up',
                'description': 'General engine maintenance and tuning'
            },
            {
                'name': 'State Inspection',
                'description': 'Annual/biannual state safety or emissions inspection'
            },
            {
                'name': 'Registration Renewal',
                'description': 'Renewing vehicle registration'
            },
        ]

        created_count = 0
        existing_count = 0

        for category_data in categories:
            category, created = MaintenanceCategory.objects.get_or_create(
                name=category_data['name'],
                defaults={'description': category_data['description']}
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