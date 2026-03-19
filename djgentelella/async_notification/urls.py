from django.urls import path, include
from rest_framework.routers import DefaultRouter

from djgentelella.async_notification.views import (
    EmailNotificationManagement, EmailTemplateManagement,
    NewsLetterTemplateManagement, NewsLetterManagement,
    NewsLetterTaskManagement,
    email_notification_view, email_template_view,
    newsletter_view, newsletter_template_view, newsletter_task_view,
    email_autocomplete_view, model_fields_view,
    upload_image_view, upload_video_view,
    preview_file_view, reassociate_files_view, preview_template_view,
)

app_name = 'async_notification'

router = DefaultRouter()
router.register(
    'email_notification', EmailNotificationManagement,
    basename='api-emailnotification')
router.register(
    'email_template', EmailTemplateManagement,
    basename='api-emailtemplate')
router.register(
    'newsletter_template', NewsLetterTemplateManagement,
    basename='api-newslettertemplate')
router.register(
    'newsletter', NewsLetterManagement,
    basename='api-newsletter')
router.register(
    'newsletter_task', NewsLetterTaskManagement,
    basename='api-newslettertask')

urlpatterns = [
    # API
    path('objapi/', include(router.urls)),

    # HTML views
    path('email-notifications/',
         email_notification_view, name='email_notification'),
    path('email-templates/',
         email_template_view, name='email_template'),
    path('newsletters/',
         newsletter_view, name='newsletter'),
    path('newsletter-templates/',
         newsletter_template_view, name='newsletter_template'),
    path('newsletter-tasks/',
         newsletter_task_view, name='newsletter_task'),

    # Auxiliary endpoints
    path('autocomplete/',
         email_autocomplete_view, name='email_autocomplete'),
    path('model-fields/',
         model_fields_view, name='model_fields'),
    path('upload-image/',
         upload_image_view, name='async_upload_image'),
    path('upload-video/',
         upload_video_view, name='async_upload_video'),
    path('preview-file/<int:pk>/',
         preview_file_view, name='preview_file'),
    path('reassociate-files/',
         reassociate_files_view, name='reassociate_files'),
    path('preview-template/',
         preview_template_view, name='preview_template'),
]
