import re

from django.conf import settings as django_settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db.models import Q
from django.utils.safestring import mark_safe

from djgentelella.models import GentelellaSettings, settings_cache_key
from djgentelella.sites import site_pk


#: What the global cache holds for a key that has no global row. The global
#: scope keeps the bare key and a plain string value (see settings_cache_key).
_MISSING = '\x00gt-setting-missing'


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
    value = cache.get(key)
    if value is None:
        found = GentelellaSettings.objects.filter(
            key=key, site__isnull=True).values_list('value', flat=True)[:1]
        # A key without a global row is cached too: most pages read several
        # settings nobody set, and each would cost a query on every request.
        value = found[0] if found else _MISSING
        cache.set(key, value, timeout=None)
    if value == _MISSING:
        return None if none_asdefault else ''
    return value


#: The settings whose value is HTML: ``{% get_settings %}`` prints them as
#: they are. ``settings.GT_HTML_SETTINGS`` replaces this list.
DEFAULT_HTML_SETTINGS = ('site_logo',)

# An ``&`` that does not start a character reference (``&lt;``, ``&#60;``,
# ``&#x3c;``).
_BARE_AMPERSAND = re.compile(
    r'&(?!(?:[A-Za-z][A-Za-z0-9]{1,31}|#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6});)')


def html_settings():
    """The keys whose value ``{% get_settings %}`` prints as HTML."""
    return frozenset(getattr(django_settings, 'GT_HTML_SETTINGS',
                             DEFAULT_HTML_SETTINGS))


def setting_allows_html(key):
    """Whether the value of the setting ``key`` is HTML (see
    :func:`html_settings`)."""
    return key in html_settings()


def escape_setting(value):
    """``value`` as text for HTML: ``<``, ``>``, quotes and every ``&`` that
    does not start a character reference are escaped.

    A character reference is kept as it is, so a value stored already escaped
    (``Sales &lt;North&gt;``, what djodo and older code saved because the
    values used to be printed unescaped) shows the same text, not
    ``&amp;lt;``. A reference can only ever be text: it cannot open a tag or
    close an attribute.
    """
    value = _BARE_AMPERSAND.sub('&amp;', str(value))
    return (value.replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;').replace("'", '&#x27;'))


def get_settings_display(key, site=None, default=''):
    """The value of the setting ``key`` ready to print in a template (safe):
    as it is for the keys of :func:`html_settings`, escaped
    (:func:`escape_setting`) for any other. ``default`` when there is none.

    What ``{% get_settings %}`` prints.
    """
    value = get_settings(key, site=site)
    if not value:
        return default
    if setting_allows_html(key):
        return mark_safe(value)
    return mark_safe(escape_setting(value))


def set_settings(key, value, site=None):
    """Store ``value`` for ``key``: global with ``site=None``, else that Site's."""
    site_id = site_pk(site)
    GentelellaSettings.objects.update_or_create(
        key=key, site_id=site_id, defaults={'value': value})
    cache.delete(settings_cache_key(key, site_id))


#: The global settings djgentelella's migrations create (``0001``, ``0008``,
#: ``00012``): what a fresh database has before anyone edits them.
DEFAULT_SETTINGS = {
    'site_title': 'Django Gentelella Alela!',
    'site_logo': '<h1><i class="fa fa-paw"></i></h1>',
    'site_theme': 'gentelella/css/custom.css',
    'use_compress_static': 'true',
}


def load_default_settings(overwrite=False, **values):
    """Create the global settings the migrations load (:data:`DEFAULT_SETTINGS`),
    those that are missing; with ``overwrite=True`` reset them too.

    For what empties the database after the migrations: the *flush* of a
    ``TransactionTestCase`` or a live server test (Selenium) leaves no
    settings, so the pages lose their title, their theme and the bundled
    static files (``use_compress_static``). Such a test calls it in
    ``setUp``. ``values`` replaces or adds keys (``use_compress_static='false'``
    to serve the files one by one); a value ``None`` leaves that key out.
    Returns the keys written.
    """
    wanted = {**DEFAULT_SETTINGS, **values}
    written = []
    for key, value in wanted.items():
        if value is None:
            continue
        if overwrite:
            set_settings(key, value)
            written.append(key)
            continue
        _row, created = GentelellaSettings.objects.get_or_create(
            key=key, site=None, defaults={'value': value})
        if created:
            written.append(key)
    clean_cache(written)
    return written


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
