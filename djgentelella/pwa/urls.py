from django.urls import path

from djgentelella.pwa import views

urlpatterns = [
    path('pwa/manifest.webmanifest', views.manifest_view, name='gt_pwa_manifest'),
    path('pwa/sw.js', views.service_worker_view, name='gt_pwa_service_worker'),
    path('pwa/offline/', views.offline_view, name='gt_pwa_offline'),
    path('pwa/push/', views.preferences_view, name='gt_push_preferences'),
    path('pwa/push/subscribe/', views.subscribe_view, name='gt_push_subscribe'),
    path('pwa/push/unsubscribe/', views.unsubscribe_view,
         name='gt_push_unsubscribe'),
    path('pwa/push/test/', views.test_view, name='gt_push_test'),
]
