from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import  translation
from django.templatetags import static

class NotificationMenu:
    def __init__(self, context):
        self.context = context

    def render(self):
        api_url = self.context['item'].reversed_args
        view_url = self.context['item'].reversed_kwargs
        if api_url is None:
            api_url = reverse('notifications')
        if view_url is None:
            view_url = reverse('notifications')
        self.context['api_url'] = api_url
        self.context['view_url'] = view_url
        self.context['lang_code'] = translation.get_language()
        return render_to_string('gentelella/menu/notificacion.html', context=self.context)

    def render_js(self):
        data = {'js_script': static.static('gentelella/js/notifications.js')}
        return """
         <script src="%(js_script)s"> </script>
        """%data

    def render_content(self):
        return ""