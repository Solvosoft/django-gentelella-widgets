"""The current Site and the Site rule.

One djgentelella installation can serve several applications, each one a
``django.contrib.sites`` Site with its own menus and settings. A row with
``site=NULL`` is global: every Site sees it, and a row with ``site=<current>``
wins over the global one with the same identity.

The Site of a request is found in this order:

1. ``request.site``, when a middleware already put it there
   (``CurrentSiteMiddleware``, or an application middleware that resolves it by
   host or by path prefix). ``None`` there means "no Site" and is respected.
2. The Site whose ``domain`` is the host of the request, with or without the
   port, the same lookup ``Site.objects.get_current(request)`` does.
3. ``None`` otherwise: menus and settings are then the global ones.

``SITE_ID`` is deliberately not a fallback: with it, every request of a host
without its own Site would land in that Site instead of in the global scope.
A project that wants ``SITE_ID`` to decide adds ``CurrentSiteMiddleware``,
which puts that Site in ``request.site`` (step 1).
"""

from django.apps import apps
# requests.py imports nothing and works without sites installed.
from django.contrib.sites.requests import RequestSite
from django.core.exceptions import DisallowedHost
from django.db.models import Model, Q
from django.http import HttpRequest, QueryDict
from django.http.request import split_domain_port

# Cached on the request, so the menus and every {% get_settings %} of a page
# resolve the Site once. A sentinel, because None is a valid answer.
_REQUEST_ATTR = '_djgentelella_site'
_UNSET = object()


def sites_installed():
    """True when ``django.contrib.sites`` is in ``INSTALLED_APPS``."""
    return apps.is_installed('django.contrib.sites')


def _site_for_host(request):
    site_model = apps.get_model('sites', 'Site')
    try:
        host = request.get_host()
    except DisallowedHost:
        return None
    domain, _port = split_domain_port(host)
    for candidate in dict.fromkeys((host, domain)):
        if not candidate:
            continue
        site = site_model.objects.filter(domain__iexact=candidate).first()
        if site is not None:
            return site
    return None


def get_current_site(request=None):
    """The Site of the request, or ``None``.

    ``None`` if django.contrib.sites is not installed, without a request, or
    if there is no Site for the host. Uses ``request.site`` when
    ``CurrentSiteMiddleware`` (or another middleware) already put it there.
    """
    if request is None or not sites_installed():
        return None
    cached = getattr(request, _REQUEST_ATTR, _UNSET)
    if cached is not _UNSET:
        return cached
    site_model = apps.get_model('sites', 'Site')
    if hasattr(request, 'site'):
        # A RequestSite (sites not installed when the middleware ran) or any
        # other object is not a row anything can point to: global.
        site = request.site if isinstance(request.site, site_model) else None
    else:
        site = _site_for_host(request)
    try:
        setattr(request, _REQUEST_ATTR, site)
    except AttributeError:
        pass
    return site


def site_q(site, field='site'):
    """``Q(site=site) | Q(site__isnull=True)``.

    With ``site=None`` it is only ``Q(site__isnull=True)``: the global rows.
    ``field`` is the name of the foreign key, or a path to it
    (``'page__site'``).
    """
    isnull = Q(**{field + '__isnull': True})
    if site is None:
        return isnull
    return Q(**{field: site}) | isnull


def site_pk(site):
    """The id of ``site``: a Site, a Site id, or ``None`` for global.

    ``None`` and an object that is not a row (a ``RequestSite``, which
    ``CurrentSiteMiddleware`` sets when sites is not installed) are the global
    scope, as in :func:`get_current_site`. An ``int`` or a string of digits is
    a Site id. A model instance without a primary key (not saved yet) and any
    other value raise ``ValueError`` / ``TypeError`` with a clear message,
    instead of failing later inside the query.
    """
    if site is None:
        return None
    if isinstance(site, bool):
        raise TypeError('A Site, a Site id or None was expected, not %r.' % site)
    if isinstance(site, int):
        return site
    if isinstance(site, str):
        if site.strip().isdigit():
            return int(site)
        raise ValueError('%r is not a Site id.' % site)
    if isinstance(site, Model):
        if site.pk is None:
            raise ValueError('The Site %r has not been saved yet.' % site)
        return site.pk
    if isinstance(site, RequestSite):
        return None
    raise TypeError('A Site, a Site id or None was expected, not %r.' % site)


def resolve_site(site):
    """The Site row of ``site`` (a Site, its id or ``None``), or ``None`` for
    the global scope.

    An id of no Site raises ``ValueError``: it is never taken as the global
    scope, so a job whose Site went away fails instead of reading the global
    settings and flags.
    """
    if site is None or isinstance(site, Model):
        return site
    pk = site_pk(site)
    if pk is None:
        return None
    found = apps.get_model('sites', 'Site').objects.filter(pk=pk).first()
    if found is None:
        raise ValueError('There is no Site with id %s.' % pk)
    return found


def site_request(site, user=None):
    """A synthetic ``GET`` request of ``site`` on behalf of ``user``.

    For asking, from one Site, what another Site answers: the export formats
    of a report of another App (``available_formats(site_request(...))``), its
    conditions, flags and settings. It is a real
    :class:`~django.http.HttpRequest`, so whatever reads a request gets one
    (``request.user``, ``request.GET``, ``get_host()``...), with:

    * ``site``: the Site row (``site`` may be a Site, its id or ``None`` for
      the global scope; an id of no Site raises ``ValueError``), which
      :func:`get_current_site` takes as it is;
    * ``user``: ``user``, or an ``AnonymousUser`` when it is ``None`` (the
      system, as in :class:`~djgentelella.authorization.ConditionRequest`);
    * ``method = 'GET'``, ``path = '/'``, empty ``GET``, ``POST`` and
      ``COOKIES``; the host is the Site's ``domain`` (``SERVER_NAME``, and
      ``HTTP_HOST`` too, so ``get_host()`` checks it against
      ``ALLOWED_HOSTS`` like any request) and ``localhost`` for the global
      scope;
    * ``is_site_request = True``, to tell it apart from a real one.

    No middleware has run on it: there is no session nor messages, and the
    language is the active one. Per-request caches (authorizations with
    ``cache=True``) live on it, so build a new one when the user changes.
    """
    site = resolve_site(site)
    if user is None:
        # auth.models needs the app registry; this module is imported before
        # it is ready (djgentelella.authorization imports it).
        from django.contrib.auth.models import AnonymousUser  # noqa: PLC0415

        user = AnonymousUser()
    request = HttpRequest()
    request.method = 'GET'
    request.path = request.path_info = '/'
    request.GET = QueryDict()
    request.POST = QueryDict()
    request.META = {'SERVER_NAME': site.domain if site is not None else 'localhost',
                    'SERVER_PORT': '80', 'REQUEST_METHOD': 'GET',
                    'PATH_INFO': '/', 'QUERY_STRING': ''}
    if site is not None:
        request.META['HTTP_HOST'] = site.domain
    request.user = user
    request.site = site
    request.is_site_request = True
    return request
