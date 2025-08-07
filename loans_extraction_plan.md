# Plan for Extracting Loans App to Standalone Django Project

## Overview
This document outlines the steps to extract the loans app from TripTrack into its own standalone Django project called LoansManager.

## Step-by-Step Instructions

### 1. Create New Django Project Structure
```bash
cd /Users/davidhale87/Coding
django-admin startproject LoansManager
cd LoansManager
```

### 2. Copy Loans App
```bash
cp -r ../TripTrack/loans .
```

### 3. Handle the Family Model Dependency
The loans app currently depends on `tracker.Family`. Choose one of these options:

#### Option A: Create a Minimal Family Model (Recommended for quick start)
Create a simplified version of the Family model in the new project.

#### Option B: Remove Family Relationship
Replace the family relationship with a simple user relationship.

#### Option C: API Integration
Create an API integration between TripTrack and LoansManager.

### 4. Create Requirements File
Create `requirements.txt` with the following content:
```
Django>=4.2
django-crispy-forms
crispy-bootstrap5
python-dotenv
dj-database-url
psycopg2-binary
redis
```

### 5. Update Settings.py
Add the following to `LoansManager/settings.py`:
```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'crispy_forms',
    'crispy_bootstrap5',
    
    # Local apps
    'loans',
]

# Crispy Forms settings
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
```

### 6. Create Minimal Family Model (if choosing Option A)
Create a new app called `core`:
```bash
python manage.py startapp core
```

Add to `core/models.py`:
```python
from django.db import models
from django.contrib.auth.models import User

class Family(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    members = models.ManyToManyField(User, related_name='families')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Families"
    
    def __str__(self):
        return self.name
```

Don't forget to add 'core' to INSTALLED_APPS in settings.py.

### 7. Update Loans Models
In `loans/models.py`, update the ForeignKey references:
```python
# Change all occurrences of:
family = models.ForeignKey('tracker.Family', ...)

# To:
family = models.ForeignKey('core.Family', ...)
```

### 8. Update URLs
Create or update `LoansManager/urls.py`:
```python
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/loans/', permanent=False)),
    path('loans/', include('loans.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]
```

### 9. Create New Migrations
```bash
# Remove old migrations
rm -rf loans/migrations/

# Create new migrations
python manage.py makemigrations core
python manage.py makemigrations loans
python manage.py migrate
```

### 10. Copy Static Files and Templates
Copy necessary files from TripTrack:
```bash
# Copy static files
cp -r ../TripTrack/static .

# Create templates directory
mkdir -p templates/registration

# Copy base templates
cp ../TripTrack/templates/registration/login.html templates/registration/
cp ../TripTrack/templates/registration/register.html templates/registration/
```

Create a base template at `templates/base.html` that the loans templates can extend.

### 11. Environment Configuration
Create a `.env` file:
```
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://user:password@localhost:5432/loansmanager_db
```

### 12. Update Loans Templates
Update the base template references in all loans templates from:
```django
{% extends "tracker/base.html" %}
```
To:
```django
{% extends "base.html" %}
```

### 13. Create Superuser and Test
```bash
python manage.py createsuperuser
python manage.py runserver
```

### 14. Remove Loans from TripTrack
After confirming the new project works:

1. Update `vehicle_tracker/settings.py`:
   - Remove 'loans' from INSTALLED_APPS

2. Update `vehicle_tracker/urls.py`:
   - Remove the line: `path('loans/', include('loans.urls')),`

3. Delete the loans directory from TripTrack:
   ```bash
   rm -rf loans/
   ```

4. Consider adding a link in TripTrack to redirect users to the new LoansManager application.

## Additional Considerations

### Data Migration
If you have existing loan data in TripTrack:
1. Use Django's dumpdata to export loans data
2. Modify the JSON to match the new model structure
3. Use loaddata to import into LoansManager

```bash
# In TripTrack:
python manage.py dumpdata loans --indent 2 > loans_data.json

# In LoansManager (after adjusting the JSON):
python manage.py loaddata loans_data.json
```

### Authentication Integration
Consider implementing:
- Single Sign-On (SSO) between TripTrack and LoansManager
- Shared authentication backend
- JWT tokens for API communication

### Deployment
- Set up separate deployment pipeline for LoansManager
- Configure nginx/Apache to route traffic appropriately
- Update DNS if using subdomains (e.g., loans.yourdomain.com)

## Troubleshooting

### Common Issues
1. **Import errors**: Make sure all imports are updated from 'tracker' to 'core'
2. **Template not found**: Ensure all template paths are updated
3. **Static files not loading**: Run `python manage.py collectstatic`
4. **Migration conflicts**: Clear migrations and recreate from scratch

### Testing Checklist
- [ ] User registration and login work
- [ ] Loan creation and editing work
- [ ] Payment tracking functions correctly
- [ ] Investment features work
- [ ] All calculators function properly
- [ ] Admin interface is accessible
- [ ] Static files load correctly
- [ ] All templates render without errors