from django.urls import path

from djgentelella.feedback import views

urlpatterns = [
    path('gt-feedback/send/', views.feedback_create, name='gt_feedback_create'),
    path('gt-feedback/', views.feedback_inbox, name='gt_feedback_inbox'),
    path('gt-feedback/<int:pk>/', views.feedback_detail, name='gt_feedback_detail'),
]
