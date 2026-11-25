"""Which theme a Site uses (:mod:`djgentelella.theme`)."""

from django.core.cache import cache

from djgentelella.models import SiteTheme, theme_cache_key
from djgentelella.sites import site_pk


def resolve_theme(site=None):
    """``(pk, version, has_logo)`` of the theme of ``site`` -- its own, else
    the global one -- or ``None``. Cached until a theme is saved or deleted.
    """
    site_id = site_pk(site)
    found = None
    for scope in ([site_id, None] if site_id is not None else [None]):
        key = theme_cache_key(scope)
        cached = cache.get(key)
        if cached is None:
            row = SiteTheme.objects.filter(site_id=scope).values_list(
                'pk', 'version', 'logo').first()
            cached = (row[0], row[1], bool(row[2])) if row else ()
            cache.set(key, cached, timeout=None)
        if cached:
            found = tuple(cached)
            break
    return found


def get_theme(site=None):
    """The :class:`~djgentelella.models.SiteTheme` that applies to ``site``,
    or ``None``."""
    found = resolve_theme(site)
    if found is None:
        return None
    return SiteTheme.objects.filter(pk=found[0]).first()
