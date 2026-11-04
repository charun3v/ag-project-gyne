"""
URL configuration for gynae_oncology project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('patients/', include('patients.urls')),
    path('clinical/', include('clinical.urls')),
    path('investigations/', include('investigations.urls')),
    path('radiotherapy/', include('radiotherapy.urls')),
    path('systemic/', include('systemic.urls')),
    path('followup/', include('followup.urls')),
    path('documents/', include('documents.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
