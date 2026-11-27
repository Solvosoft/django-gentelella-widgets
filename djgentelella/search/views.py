"""The results page (``search/``) and the JSON API (``gtapis/search/``).

Both read ``q``, the text. The page shows every group with its first hits
and a "see more" link per group, which is the same page with
``source=<name>`` and ``page=<n>``. The API answers the box's autocomplete:
``sources=a,b`` (optional), ``limit`` and ``offset``.

Neither requires a session: what a request finds is what its data sources
allow (``has_permission`` and ``get_queryset``), and a source open to
anonymous users is so on purpose (``perms = []``).
"""

from urllib.parse import urlencode

from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.module_loading import import_string
from django.views.decorators.http import require_GET

from djgentelella.sites import get_current_site
from djgentelella.utils import _get_site_settings

from .base import (
    NAVBAR_SETTING, default_source_names, search_setting, searchable_sources,
)
from .engine import clean_text, search

_TRUE = ('1', 'true', 'yes', 'on', 'si', 'sí')


def navbar_enabled(request):
    """Whether the top bar shows the search box for ``request``.

    The ``global_search`` GentelellaSettings of the current Site, when it
    has one, else ``GT_SEARCH_NAVBAR`` (False by default). The Site value is
    cached like every other setting, so drawing the bar costs no query once
    it is known.
    """
    site = get_current_site(request) if request is not None else None
    if site is not None:
        value = _get_site_settings(NAVBAR_SETTING, site.pk)
        if value is not None:
            return value.strip().lower() in _TRUE
    return bool(search_setting('NAVBAR'))


def _int(value, default, low=None, high=None):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    if low is not None and value < low:
        return default
    if high is not None:
        value = min(value, high)
    return value


def requested_sources(request, names):
    """The source names a request may search: ``names`` (or every one),
    within what ``GT_SEARCH_SOURCES`` allows it."""
    allowed = default_source_names(request)
    if names is None:
        return allowed
    if allowed is not None:
        names = [name for name in names if name in allowed]
    return names


#: What the results page itself puts in its context: ``GT_SEARCH_PAGE_CONTEXT``
#: cannot replace it.
RESERVED_CONTEXT = ('query', 'source', 'groups', 'min_length', 'page',
                    'source_label', 'previous_page', 'next_page')


def page_context(request):
    """What the results page adds to its context besides the hits: the
    ``base_template`` it extends (``GT_SEARCH_BASE_TEMPLATE``) and whatever
    the ``GT_SEARCH_PAGE_CONTEXT`` callable returns for ``request`` -- a
    ``base_template`` of its own, a theme, ``breadcrumbs``. The keys of
    :data:`RESERVED_CONTEXT` are left out.
    """
    context = {'base_template': search_setting('BASE_TEMPLATE')}
    hook = search_setting('PAGE_CONTEXT')
    if not hook:
        return context
    if isinstance(hook, str):
        hook = import_string(hook)
    extra = hook(request)
    if extra is None:
        return context
    if not isinstance(extra, dict):
        raise ImproperlyConfigured('GT_SEARCH_PAGE_CONTEXT must return a dict, not %s'
                                   % type(extra).__name__)
    context.update({key: value for key, value in extra.items()
                    if key not in RESERVED_CONTEXT})
    return context


def more_url(text, source):
    return '%s?%s' % (reverse('gt-search'), urlencode({'q': text,
                                                       'source': source}))


@require_GET
def search_page(request):
    text = clean_text(request.GET.get('q'))
    source = request.GET.get('source') or None
    context = page_context(request)
    context.update({'query': text, 'source': None, 'groups': [],
                    'min_length': search_setting('MIN_LENGTH')})
    if source is not None:
        names = requested_sources(request, [source])
        size = int(search_setting('PAGE_SIZE'))
        page = _int(request.GET.get('page'), 1, low=1)
        groups = search(request, text, sources=names, limit=size,
                        offset=(page - 1) * size) if names else []
        found = searchable_sources(names or [])
        context.update({
            'source': source, 'page': page,
            'source_label': (found[source].global_search.get_group(found[source])
                             if source in found
                             and found[source].has_permission(request) else ''),
            'previous_page': page - 1 if page > 1 else None,
            'next_page': (page + 1 if groups and groups[0].has_more else None),
        })
    else:
        groups = search(request, text, sources=requested_sources(request, None))
    for group in groups:
        group.more_url = more_url(text, group.source)
    context['groups'] = groups
    return render(request, 'gentelella/search/results.html', context)


@require_GET
def search_api(request):
    """``{"query", "groups": [{"source", "label", "icon", "has_more",
    "more_url", "results": [{"title", "subtitle", "url", "score", "pk"}]}]}``.
    """
    text = clean_text(request.GET.get('q'))
    names = request.GET.get('sources')
    names = [n for n in names.split(',') if n] if names else None
    limit = _int(request.GET.get('limit'), None, low=1,
                 high=int(search_setting('MAX_LIMIT')))
    offset = _int(request.GET.get('offset'), 0, low=0)
    groups = search(request, text, sources=requested_sources(request, names),
                    limit=limit, offset=offset)
    data = []
    for group in groups:
        item = group.as_dict()
        item['more_url'] = more_url(text, group.source)
        data.append(item)
    return JsonResponse({'query': text, 'groups': data})
