"""URLconf of ``settings_minimal``: what a project wiring djgentelella would have."""
from django.apps import apps
from django.contrib import admin
from django.urls import include, path

urlpatterns = [path('admin/', admin.site.urls)]

if apps.is_installed('djgentelella'):
    # designs/flows/datasources hook themselves into djgentelella.urls.
    from djgentelella.urls import urlpatterns as gt_urls  # noqa: PLC0415 -- optional
    urlpatterns = gt_urls + urlpatterns
if apps.is_installed('djgentelella.blog'):
    urlpatterns.append(path('blog/', include('djgentelella.blog.urls')))
if apps.is_installed('djgentelella.async_notification'):
    urlpatterns.append(path('async_notification/',
                            include('djgentelella.async_notification.urls')))
