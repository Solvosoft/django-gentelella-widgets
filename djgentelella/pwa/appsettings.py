"""The settings of one application (a Site) that the manifest and the push
payloads use, read in one query."""
from django.templatetags.static import static

from djgentelella.models import GentelellaSettings
from djgentelella.pwa import conf
from djgentelella.sites import site_pk, site_q

#: The keys of ``GentelellaSettings`` the PWA reads (per Site, C1).
PWA_KEYS = (
    'site_title', 'pwa_name', 'pwa_short_name', 'pwa_description',
    'pwa_theme_color', 'pwa_background_color', 'pwa_icon_192', 'pwa_icon_512',
    'pwa_start_url', 'pwa_scope',
)


class AppSettings:
    """``PWA_KEYS`` of ``site``: the Site's value, else the global one."""

    def __init__(self, site=None):
        self.site = site
        site_id = site_pk(site)
        found, own = {}, {}
        rows = GentelellaSettings.objects.filter(
            site_q(site_id), key__in=PWA_KEYS).values_list('key', 'value', 'site_id')
        for key, value, row_site in rows:
            (own if row_site is not None else found)[key] = value
        found.update({key: value for key, value in own.items() if value})
        self.values = found

    def get(self, key, default=''):
        return self.values.get(key) or default

    def name(self):
        """``pwa_name``, ``site_title``, the Site's name, in that order."""
        name = self.get('pwa_name') or self.get('site_title')
        if not name and self.site is not None:
            name = getattr(self.site, 'name', '')
        return name or 'djgentelella'

    def scope(self):
        """``pwa_scope`` of the Site (a path that starts and ends with ``/``:
        the prefix the application is served under), else ``GT_PWA_SCOPE``."""
        value = self.get('pwa_scope').strip()
        if value.startswith('/') and value.endswith('/') and '//' not in value:
            return value
        return conf.scope()

    def icon(self, size):
        """The icon of ``size`` (``'192'`` or ``'512'``): ``pwa_icon_<size>``
        (a static path, or a URL as it is), else djgentelella's."""
        value = self.get('pwa_icon_%s' % size)
        if not value:
            return static(dict((s.split('x')[0], p)
                               for p, s in conf.DEFAULT_ICONS)[size])
        if value.startswith('/') or '://' in value:
            return value
        return static(value)
