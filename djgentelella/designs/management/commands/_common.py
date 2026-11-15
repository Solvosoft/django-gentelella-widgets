from django.apps import apps
from django.core.management.base import CommandError


def get_site(domain):
    """The Site of ``--site``, or ``None`` (global) without one."""
    if not domain:
        return None
    site_model = apps.get_model('sites', 'Site')
    try:
        return site_model.objects.get(domain=domain)
    except site_model.DoesNotExist:
        raise CommandError('No site with domain %r.' % domain) from None
