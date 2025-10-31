# TripTrack - Django Project Consolidation Analysis

## PROJECT OVERVIEW
- **Project Name**: TripTracker
- **Primary Purpose**: A comprehensive vehicle management system for tracking maintenance, gas fill-ups, outings/trips, to-do items, and scheduled maintenance across multiple vehicles (cars, boats, etc.)
- **Primary Users**: Families and individuals - Uses a family-based access model where users belong to families and share access to vehicles, locations, and tracking data
- **Current Status**: Actively used (based on recent commits and production deployment with Docker/Cloudflared)

## TECHNICAL DETAILS
- **Django Version**: 5.2
- **Python Version**: 3.13.1
- **Database**: PostgreSQL (with dj-database-url for configuration)
- **Key Dependencies**:
  - gunicorn (21.2.0) - Production WSGI server
  - Pillow (11.2.1) - Image processing
  - django-imagekit (5.0.0) - Image optimization
  - django-crispy-forms (2.1) + crispy-bootstrap5 (0.7) - Form rendering
  - djangorestframework (3.15.0) - API endpoints
  - redis (5.0.1) - Caching
  - whitenoise (6.6.0) - Static file serving
  - psycopg2-binary (2.9.10) - PostgreSQL adapter
  - python-dotenv (1.0.0) - Environment variable management
- **Deployment**: Docker containers with Cloudflared tunneling, Redis cache, accessed via https://triptrack.flyhomemnlab.com

## MODELS & DATABASE

### Family
- **Purpose**: Group users together to share access to vehicles and locations
- **Key fields**: name, created_by, members (ManyToMany), created_at
- **Relationships**: ManyToMany with User, OneToMany with Vehicle and Location
- **Records**: Unknown (small scale - family/personal use)

### Vehicle
- **Purpose**: Stores vehicle information (cars, boats, other)
- **Key fields**: name, make, model, year, vin, license_plate, type (car/boat/other), boat_engine_type (inboard/outboard/io), starting_mileage, image
- **Relationships**: ForeignKey to Family, OneToMany with Event/TodoItem/MaintenanceSchedule
- **Records**: Unknown (likely 5-20 vehicles)

### Event
- **Purpose**: Central model for tracking ALL vehicle-related events (maintenance, gas, outings)
- **Key fields**: event_type (maintenance/gas/outing), date, miles, hours, gallons, price_per_gallon, total_cost, milespergallon, gallonsperhour, notes
- **Relationships**: ForeignKey to Vehicle, MaintenanceCategory, Location, created_by (User)
- **Records**: Likely hundreds to thousands
- **Special**: Auto-calculates MPG/GPH on save, updates maintenance schedules

### MaintenanceItem
- **Purpose**: Individual maintenance items within a maintenance event
- **Key fields**: maintenance_category, description, cost, created_at
- **Relationships**: ForeignKey to Event and MaintenanceCategory
- **Records**: Multiple items per maintenance event

### MaintenanceCategory
- **Purpose**: Categorizes types of maintenance (oil change, tire rotation, etc.)
- **Key fields**: name, description, vehicle_types (JSONField), boat_engine_types (JSONField)
- **Relationships**: Referenced by Event and MaintenanceItem
- **Records**: ~20-50 predefined categories

### MaintenanceSchedule
- **Purpose**: Track recurring maintenance schedules with intervals
- **Key fields**: name, description, interval_miles, interval_hours, interval_days, last_performed, last_miles, last_hours, is_active
- **Relationships**: ForeignKey to Vehicle, MaintenanceCategory, created_by
- **Records**: ~5-10 per vehicle

### Location
- **Purpose**: Store frequently visited locations for outings
- **Key fields**: name, address, latitude, longitude
- **Relationships**: ForeignKey to Family and created_by, OneToMany with Event
- **Records**: ~10-50 locations

### TodoItem
- **Purpose**: Track vehicle-related tasks and reminders
- **Key fields**: title, description, completed, due_date, priority (0-2), shared_with (ManyToMany)
- **Relationships**: ForeignKey to Vehicle and created_by, ManyToMany with User (shared_with)
- **Records**: ~10-50 active todos

## FEATURES & FUNCTIONALITY

### Core Tracking Features:
- Multi-vehicle management (supports cars, boats, other types)
- Maintenance event logging with multiple items per event
- Gas fill-up tracking with automatic MPG/GPH calculation
- Outing/trip logging with locations
- Smart field labels (miles vs hours, MPG vs GPH) based on vehicle type

