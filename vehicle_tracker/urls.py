# vehicle_tracker/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.storage import staticfiles_storage
from django.views.generic import RedirectView,TemplateView
from django.http import HttpResponse
from tracker.views import service_worker  

def health_check(request):
    """Simple health check endpoint for Docker healthcheck"""
    return HttpResponse("OK")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('tracker.urls')),  # Include the app's URLs
    
    # Add these if you want to use Django's built-in auth views with your custom templates
    path('accounts/', include('django.contrib.auth.urls')),
    
    path('service-worker.js', service_worker, name='service_worker'),
    path('offline.html', TemplateView.as_view(template_name='offline.html')),
    path('manifest.json', RedirectView.as_view(url=staticfiles_storage.url('manifest.json'))),
    
    # Health check endpoint
    path('health/', health_check, name='health_check'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)