from chunked_upload.views import ChunkedUploadView, ChunkedUploadCompleteView
from django.conf.urls import url
from django.urls import path, include
from django.contrib.auth import views as auth_views

from djgentelella.notification.base import NotificacionAPIView, NotificationList
from djgentelella.widgets.helper import HelperWidgetView

auth_urls = [
    path('accounts/login/',
         auth_views.LoginView.as_view(template_name='gentelella/registration/login.html'),
         name="login"),
    path('accounts/logout/', auth_views.LogoutView.as_view(template_name='gentelella/registration/logout.html'),
         name='logout'),
    path('accounts/password_change/',
        auth_views.PasswordChangeView.as_view(
            template_name='gentelella/registration/change-password.html',
            ), name="password_change"  ),
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name = 'gentelella/registration/password_change_done.html'), name='password_change_done'),
    path('accounts/password_reset/',
         auth_views.PasswordResetView.as_view(
             email_template_name='gentelella/registration/password_reset_email.html',
             subject_template_name='gentelella/registration/password_reset_subject.txt',
             html_email_template_name='gentelella/registration/password_reset_email.html',
             template_name='gentelella/registration/password_reset_form.html',
         ), name="password_reset"),
    path('accounts/password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name = 'gentelella/registration/password_reset_done.html'),
         name="password_reset_done"
         ),
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
            template_name = 'gentelella/registration/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name = 'gentelella/registration/password_reset_done.html'
    ), name="password_reset_complete")
]

from .groute import routes
from django.conf import settings
for x in settings.INSTALLED_APPS:
    try:
        __import__(x+'.gtselects')
    except:
        pass

base_urlpatterns = [
    url('gtselects/', include(routes.urls)),
    path('djgentelella/upload/', ChunkedUploadView.as_view(), name='upload_file_view'),
    path('djgentelella/upload/done/', ChunkedUploadCompleteView.as_view(), name='upload_file_done'),
    url('help/(?P<pk>\d+)?', HelperWidgetView.as_view({'get': 'list', 'post': 'create', 'put': 'update', 'delete': 'destroy'}),
        name='help'),
    url('^notification/(?P<pk>\d+)?$', NotificacionAPIView.as_view({'get': 'list', 'put': 'update', 'delete': 'destroy'}),
        name="notifications"),
    url('^notification/list/$', NotificationList.as_view(), name="notification_list")
]

urlpatterns = auth_urls + base_urlpatterns