### Maintenance Management:
- Maintenance categories filtered by vehicle type and boat engine type
- Recurring maintenance schedules (by miles, hours, or days)
- Automatic schedule updates when maintenance is performed
- Due maintenance dashboard alerts
- Detailed maintenance items list with search/filtering

### Reporting & Analytics:
- Vehicle detail page with statistics and charts
- Full vehicle reports with monthly/yearly breakdowns
- Usage analytics page with graphs
- Fuel efficiency tracking and charts
- Monthly/yearly cost analysis
- Export to CSV functionality

### Family & Sharing:
- Family-based access control
- Share vehicles and locations within families
- Share todo items with family members
- Multi-user collaboration

### Data Management:
- CSV import for bulk event creation
- CSV export for vehicles, maintenance, and events
- Data deduplication on import

### Additional Features:
- Progressive Web App (PWA) with offline support
- Image uploads for vehicles
- Location tracking with visit counts
- Health check endpoints for monitoring
- Responsive Bootstrap 5 UI
- Landing page for unauthenticated users

## VIEWS & URLS
- **Approximate number of views/pages**: ~50+ views/pages
- **API endpoints**: Yes
  - `/api/vehicles/<id>/` - Vehicle details
  - `/api/vehicle/<id>/events/` - Event data for charts
  - `/api/vehicle/<id>/mileage/` - Mileage/hours data
  - `/api/vehicle/<id>/fuel-efficiency/` - MPG data
  - `/api/maintenance-categories/` - Filtered maintenance categories
  - REST API endpoints for integration
- **Authentication required**: Yes - Most pages require login via LoginRequiredMixin/decorators
  - Public pages: Landing page, login, register
  - Protected: Dashboard, all vehicle/event/family/location CRUD operations

## SHARED/COMMON FUNCTIONALITY

- **User authentication**: ✅ Django built-in auth with custom registration
- **File uploads**: ✅ Vehicle images via django-imagekit (optimized to 800x600 JPEG)
- **Email notifications**: ❌ Not implemented (mentioned in roadmap)
- **Scheduled tasks/cron jobs**: ❌ None currently (maintenance due calculated on-demand)
- **External API integrations**: ❌ None
- **Payment processing**: ❌ Not applicable
- **Caching**: ✅ Redis for performance
- **Static file serving**: ✅ WhiteNoise with compression
- **Image processing**: ✅ Pillow + django-imagekit
- **CSV import/export**: ✅ Custom implementation
- **Health checks**: ✅ Database and Redis monitoring
- **Family/group sharing**: ✅ Custom family-based access control system
- **REST API**: ✅ Django REST Framework for AJAX endpoints

## DATA MIGRATION

- **Critical data to migrate**: YES - This is primary data storage for vehicle tracking
- **Most important models**:
  1. **Family** - Must migrate first (referenced by Vehicle/Location)
  2. **Vehicle** - Core model with image files
  3. **Location** - Frequently reused, family-owned
  4. **MaintenanceCategory** - Predefined categories (may not need migration if recreated)
  5. **Event** - All historical tracking data (maintenance, gas, outings)
  6. **MaintenanceItem** - Detailed maintenance records
  7. **MaintenanceSchedule** - Active schedules with last-performed data
  8. **TodoItem** - Active tasks

- **Data that can be recreated/skipped**:
  - MaintenanceCategory records (can be recreated via management command)
  - Static files/images (can be regenerated)

- **Sensitive/personal data**:
  - Vehicle VINs and license plates
  - Location addresses (may include home addresses)
  - Family member associations
  - Personal notes in events
  - Vehicle images
  - All user-generated content

## UNIQUE/COMPLEX FEATURES

### Complex Auto-calculations:
- Event model has complex save() logic that:
  - Auto-calculates total_cost from gallons × price_per_gallon
  - Calculates MPG for cars by comparing with previous gas event
  - Calculates GPH for boats/other vehicles
  - Automatically updates related MaintenanceSchedule records
  - Requires careful migration to preserve calculation logic

### Vehicle Type Polymorphism:
- Same models support multiple vehicle types (car/boat/other)
- Dynamic field labels and units based on type
- Conditional category filtering by vehicle type AND boat engine type
- Miles vs Hours fields used conditionally
- MPG vs GPH calculations

### Multi-item Maintenance Events:
- Uses Django formsets for dynamic add/remove of maintenance items
- Auto-calculates total cost from individual item costs
- Complex form handling in MaintenanceCreateView and MaintenanceUpdateView

### Smart Maintenance Scheduling:
- `is_due()` method checks multiple criteria (miles, hours, days)
- Automatically updated via Event model signals
- Pre-fills maintenance forms from schedules

