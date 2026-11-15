"""System checks of djgentelella."""

from django.apps import apps
from django.core import checks


@checks.register(checks.Tags.compatibility)
def check_sites_installed(app_configs=None, **kwargs):
    """``django.contrib.sites`` is required since migration 0022_site_scoping.

    Menu items and settings have an optional foreign key to ``sites.Site``.
    Without the app, Django only reports an unknown related model; this says
    what to do.
    """
    if apps.is_installed('django.contrib.sites'):
        return []
    return [checks.Error(
        'djgentelella requires django.contrib.sites.',
        hint="Add 'django.contrib.sites' to INSTALLED_APPS and set SITE_ID; "
             'menus and settings are global unless a Site is given '
             '(see the djgentelella docs, sites).',
        id='djgentelella.E001',
    )]
