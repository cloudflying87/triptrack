from django.core.management.base import BaseCommand
from tracker.models import Event, Vehicle


class Command(BaseCommand):
    help = 'Migrate gas records from miles to hours for boat vehicles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )
        parser.add_argument(
            '--vehicle-id',
            type=int,
            help='Only migrate records for a specific vehicle ID',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        vehicle_id = options.get('vehicle_id')
        
        # Find all gas events for boat vehicles that have miles but no hours
        queryset = Event.objects.filter(
            event_type='gas',
            vehicle__type__in=['boat', 'other'],
            miles__isnull=False,
            hours__isnull=True
        )
        
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        
        events_to_migrate = queryset.select_related('vehicle')
        
        if not events_to_migrate.exists():
            self.stdout.write(
                self.style.SUCCESS('No gas records need to be migrated.')
            )
            return
        
        self.stdout.write(
            f'Found {events_to_migrate.count()} gas records that need migration:'
        )
        
        for event in events_to_migrate:
            self.stdout.write(
                f'  - Event {event.id}: {event.vehicle.name} ({event.vehicle.type}) '
                f'on {event.date} - Miles: {event.miles}'
            )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('Dry run mode - no changes made.')
            )
            return
        
        # Ask for confirmation unless in dry run mode
        confirm = input(
            f'\nDo you want to migrate {events_to_migrate.count()} records? '
            'This will move the miles values to the hours field. (y/N): '
        )
        
        if confirm.lower() != 'y':
            self.stdout.write('Migration cancelled.')
            return
        
        # Perform the migration
        migrated_count = 0
        for event in events_to_migrate:
            old_miles = event.miles
            event.hours = old_miles  # Move miles value to hours
            event.miles = None  # Clear miles field
            event.save()
            migrated_count += 1
            
            self.stdout.write(
                f'Migrated Event {event.id}: {old_miles} miles -> {event.hours} hours'
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully migrated {migrated_count} gas records from miles to hours.'
            )
        )
        
        # Show summary by vehicle
        vehicles = Vehicle.objects.filter(
            type__in=['boat', 'other'],
            events__in=events_to_migrate
        ).distinct()
        
        self.stdout.write('\nSummary by vehicle:')
        for vehicle in vehicles:
            migrated_for_vehicle = events_to_migrate.filter(vehicle=vehicle).count()
            self.stdout.write(
                f'  {vehicle.name} ({vehicle.type}): {migrated_for_vehicle} records migrated'
            )