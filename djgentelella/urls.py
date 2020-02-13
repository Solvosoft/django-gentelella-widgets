from django.urls import path
from django.contrib.auth import views as auth_views

#from views.auth import testing

"""
accounts/login/ [name='login']
accounts/logout/ [name='logout']
accounts/password_change/ [name='password_change']
accounts/password_change/done/ [name='password_change_done']
accounts/password_reset/ [name='password_reset']
accounts/password_reset/done/ [name='password_reset_done']
accounts/reset/<uidb64>/<token>/ [name='password_reset_confirm']
accounts/reset/done/ [name='password_reset_complete']
"""

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
    path('accounts/password_reset/',
         auth_views.PasswordResetView.as_view(
template_name='gentelella/registration/password_reset_form.html',
         ), name="password_reset"),
]

urlpatterns =   auth_urls + [
]