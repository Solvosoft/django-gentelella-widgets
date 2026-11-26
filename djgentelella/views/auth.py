from django.contrib.auth.views import LoginView, LogoutView


class GentelellaLoginView(LoginView):
    #: Public (:func:`djgentelella.public.is_public_view`).
    gt_public = True
    template_name = 'gentelella/registration/login.html'


class GentelellaLogoutView(LogoutView):
    gt_public = True
    http_method_names = ['get', 'post', 'options']
    template_name = 'gentelella/registration/logout.html'
