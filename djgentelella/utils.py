from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db.models import Q

from djgentelella.models import GentelellaSettings, settings_cache_key
from djgentelella.sites import site_pk


def _get_site_settings(key, site_id):
    """The value stored for ``key`` in that Site only, or ``None``.

    Cached as ``(value,)`` or ``()``: a Site without its own value is the usual
    case, and it must not cost a query on every read.
    """
    cache_key = settings_cache_key(key, site_id)
    cached = cache.get(cache_key)
    if cached is None:
        value = GentelellaSettings.objects.filter(
            key=key, site_id=site_id).values_list('value', flat=True)[:1]
        cached = (value[0],) if value else ()
        cache.set(cache_key, cached, timeout=None)
    return cached[0] if cached else None


def get_settings(key, site=None, none_asdefault=False):
    """The value of the setting ``key``: the Site's one, else the global one.

    ``site`` is a Site, a Site id or ``None`` (only the global value). Without
    a value it returns ``''``, or ``None`` with ``none_asdefault=True``.
    """
    if isinstance(site, bool):
        # The old signature was get_settings(key, none_asdefault).
        site, none_asdefault = None, site
    site_id = site_pk(site)
    if site_id is not None:
        value = _get_site_settings(key, site_id)
        if value is not None:
            return value
    _cache = cache.get(key)
    if _cache:
        return _cache
    value = GentelellaSettings.objects.filter(
        key=key, site__isnull=True).values('value')
    if value:
        value = value[0]['value']
        cache.set(key, value, timeout=None)
    else:
        if none_asdefault:
            value = None
        else:
            value = ''
    return value


def set_settings(key, value, site=None):
    """Store ``value`` for ``key``: global with ``site=None``, else that Site's."""
    site_id = site_pk(site)
    GentelellaSettings.objects.update_or_create(
        key=key, site_id=site_id, defaults={'value': value})
    cache.delete(settings_cache_key(key, site_id))


def clean_cache(keys, site=None):
    """Forget the cached value of ``keys`` in one scope (global by default)."""
    cache.delete_many([settings_cache_key(key, site) for key in keys])


def contenttypes_from_labels(entries):
    """Resolve ``app_label.model`` strings into a ContentType queryset.

    Anything that is not such a string is skipped, and an empty result is an
    empty queryset -- never every content type, which as a filter would widen
    what the caller may see instead of narrowing it.
    """
    q = Q()
    for item in entries:
        if isinstance(item, str) and '.' in item:
            app_label, model_name = item.split('.', 1)
            q |= Q(
                app_label=app_label.strip(),
                model=model_name.strip().lower(),
            )

    if not q:
        return ContentType.objects.none()

    return ContentType.objects.filter(q)
