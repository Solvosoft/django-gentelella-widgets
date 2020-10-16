from django.core.cache import cache

from djgentelella.models import GentelellaSettings


def get_settings(key, none_asdefault=False):
    _cache = cache.get(key)
    if _cache:
        return _cache
    value = GentelellaSettings.objects.filter(key=key).values('value')
    if value:
        value=value[0]['value']
        cache.set(key, value, timeout=None)
    else:
        if none_asdefault:
            value=None
        else:
            value = ''
    return value

def set_settings(key, value):
    instance = GentelellaSettings.objects.filter(key=key, value=value).first()
    if instance:
        instance.key=key
        instance.value=value
        instance.save()
    else:
        GentelellaSettings.objects.create(key=key, value=value)


def clean_cache(keys):
    _cache = cache.delete_many(keys)
