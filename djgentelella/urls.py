from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import path, include, re_path
from django.views.decorators.cache import cache_page
from django.views.i18n import JavaScriptCatalog
from rest_framework.routers import DefaultRouter

from djgentelella.chunked_upload.views import ChunkedUploadView, \
    ChunkedUploadCompleteView
from djgentelella.notification.base import NotificacionAPIView, NotificationViewSet, \
    notification_list_view
from djgentelella.permission_management import views as permissions
from djgentelella.widgets.helper import HelperWidgetView
from djgentelella.wysiwyg import views as wysiwyg
from djgentelella.firmador_digital import views as firmador_digital
from .groute import routes
from .templatetags.gtsettings import get_version
from .views import auth

auth_urls = [
    path('accounts/login/', auth.GentelellaLoginView.as_view(), name="login"),
    path('accounts/logout/', auth.GentelellaLogoutView.as_view(), name='logout'),
    path('accounts/password_change/',
         auth_views.PasswordChangeView.as_view(
             template_name='gentelella/registration/change-password.html',
         ), name="password_change"),
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='gentelella/registration/password_change_done.html'),
         name='password_change_done'),
    path('accounts/password_reset/',
         auth_views.PasswordResetView.as_view(
             email_template_name='gentelella/registration/password_reset_email.html',
             subject_template_name='gentelella/registration/password_reset_subject.txt',
             html_email_template_name='gentelella/registration/' +
                                      'password_reset_email.html',
             template_name='gentelella/registration/password_reset_form.html',
         ), name="password_reset"),
    path('accounts/password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='gentelella/registration/password_reset_done.html'),
         name="password_reset_done"
         ),
    path('accounts/reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='gentelella/registration/password_reset_confirm.html'
         ), name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='gentelella/registration/reset_done.html'
    ), name="password_reset_complete")
]
wysiwyg_urls = [
    re_path("^u_image$", login_required(wysiwyg.image_upload),
            name="tinymce_upload_image"),
    re_path("^u_video$", login_required(wysiwyg.video_upload),
            name="tinymce_upload_video"),
]


def import_module_app_gt(app, name):
    try:
        __import__(app + '.' + name)
    except ModuleNotFoundError as e:
        pass


for app in settings.INSTALLED_APPS:
    import_module_app_gt(app, 'gtcharts')
    import_module_app_gt(app, 'gtselects')
    import_module_app_gt(app, 'gttimeline')
    import_module_app_gt(app, 'gtstorymap')
    import_module_app_gt(app, 'gtstoryline')

router = DefaultRouter()
router.register('notificationtableview', NotificationViewSet, 'api-notificationtable')

base_urlpatterns = [
    re_path('gtapis/', include(routes.urls)),
    path('djgentelella/upload/', ChunkedUploadView.as_view(),
         name='upload_file_view'),
    path('djgentelella/upload/done/',
         ChunkedUploadCompleteView.as_view(), name='upload_file_done'),
    re_path(r'help/(?P<pk>\d+)?', HelperWidgetView.as_view(
        {'get': 'list', 'post': 'create', 'put': 'update', 'delete': 'destroy'}),
            name='help'),
    re_path(r'^notification/(?P<pk>\d+)?$', NotificacionAPIView.as_view(
        {'get': 'list', 'put': 'update', 'delete': 'destroy'}),
            name="notifications"),
    re_path('^notification/list/$', notification_list_view,
            name="notification_list"),
    path('tableapi/', include(router.urls)),
    path("update_config/", firmador_digital.update_signature_settings, name="signature_config"),
]

permission_management_urls = [
    path('permissionsmanagement/<int:pk>', permissions.get_permissions,
         name="permission_view_list"),
    path('permissionsmanagement/list', permissions.get_permission_list,
         name="permissionsmanagement-list"),
    path('permissionsmanagement/save', permissions.save_permcategorymanagement,
         name="permcategorymanagement-save"),

]

urlpatterns = auth_urls + base_urlpatterns + wysiwyg_urls + permission_management_urls

if settings.DEBUG:
    urlpatterns += [
        path('djsi18n/', JavaScriptCatalog.as_view(), name='djgentelella-js-catalog'),
    ]
else:
    urlpatterns += [
        path('djsi18n/',
             cache_page(86400, key_prefix='djsi18n-%s' % get_version())(
                 JavaScriptCatalog.as_view()),
             name='djgentelella-js-catalog'),
    ]
