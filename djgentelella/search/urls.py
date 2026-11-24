from django.urls import path

from . import views

urlpatterns = [
    path('search/', views.search_page, name='gt-search'),
    path('gtapis/search/', views.search_api, name='gt-search-api'),
]
