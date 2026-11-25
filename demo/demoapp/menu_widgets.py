"""Menu widgets of the demo.

A class defined in the ``menu_widgets`` module of an installed app is a menu
widget without registering it (:mod:`djgentelella.menu`): a ``MenuItem`` with
``is_widget=True`` names it by its dotted path::

    MenuItem.objects.create(title='User', category='main', is_widget=True,
                            url_name='demoapp.menu_widgets.UserBadgeMenu')
"""
from django.utils.html import format_html


class UserBadgeMenu:
    """The name of the signed-in user, as an entry of the top bar."""

    def __init__(self, context):
        self.context = context

    def render(self):
        request = self.context['context'].get('request')
        user = getattr(request, 'user', None)
        name = user.get_username() if user is not None and \
            user.is_authenticated else ''
        return format_html('<span class="nav-link gt-user-badge">{}</span>', name)

    def render_content(self):
        # render_external_widget falls back to render() without it.
        return ''
