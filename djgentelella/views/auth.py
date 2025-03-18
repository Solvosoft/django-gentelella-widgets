from django.contrib.auth.views import LoginView, LogoutView


class GentelellaLoginView(LoginView):
    template_name = 'gentelella/registration/login.html'


class GentelellaLogoutView(LogoutView):
    http_method_names = ["get", "post", "options"]
    template_name = "gentelella/registration/logout.html"
