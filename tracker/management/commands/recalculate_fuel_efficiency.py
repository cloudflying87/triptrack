from django.core.management.base import BaseCommand
from tracker.models import Event, Vehicle
from decimal import Decimal

class Command(BaseCommand):
    help = 'Recalculates fuel efficiency for existing gas fill-up events'

    def add_arguments(self, parser):
        parser.add_argument(
            '--vehicle-type',
            type=str,
            choices=['car', 'boat', 'other', 'all'],
            default='all',
            help='Vehicle type to recalculate (default: all)'
        )
        parser.add_argument(
            '--vehicle-id',
            type=int,
            help='Specific vehicle ID to recalculate'
        )

    def handle(self, *args, **options):
        vehicle_type = options['vehicle_type']
        vehicle_id = options['vehicle_id']
        
        # Get vehicles to process
        if vehicle_id:
            vehicles = Vehicle.objects.filter(id=vehicle_id)
            if not vehicles.exists():
                self.stdout.write(self.style.ERROR(f'Vehicle with ID {vehicle_id} not found'))
                return
        elif vehicle_type == 'all':
            vehicles = Vehicle.objects.all()
        else:
            vehicles = Vehicle.objects.filter(type=vehicle_type)
        
        total_updated = 0
        total_skipped = 0
        
        for vehicle in vehicles:
            self.stdout.write(f'\nProcessing {vehicle.name} ({vehicle.get_type_display()})...')
            
            # Get all gas events for this vehicle, ordered by date
            gas_events = Event.objects.filter(
                vehicle=vehicle,
                event_type='gas'
            ).order_by('date')
            
            updated_count = 0
            skipped_count = 0
            
            for i, event in enumerate(gas_events):
                if not event.gallons or event.gallons <= 0:
                    self.stdout.write(f'  Skipping event {event.date}: no gallons data')
                    skipped_count += 1
                    continue
                
                if vehicle.type == 'car':
                    # Recalculate MPG for cars
                    if not event.miles:
                        self.stdout.write(f'  Skipping event {event.date}: no miles data')
                        skipped_count += 1
                        continue
                    
                    # Find previous gas event
                    prev_event = gas_events.filter(date__lt=event.date).last()
                    
                    # Calculate miles driven
                    if prev_event and prev_event.miles:
                        miles_driven = event.miles - prev_event.miles
                    elif vehicle.starting_mileage:
                        miles_driven = event.miles - vehicle.starting_mileage
                    else:
                        miles_driven = event.miles
                    
                    if miles_driven > 0:
                        old_mpg = event.milespergallon
                        new_mpg = round(miles_driven / event.gallons, 2)
                        event.milespergallon = new_mpg
                        event.save(update_fields=['milespergallon'])
                        
                        self.stdout.write(f'  Updated {event.date}: MPG {old_mpg or "None"} → {new_mpg}')
                        updated_count += 1
                    else:
                        self.stdout.write(f'  Skipping event {event.date}: invalid miles driven ({miles_driven})')
                        skipped_count += 1
                
                elif vehicle.type in ['boat', 'other']:
                    # For boats/other, check if we need to migrate miles to hours
                    if not event.hours and event.miles:
                        self.stdout.write(f'  Migrating miles to hours for {event.date}: {event.miles} miles → {event.miles} hours')
                        event.hours = event.miles
                        event.miles = None  # Clear miles for boats
                        event.save(update_fields=['hours', 'miles'])
                    
                    # Recalculate GPH for boats/other
                    if not event.hours:
                        self.stdout.write(f'  Skipping event {event.date}: no hours data')
                        skipped_count += 1
                        continue
                    
                    # Find previous gas event
                    prev_event = gas_events.filter(date__lt=event.date).last()
                    
                    # Calculate hours run
                    if prev_event and prev_event.hours:
                        hours_run = event.hours - prev_event.hours
                    else:
                        # For first fill-up, we can't calculate consumption without a baseline
                        self.stdout.write(f'  Skipping event {event.date}: first fill-up, no baseline hours')
                        skipped_count += 1
                        continue
                    
                    if hours_run > 0:
                        old_gph = event.gallonsperhour
                        new_gph = round(event.gallons / hours_run, 2)
                        event.gallonsperhour = new_gph
                        event.save(update_fields=['gallonsperhour'])
                        
                        self.stdout.write(f'  Updated {event.date}: GPH {old_gph or "None"} → {new_gph}')
                        updated_count += 1
                    else:
                        self.stdout.write(f'  Skipping event {event.date}: invalid hours run ({hours_run})')
                        skipped_count += 1
            
            self.stdout.write(f'  Vehicle summary: {updated_count} updated, {skipped_count} skipped')
            total_updated += updated_count
            total_skipped += skipped_count
        
        self.stdout.write(self.style.SUCCESS(
            f'\nRecalculation complete: {total_updated} events updated, {total_skipped} events skipped'
        ))
        
        if total_skipped > 0:
            self.stdout.write(self.style.WARNING(
                'Skipped events may be missing required data (miles for cars, hours for boats, or gallons)'
            ))