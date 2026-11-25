"""Menu widgets of the demo.

A class defined in the ``menu_widgets`` module of an installed app is a menu
widget without registering it (:mod:`djgentelella.menu`): a ``MenuItem`` with
``is_widget=True`` names it by its dotted path::

    MenuItem.objects.create(title='User', category='main', is_widget=True,
                            url_name='demoapp.menu_widgets.UserBadgeMenu')
"""
from django.conf import settings
from django.middleware.csrf import get_token
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import get_language


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


class LanguageMenu:
    """The languages of the demo as a small form in the top bar: it posts to
    ``set_language``, which keeps the choice in a cookie
    (``demoapp.middleware.LanguageCookieMiddleware``)."""

    def __init__(self, context):
        self.context = context

    def render(self):
        request = self.context['context'].get('request')
        current = get_language()
        buttons = format_html_join(
            '', '<button type="submit" name="language" value="{}" class="btn btn-sm '
            '{}" lang="{}" aria-pressed="{}">{}</button>',
            ((code, 'btn-primary' if code == current else 'btn-outline-secondary',
              code, 'true' if code == current else 'false', code.upper())
             for code, _name in settings.LANGUAGES))
        return format_html(
            '<form class="nav-link gt-language-menu d-inline-flex gap-1" method="post" '
            'action="{}"><input type="hidden" name="csrfmiddlewaretoken" value="{}">'
            '<input type="hidden" name="next" value="{}">{}</form>',
            reverse('set_language'), get_token(request) if request else '',
            request.get_full_path() if request else '/', buttons)

    def render_content(self):
        return ''
