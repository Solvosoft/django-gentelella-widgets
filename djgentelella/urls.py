from django.urls import path
from django.contrib.auth import views as auth_views

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
    ) ,name="password_reset_complete")
]

urlpatterns =   auth_urls + [
]