from django.urls import path

from djgentelella.theme import views

urlpatterns = [
    path('gt-theme/<int:pk>.css', views.theme_css, name='gt_theme_css'),
    path('gt-theme/<int:pk>/logo', views.theme_logo, name='gt_theme_logo'),
    path('gt-theme/', views.theme_roller, name='gt_theme_roller'),
    path('gt-theme/preview.css', views.theme_preview, name='gt_theme_preview'),
]
