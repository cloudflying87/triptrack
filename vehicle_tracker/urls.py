# vehicle_tracker/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from tracker import views  # Import your views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('tracker.urls')),  # Include the app's URLs
    
    # Add these if you want to use Django's built-in auth views with your custom templates
    path('accounts/', include('django.contrib.auth.urls')),
    path('debug-templates/', views.debug_templates, name='debug_templates'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)