"""demo URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from djgentelella.urls import urlpatterns as djgentelellaurls
from .dashboad import show_top_counts
from .views import home, logeado, add_view_select, color_widget_test
from demoapp.urls import  urlpatterns as demourls

app_name = 'demo'
urlpatterns = djgentelellaurls + [
    path('admin/', admin.site.urls),
    path('', color_widget_test, name="color-widget-test"),
    path('logueado', logeado),
    path('dashboard', show_top_counts, name='dashboard'),
    path('add_view_select', add_view_select, name='add_view_select')
] + demourls
