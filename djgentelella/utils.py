from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db.models import Q

from djgentelella.models import GentelellaSettings


def get_settings(key, none_asdefault=False):
    _cache = cache.get(key)
    if _cache:
        return _cache
    value = GentelellaSettings.objects.filter(key=key).values('value')
    if value:
        value = value[0]['value']
        cache.set(key, value, timeout=None)
    else:
        if none_asdefault:
            value = None
        else:
            value = ''
    return value


def set_settings(key, value):
    GentelellaSettings.objects.update_or_create(key=key, defaults={'value': value})
    cache.delete(key)


def clean_cache(keys):
    _cache = cache.delete_many(keys)


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
