"""The user menu of the top bar, with entries a project registers.

A menu widget (:func:`djgentelella.menu.register_menu_widget`) named
``gt-user-menu``: a global ``MenuItem`` of the ``main`` category draws it::

    MenuItem.objects.create(
        key='gt-user-menu', title='User', category='main', is_widget=True,
        url_name='gt-user-menu', icon='fa fa-user', position=110)

Its dropdown lists the entries of :func:`user_menu_entries`. djgentelella
registers three: ``push`` (the push notifications of this browser, ``/pwa/
push/``), ``feedback`` (the feedback inbox, for its reviewers) and ``logout``
(a POST). A project adds its own (a profile, the applications of the user...)
with :func:`register_user_menu_entry`, replaces one by registering its key
again, or drops one with :func:`unregister_user_menu_entry` -- from an
``AppConfig.ready()`` or a ``menu_widgets`` module of its app::

    register_user_menu_entry('profile', _('My profile'), 'profile',
                             icon='fa fa-id-card', position=50)
"""

import threading
from dataclasses import dataclass

from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _

from djgentelella.feedback.conf import feedback_enabled, is_feedback_reviewer
from djgentelella.menu import register_menu_widget
from djgentelella.pwa import conf as pwa_conf
from djgentelella.pwa.push import push_enabled

__all__ = ['USER_MENU_WIDGET', 'UserMenu', 'UserMenuEntry',
           'register_user_menu_entry', 'registered_user_menu_entries',
           'unregister_user_menu_entry', 'user_menu_entries']

#: The ``url_name`` of the menu item that draws the user menu.
USER_MENU_WIDGET = 'gt-user-menu'

METHODS = ('get', 'post')


@dataclass(frozen=True)
class UserMenuEntry:
    """One entry of the user menu.

    ``url`` is a URL name (reversed without arguments), a path or an absolute
    URL, or a callable ``(request) -> str``; an entry whose URL name does not
    reverse, or whose callable returns nothing, is left out. ``visible`` is
    ``(request) -> bool`` (always, by default). ``method='post'`` draws a
    form with the CSRF token instead of a link (a logout). ``divider`` puts a
    line before the entry. Entries are sorted by ``position``, then ``key``.
    """

    key: str
    title: object
    url: object
    icon: str = ''
    position: int = 100
    visible: object = None
    method: str = 'get'
    divider: bool = False


_entries = {}
_lock = threading.Lock()


def register_user_menu_entry(key, title, url, *, icon='', position=100,
                             visible=None, method='get', divider=False):
    """Add the entry ``key`` to the user menu (or replace the one with that
    key); returns the :class:`UserMenuEntry`."""
    if not isinstance(key, str) or not key:
        raise ValueError('A user menu entry needs a key, not %r' % (key,))
    if method not in METHODS:
        raise ValueError('The method of user menu entry %r is one of %s, not %r'
                         % (key, ', '.join(METHODS), method))
    if visible is not None and not callable(visible):
        raise ValueError('visible of user menu entry %r is a callable' % (key,))
    entry = UserMenuEntry(key, title, url, icon, position, visible, method, divider)
    with _lock:
        _entries[key] = entry
    return entry


def unregister_user_menu_entry(key):
    """Remove the entry ``key``; nothing when there is none."""
    with _lock:
        _entries.pop(key, None)


def registered_user_menu_entries():
    """``{key: UserMenuEntry}``, sorted by position."""
    with _lock:
        found = list(_entries.values())
    found.sort(key=lambda entry: (entry.position, entry.key))
    return {entry.key: entry for entry in found}


def _url(entry, request):
    if callable(entry.url):
        return entry.url(request) or ''
    url = str(entry.url or '')
    if not url or url.startswith('/') or '://' in url:
        return url
    try:
        return reverse(url)
    except NoReverseMatch:
        return ''


def user_menu_entries(request):
    """The entries ``request`` sees, as dicts ``{key, id, title, url, icon,
    method, divider}`` in order: none for an anonymous user."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return []
    result = []
    for entry in registered_user_menu_entries().values():
        if entry.visible is not None and not entry.visible(request):
            continue
        url = _url(entry, request)
        if not url:
            continue
        result.append({'key': entry.key, 'id': 'gt-user-%s' % entry.key,
                       'title': entry.title, 'url': url, 'icon': entry.icon,
                       'method': entry.method, 'divider': entry.divider})
    return result


@register_menu_widget(name=USER_MENU_WIDGET)
class UserMenu:
    """The menu widget: the user's name and the dropdown of their entries."""

    template_name = 'gentelella/menu/user_menu.html'

    def __init__(self, context):
        self.context = context

    def get_request(self):
        context = self.context.get('context')
        return context.get('request') if context is not None else None

    def render(self):
        request = self.get_request()
        entries = user_menu_entries(request)
        if not entries:
            return ''
        return render_to_string(self.template_name, {
            'id': self.context['id'], 'item': self.context['item'],
            'entries': entries, 'user': request.user,
        }, request=request)

    def render_content(self):
        return ''


# -- djgentelella's entries ------------------------------------------------------------

def _push_visible(request):
    return pwa_conf.manifest_enabled() or pwa_conf.service_worker_enabled() or \
        push_enabled()


def _feedback_visible(request):
    return feedback_enabled(request) and is_feedback_reviewer(request)


register_user_menu_entry('push', _('Push notifications'), 'gt_push_preferences',
                         icon='fa fa-bell', position=100, visible=_push_visible)
register_user_menu_entry('feedback', _('Feedback'), 'gt_feedback_inbox',
                         icon='fa fa-comments', position=200,
                         visible=_feedback_visible)
register_user_menu_entry('logout', _('Log out'), 'logout', icon='fa fa-sign-out',
                         position=1000, method='post', divider=True)
