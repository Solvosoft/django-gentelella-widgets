"""The web app manifest of the current Site and the service worker's config."""
from django.urls import reverse
from django.utils.translation import get_language

from djgentelella.pwa import conf
from djgentelella.pwa.appsettings import AppSettings
from djgentelella.pwa.push import push_enabled
from djgentelella.sites import get_current_site

_REQUEST_ATTR = '_djgentelella_pwa_manifest'


def build_manifest(request):
    """The manifest (a dict) of the Site of ``request``.

    Each value is a ``GentelellaSettings`` key (C1: the Site's,
    else the global one), else a default:

    - ``name``: ``pwa_name``, ``site_title``, the Site's name.
    - ``short_name``: ``pwa_short_name``, else the name cut to 12 characters.
    - ``description``: ``pwa_description``.
    - ``theme_color`` / ``background_color``: ``pwa_theme_color`` /
      ``pwa_background_color``, else ``GT_PWA_THEME_COLOR`` /
      ``GT_PWA_BACKGROUND_COLOR``.
    - ``icons``: ``pwa_icon_192`` and ``pwa_icon_512`` (static paths or
      URLs), else djgentelella's.
    - ``scope``: ``pwa_scope``, else ``GT_PWA_SCOPE``.
    - ``start_url``: ``pwa_start_url``, else the scope.
    """
    cached = getattr(request, _REQUEST_ATTR, None)
    if cached is not None:
        return cached
    app = AppSettings(get_current_site(request))
    name = app.name()
    scope = app.scope()
    start_url = app.get('pwa_start_url') or scope
    manifest = {
        'id': start_url,
        'name': name,
        'short_name': app.get('pwa_short_name') or name[:12],
        'start_url': start_url,
        'scope': scope,
        'display': conf.display(),
        'theme_color': app.get('pwa_theme_color') or conf.theme_color(),
        'background_color': (app.get('pwa_background_color')
                             or conf.background_color()),
        'lang': get_language() or 'en',
        'icons': [
            {'src': app.icon(size.split('x')[0]),
             'sizes': size, 'type': 'image/png', 'purpose': 'any'}
            for _path, size in conf.DEFAULT_ICONS
        ],
    }
    description = app.get('pwa_description')
    if description:
        manifest['description'] = description
    try:
        setattr(request, _REQUEST_ATTR, manifest)
    except AttributeError:
        pass
    return manifest


def worker_mode():
    """What ``sw.js`` does: ``'cache'`` (static cache + offline page, and push
    if on), ``'push'`` (push only) or ``'remove'`` (unregisters itself and
    drops its caches: what a browser that had it installs once the settings
    are turned off)."""
    if conf.service_worker_enabled():
        return 'cache'
    if push_enabled():
        return 'push'
    return 'remove'


def worker_config(request):
    """The config ``sw.js`` is rendered with."""
    mode = worker_mode()
    app = AppSettings(get_current_site(request))
    push_on = mode != 'remove' and push_enabled()
    return {
        'mode': mode,
        'cache_name': 'gt-pwa-%s' % conf.cache_version(),
        'cache_prefixes': conf.cache_prefixes() if mode == 'cache' else [],
        'offline_url': reverse('gt_pwa_offline') if mode == 'cache' else '',
        'precache': conf.precache() if mode == 'cache' else [],
        'push': push_on,
        'default_title': app.name(),
        'scope': app.scope(),
        # pushsubscriptionchange: where the worker sends the new subscription.
        'resubscribe_url': reverse('gt_push_resubscribe') if push_on else '',
    }
