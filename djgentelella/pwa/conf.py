"""The settings of :mod:`djgentelella.pwa`, read when they are used.

Everything is off by default: a project without these settings gets no
manifest tags, no service worker and no push.
"""
from django.conf import settings
from django.templatetags.static import static

from djgentelella import __version__

#: ``GT_PWA_THEME_COLOR`` / ``GT_PWA_BACKGROUND_COLOR`` by default: the
#: colours of the gentelella sidebar and page.
DEFAULT_THEME_COLOR = '#2A3F54'
DEFAULT_BACKGROUND_COLOR = '#F7F7F7'

#: The icons shipped with djgentelella, used while the Site has none.
DEFAULT_ICONS = (
    ('gentelella/pwa/icon-192.png', '192x192'),
    ('gentelella/pwa/icon-512.png', '512x512'),
)

#: Hosts of the push services of the browsers. A subscription whose endpoint
#: is elsewhere is refused: the server POSTs to that URL, so accepting any
#: would let a user aim the server at an internal host. ``.example`` matches
#: the host and its subdomains.
DEFAULT_PUSH_HOSTS = (
    '.googleapis.com',               # Chrome, Opera (FCM: fcm.googleapis.com)
    '.google.com',                   # Chrome since 2024 (jmt17.google.com)
    '.push.services.mozilla.com',    # Firefox
    '.notify.windows.com',           # Edge (WNS)
    '.push.apple.com',               # Safari
)


def manifest_enabled():
    """``GT_PWA_MANIFEST``: the manifest tags in ``base.html``."""
    return bool(getattr(settings, 'GT_PWA_MANIFEST', False))


def service_worker_enabled():
    """``GT_PWA_SERVICE_WORKER``: every page registers the service worker
    (static cache and offline page)."""
    return bool(getattr(settings, 'GT_PWA_SERVICE_WORKER', False))


def scope():
    """``GT_PWA_SCOPE``: the scope of the service worker and of the app."""
    return getattr(settings, 'GT_PWA_SCOPE', '/')


def cache_version():
    """``GT_PWA_CACHE_VERSION``, else the version of djgentelella.

    It names the static cache: change it and the next service worker drops
    the old cache.
    """
    value = getattr(settings, 'GT_PWA_CACHE_VERSION', None)
    if value:
        return str(value)
    return __version__


def cache_prefixes():
    """URL prefixes the service worker caches: ``STATIC_URL`` and the
    ``GT_PWA_CACHE_URLS`` the project adds on purpose. Pages and APIs are not
    cached."""
    prefixes = [settings.STATIC_URL or '/static/']
    prefixes.extend(getattr(settings, 'GT_PWA_CACHE_URLS', ()))
    return [p if '://' in p or p.startswith('/') else '/' + p for p in prefixes]


def precache():
    """``GT_PWA_PRECACHE``: static paths (or URLs) downloaded on install."""
    return [url if url.startswith('/') or '://' in url else static(url)
            for url in getattr(settings, 'GT_PWA_PRECACHE', ())]


def theme_color():
    return getattr(settings, 'GT_PWA_THEME_COLOR', DEFAULT_THEME_COLOR)


def background_color():
    return getattr(settings, 'GT_PWA_BACKGROUND_COLOR', DEFAULT_BACKGROUND_COLOR)


def display():
    return getattr(settings, 'GT_PWA_DISPLAY', 'standalone')


def push_backend_path():
    return getattr(settings, 'GT_PUSH_BACKEND',
                   'djgentelella.pwa.backends.WebPushBackend')


def vapid_private_key():
    return getattr(settings, 'GT_PUSH_VAPID_PRIVATE_KEY', '') or ''


def vapid_public_key():
    return getattr(settings, 'GT_PUSH_VAPID_PUBLIC_KEY', '') or ''


def vapid_subject():
    """``GT_PUSH_VAPID_SUBJECT``: a ``mailto:`` or ``https:`` the push services
    can contact. ``mailto:`` + ``DEFAULT_FROM_EMAIL`` by default."""
    value = getattr(settings, 'GT_PUSH_VAPID_SUBJECT', '')
    if value:
        return value
    return 'mailto:%s' % getattr(settings, 'DEFAULT_FROM_EMAIL', 'webmaster@localhost')


def push_ttl():
    """``GT_PUSH_TTL``: seconds the push service keeps a message for an
    offline browser (one day by default)."""
    return int(getattr(settings, 'GT_PUSH_TTL', 86400))


def push_timeout():
    """``GT_PUSH_TIMEOUT``: seconds to wait for the push service."""
    return float(getattr(settings, 'GT_PUSH_TIMEOUT', 5))


def push_queue():
    """``GT_PUSH_QUEUE``: how a new notification goes out as push.
    ``'sync'`` (the default) sends it after the commit, in the process that
    saved it; ``'celery'`` queues it as the Celery task
    ``djgentelella.pwa.tasks.push_notification_task``; ``'auto'`` queues it
    when ``djgentelella.async_notification`` would (the ``celery`` extra and
    ``CELERY_BROKER_URL``), else sends it."""
    return getattr(settings, 'GT_PUSH_QUEUE', 'sync') or 'sync'


def unsubscribe_on_logout():
    """``GT_PUSH_UNSUBSCRIBE_ON_LOGOUT``: logging out forgets the push
    subscriptions this browser registered in the session (default False)."""
    return bool(getattr(settings, 'GT_PUSH_UNSUBSCRIBE_ON_LOGOUT', False))


def push_hosts():
    """``GT_PUSH_ALLOWED_HOSTS``; ``None`` accepts any https endpoint."""
    return getattr(settings, 'GT_PUSH_ALLOWED_HOSTS', DEFAULT_PUSH_HOSTS)
