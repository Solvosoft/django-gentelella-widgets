from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import  translation
from django.templatetags import static

class NotificationMenu:
    """
    This widget help to create a notification on menú, was tested only on top nav

    .. code:: python

        MenuItem.objects.create(
            parent = None,
            title = 'top_navigation',
            url_name ='djgentelella.notification.widgets.NotificationMenu',
            category = 'main',
            is_reversed = False,
            reversed_kwargs = None,
            reversed_args = reverse('notifications'),
            is_widget = True,
            icon = 'fa fa-envelope',
            only_icon = False
        )

    The follow arguments has a special behaivior

    - `reversed_args`: allow you to set custom URL for notification management API
    - `reversed_kwargs`: allow you to set custom URL for notification list

    You can set both as None to use default values.
    """
    def __init__(self, context):
        self.context = context

    def render(self):
        api_url = self.context['item'].reversed_args
        view_url = self.context['item'].reversed_kwargs
        if api_url is None:
            api_url = reverse('notifications')
        if view_url is None:
            view_url = reverse('notification_list')
        self.context['api_url'] = api_url
        self.context['view_url'] = view_url
        self.context['lang_code'] = translation.get_language()
        return render_to_string('gentelella/menu/notificacion.html', context=self.context)

    def render_js(self):
        return """<script > $('.notificationmenu').notificationWidget(); </script>"""

    def render_content(self):
        return ""