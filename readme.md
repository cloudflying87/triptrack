# TripTracker

A Django-based application for tracking vehicle maintenance, gas fill-ups, outings, and more.

## Overview

TripTracker is a comprehensive vehicle management system that helps users track various aspects of their vehicles, including:

- Maintenance records
- Gas fill-ups and mileage tracking
- Outings and trips
- To-do items for vehicle care
- Scheduled maintenance

The application supports multiple vehicle types (cars, boats, etc.) and uses appropriate measurements for each (miles for cars, hours for boats).

## Features

- **Multi-Vehicle Support**: Track multiple vehicles of different types
- **Maintenance Tracking**: Log maintenance activities with dates, costs, and categories
- **Fuel Tracking**: Record gas fill-ups and automatically calculate fuel efficiency
- **Trip Logging**: Document outings with locations, distances, and notes
- **To-Do Management**: Create and share vehicle-related tasks
- **Maintenance Scheduling**: Set up recurring maintenance schedules with reminders
- **Reports**: Generate detailed reports for each vehicle
- **Data Export**: Export data in CSV format
- **Responsive Design**: Mobile-friendly interface that works on any device
- **PWA Support**: Progressive Web App capabilities for offline access
- **User Authentication**: Secure login and registration system

## Technical Details

### Tech Stack

- **Backend**: Django 5.2 with PostgreSQL database
- **Frontend**: HTML, CSS, JavaScript with Bootstrap 5
- **Caching**: Redis for improved performance
- **Deployment**: Docker containers with Cloudflared tunneling
- **Additional Libraries**:
  - django-crispy-forms for enhanced form rendering
  - django-imagekit for image processing
  - djangorestframework for API endpoints
  - whitenoise for static file serving

### Project Structure

```
triptracker/
├── .env                   # Environment variables
├── .gitignore             # Git ignore file
├── README.md              # Project documentation
├── backups/               # Directory for database backups
├── docker-compose.yml     # Docker Compose configuration
├── Dockerfile             # Docker build instructions
├── logs/                  # Directory for log files
├── manage.py              # Django management script
├── media/                 # User-uploaded files
│   └── vehicle_images/    # Vehicle images storage
├── requirements.txt       # Python dependencies
├── static/                # Static files
│   ├── css/
│   ├── js/
│   └── images/
├── templates/             # Project-level templates
│   └── registration/      # Authentication templates
├── vehicle_tracker/       # Project package
│   ├── settings.py        # Project settings
│   ├── urls.py            # Project URL routing
│   └── wsgi.py            # WSGI configuration
└── tracker/               # Main application
    ├── admin.py           # Admin configuration
    ├── forms.py           # Form definitions
    ├── models.py          # Data models
    ├── serializers.py     # API serializers
    ├── templates/         # App-specific templates
    ├── urls.py            # App URL routing
    └── views.py           # View functions
```

## Installation

### Development Environment

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/triptracker.git
   cd triptracker
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env file with your settings
   ```

5. Run migrations:
   ```bash
   python manage.py migrate
   ```

6. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```

7. Start the development server:
   ```bash
   python manage.py runserver
   ```

### Production Deployment

1. Set up environment variables:
   ```bash
   # Configure your .env file with production settings
   ```

2. Deploy with Docker:
   ```bash
   docker-compose up -d
   ```

3. Create a superuser:
   ```bash
   docker-compose exec triptracker python manage.py createsuperuser
   ```

## Usage

1. Log in to the application
2. Add vehicles to your profile
3. Start tracking maintenance, gas fill-ups, and trips
4. Set up maintenance schedules
5. Create to-do items for vehicle care
6. Generate reports for analysis

## API Endpoints

TripTracker includes a REST API for integration with other services:

- `/api/vehicles/` - Vehicle management
- `/api/trips/` - Trip/event management
- `/api/todos/` - To-do item management

## Roadmap

- Mobile application integration
- Email notifications for maintenance due
- Import data from other tracking systems
- Integration with OBD-II devices for real-time vehicle data
- Advanced reporting and analytics

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.