### Family-based Access Control:
- Custom `FamilyMemberRequiredMixin` for permissions
- User can belong to multiple families
- Shared access to all family vehicles/locations/events
- Complex queryset filtering throughout views

### Other Notes:
- **Background tasks**: ❌ No Celery or background tasks
- **Real-time features**: ❌ No WebSockets/Channels
- **Third-party integrations**: ❌ None (OBD-II integration mentioned in roadmap)

## POTENTIAL FOR MOBILE APP

- [x] **Location-based features** - Tracks location visits, GPS coordinates stored
- [x] **Push notifications** - Would benefit from maintenance due reminders (not currently implemented)
- [x] **Camera/photo features** - Vehicle image uploads
- [x] **Offline functionality** - Already has PWA support with service worker
- [x] **Quick logging** - Gas fill-ups, outings would be ideal for mobile quick entry
- [x] **Other**:
  - Would greatly benefit from native mobile app
  - Quick event logging while at gas station or after trips
  - Photo capture for maintenance receipts
  - GPS auto-location for outings
  - Push notifications for maintenance due

## NOTES & CONCERNS

### Strengths:
- Well-structured Django app with clear separation of concerns
- Comprehensive feature set for vehicle tracking
- Family sharing model is well-implemented
- Good use of Django best practices (CBVs, mixins, model methods)
- Strong admin interface configuration
- Progressive Web App capabilities

### Potential Migration Challenges:
1. **Event model complexity** - The auto-calculation logic in save() is critical and must be preserved
2. **Family relationships** - Must maintain family memberships and access control
3. **Image files** - Vehicle images need to be migrated from media/ directory
4. **JSONField usage** - vehicle_types and boat_engine_types use JSONField (ensure target DB supports)
5. **Duplicate code** - Some views have duplicate logic (e.g., LocationDeleteView defined twice in views.py:1005-1014)
6. **Database dependencies** - Uses PostgreSQL-specific features and Redis for caching

### Code Quality Notes:
- Views.py is very large (2143 lines) - Could benefit from splitting into multiple files
- Some debug print statements left in code (views.py:219, 231, 232, 243)
- Good test coverage mentioned but tests.py appears minimal
- Management commands exist for data setup (add_maintenance_categories, etc.)

### Integration Considerations:
- Uses Django 5.2 (latest) - Ensure compatibility with consolidated project
- Heavy use of Bootstrap 5 for frontend
- Custom mixins and permission logic that may need adaptation
- REST API is minimal - mostly for AJAX, not full CRUD API
- No conflicts with standard Django auth - uses built-in User model

### Recommended Consolidation Strategy:
1. Rename app from `tracker` to `vehicle_tracker` to avoid naming conflicts
2. Preserve the Family model as core multi-tenancy mechanism
3. Consider refactoring large views.py into view modules
4. Keep separate URL namespace: `/vehicles/` or `/triptracker/`
5. Migrate management commands for initial data setup
6. Consider API expansion if consolidating with other projects that need vehicle data

### Docker/Deployment Notes:
- Currently deployed via Docker with custom entrypoint
- Uses Cloudflared for external access
- Includes database backup scripts
- Health check endpoint for monitoring
- Production-ready with gunicorn + whitenoise

---

## MIGRATION CHECKLIST

### Pre-Migration:
- [ ] Back up production database
- [ ] Export all vehicle images from media/ directory
- [ ] Document current maintenance categories
- [ ] List all active families and their members

### During Migration:
- [ ] Create consolidated project structure
- [ ] Rename `tracker` app to avoid conflicts
- [ ] Migrate models in dependency order (Family → Vehicle → Location → Event → etc.)
- [ ] Migrate vehicle images to new media directory
- [ ] Update all foreign key relationships
- [ ] Run management commands to recreate maintenance categories
- [ ] Test auto-calculation logic in Event model
- [ ] Verify family permissions work correctly

### Post-Migration:
- [ ] Verify all historical data migrated correctly
- [ ] Test MPG/GPH calculations with new events
- [ ] Test maintenance schedule triggers
- [ ] Verify image uploads work
- [ ] Test CSV import/export functionality
- [ ] Check API endpoints still function
- [ ] Verify PWA functionality
- [ ] Load test with production data volume

### Testing Focus Areas:
- [ ] Family-based access control
- [ ] Vehicle type polymorphism (car vs boat behavior)
- [ ] Event auto-calculations
- [ ] Maintenance schedule updates
- [ ] CSV import deduplication
- [ ] Multi-item maintenance formsets
- [ ] Image uploads and optimization
