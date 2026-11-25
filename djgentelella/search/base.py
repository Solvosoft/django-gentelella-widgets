"""Which data sources the global search reads, and how a hit looks.

A searchable source is a registered
:class:`~djgentelella.datasources.base.DataSource` with a
:class:`GlobalSearch` in its ``global_search`` attribute -- set it by hand or
with the :func:`searchable` decorator. There is no second registry: the
search walks the data source registry and keeps the sources that have one.
"""

import re
import string
from dataclasses import dataclass, field as dc_field

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from django.urls import NoReverseMatch, reverse
from django.utils.module_loading import import_string

from djgentelella.datasources.base import (
    TEXT_KINDS, get_datasources, resolve_field_path,
)

#: The full-text weights, from the most to the least important.
WEIGHTS = ('A', 'B', 'C', 'D')
#: What each weight is worth in the icontains engine: PostgreSQL's defaults
#: for ``ts_rank``, so both engines order a group alike.
WEIGHT_VALUES = {'A': 1.0, 'B': 0.4, 'C': 0.2, 'D': 0.1}
#: A link to a design page about the object: ``page:<path>`` opens
#: ``designs/<path>/<pk>`` (the convention of the menus and the row links).
PAGE_PREFIX = 'page:'
#: URL schemes a hit may link to; anything else (``javascript:``) is dropped.
SAFE_SCHEMES = ('', 'http', 'https')

_SCHEME = re.compile(r'^\s*([a-zA-Z][a-zA-Z0-9+.\-]*):')


@dataclass
class GlobalSearch:
    """How the global search reads one data source.

    :param fields: where to search. A dict ``{orm_path: weight}`` with
        weights ``'A'`` (most important) to ``'D'``, or a list of paths, all
        ``'A'``. ``None``: the text columns of the source, all ``'A'``.
        Paths may cross foreign keys (``'country__name'``), never a
        many-to-many or a reverse relation: they would repeat the object.
    :param title: the hit's title: an ORM path (``'name'``), a format string
        over the object (``'{code} - {name}'``, ``'{country.name}'``) or a
        callable ``(obj) -> str``. ``None``: ``str(obj)``.
    :param subtitle: the second line, same forms as ``title``; optional.
    :param url: where the hit leads: a URL name reversed with the pk, a
        design page ``'page:<path>'`` (``designs/<path>/<pk>``), a format
        string that starts with ``/`` or contains ``{`` (``'/c/{pk}/'``) or a
        callable ``(obj) -> str``. ``None``: ``obj.get_absolute_url()`` if
        the model has it.
    :param group: the label of the group; the source's label by default.
    :param icon: a CSS icon class shown next to the group (``'fa fa-flag'``).
    :param limit: hits shown per group; ``GT_SEARCH_LIMIT`` by default.
    :param select_related: relations loaded with the hits, for a title or a
        URL that reads them. Foreign keys named by a ``title`` or
        ``subtitle`` path are added on their own.
    :param owners: who the source belongs to -- the keys of whatever groups
        sources in the project (the slugs of djodo's Apps, a tenant...).
        ``()``: shared, it belongs to nobody. djgentelella only stores
        them: a ``GT_SEARCH_SOURCES`` hook reads them
        (:func:`source_owners`, :func:`searchable_sources` ``owner=``) to
        decide what a request searches.
    :param tags: free labels of the source (``'catalog'``, ``'people'``),
        for the same hooks and for screens that let someone choose sources
        (:func:`source_tags`, :func:`searchable_sources` ``tags=``).
    """
    fields: object = None
    title: object = None
    subtitle: object = None
    url: object = None
    group: object = None
    icon: str = ''
    limit: int = None
    select_related: tuple = dc_field(default_factory=tuple)
    owners: tuple = dc_field(default_factory=tuple)
    tags: tuple = dc_field(default_factory=tuple)

    def __post_init__(self):
        if isinstance(self.fields, dict):
            for path, weight in self.fields.items():
                if weight not in WEIGHTS:
                    raise ImproperlyConfigured(
                        'Weight %r of %r is not one of %s'
                        % (weight, path, ', '.join(WEIGHTS)))
        elif self.fields is not None and (
                isinstance(self.fields, str)
                or not all(isinstance(p, str) for p in self.fields)):
            raise ImproperlyConfigured(
                'GlobalSearch.fields is a dict {path: weight} or a list of '
                'paths, not %r' % (self.fields,))
        if self.limit is not None and int(self.limit) < 1:
            raise ImproperlyConfigured('GlobalSearch.limit must be positive')
        self.select_related = tuple(self.select_related or ())
        self.owners = _keys(self.owners, 'owners')
        self.tags = _keys(self.tags, 'tags')

    def weighted_fields(self, source, request):
        """``[(path, weight)]`` to search in ``source``."""
        if isinstance(self.fields, dict):
            result = list(self.fields.items())
        elif self.fields is not None:
            result = [(path, 'A') for path in self.fields]
        else:
            result = [(column.name, 'A') for column in source.columns(request)
                      if column.kind in TEXT_KINDS]
        model = getattr(source, 'model', None)
        if model is not None:
            for path, _weight in result:
                check_path(model, path)
        return result

    def get_group(self, source):
        return str(self.group or source.get_label())

    def get_limit(self):
        return int(self.limit or search_setting('LIMIT'))

    def related(self, model):
        """``select_related`` plus the foreign keys the title and subtitle
        read through ORM paths."""
        names = list(self.select_related)
        if model is None:
            return names
        for spec in (self.title, self.subtitle):
            for path in text_paths(spec):
                parts = path.split('__')[:-1]
                if parts and is_forward_path(model, '__'.join(parts)):
                    names.append('__'.join(parts))
        return list(dict.fromkeys(names))

    def render_title(self, obj):
        if self.title is None:
            return str(obj)
        return render_text(self.title, obj)

    def render_subtitle(self, obj):
        if self.subtitle is None:
            return ''
        return render_text(self.subtitle, obj)

    def render_url(self, obj):
        return safe_url(build_url(self.url, obj))


def searchable(**options):
    """Decorator: make a data source (class or instance) searchable.

    ::

        @register_datasource
        @searchable(fields={'name': 'A', 'code': 'B'}, title='name',
                    url='demoapp_country_detail', icon='fa fa-flag')
        class CountrySource(ModelDataSource):
            model = Country

    Equivalent to ``global_search = GlobalSearch(**options)`` on the class.
    It has to be applied before ``register_datasource`` (below it), which
    instantiates a class.
    """
    spec = GlobalSearch(**options)

    def decorate(source):
        source.global_search = spec
        return source
    return decorate


def search_setting(name):
    """``GT_SEARCH_<name>`` or its default."""
    return getattr(settings, 'GT_SEARCH_' + name, DEFAULTS[name])


DEFAULTS = {
    # Hits per group in the box and on the results page.
    'LIMIT': 5,
    # Hits per page when the results page shows one group ("see more").
    'PAGE_SIZE': 20,
    # The largest ``limit`` the JSON API accepts.
    'MAX_LIMIT': 50,
    # Shorter texts do not search (and cost no query).
    'MIN_LENGTH': 2,
    # Longer texts are cut to this length.
    'MAX_LENGTH': 200,
    # The search box in the top bar; a Site overrides it with the
    # GentelellaSettings "global_search".
    'NAVBAR': False,
    # pg_trgm: None detects the extension, True/False skip the detection.
    'TRIGRAM': None,
    # The least word similarity (0..1) a trigram hit needs.
    'TRIGRAM_THRESHOLD': 0.5,
    # Dotted path of a callable (request) -> list of source names or None:
    # the sources a request searches when it does not name them.
    'SOURCES': None,
    # The template the results page extends.
    'BASE_TEMPLATE': 'gentelella/base.html',
    # Dotted path of a callable (request) -> dict added to the context of the
    # results page: a base_template, a theme, breadcrumbs...
    'PAGE_CONTEXT': None,
}


#: ``owner=`` of :func:`searchable_sources` when it is not given: any owner.
ANY_OWNER = object()


def _keys(value, name):
    """``owners``/``tags`` as a tuple of non-empty strings; a bare string is
    one key."""
    if value is None:
        return ()
    if isinstance(value, str):
        value = (value,)
    value = tuple(dict.fromkeys(value))
    if not all(isinstance(key, str) and key for key in value):
        raise ImproperlyConfigured('GlobalSearch.%s takes non-empty strings, not %r'
                                   % (name, value))
    return value


def source_owners(source):
    """``GlobalSearch.owners`` of ``source``; ``()`` for a shared source or
    one that is not searchable."""
    spec = getattr(source, 'global_search', None)
    return spec.owners if isinstance(spec, GlobalSearch) else ()


def source_tags(source):
    """``GlobalSearch.tags`` of ``source``; ``()`` when it has none."""
    spec = getattr(source, 'global_search', None)
    return spec.tags if isinstance(spec, GlobalSearch) else ()


def is_owned_by(source, owner):
    """Whether ``owner`` may search ``source``: it is shared (no owners) or
    ``owner`` is one of them. ``owner=None`` (outside every owner) only
    reaches the shared ones."""
    owners = source_owners(source)
    return not owners or (owner is not None and owner in owners)


def searchable_sources(names=None, *, owner=ANY_OWNER, tags=()):
    """The registered sources that have a ``global_search``, by name.

    ``names`` keeps those and in that order; unknown or not searchable names
    are left out. ``owner`` keeps the shared sources and those of ``owner``
    (:func:`is_owned_by`; ``None``: only the shared ones), ``tags`` those
    that have every one of them. What a ``GT_SEARCH_SOURCES`` hook needs::

        def app_sources(request):
            app = getattr(request, 'app', None)
            return list(searchable_sources(owner=app.slug if app else None))
    """
    registry = get_datasources()
    found = {name: source for name, source in registry.items()
             if isinstance(getattr(source, 'global_search', None), GlobalSearch)}
    if owner is not ANY_OWNER:
        found = {name: source for name, source in found.items()
                 if is_owned_by(source, owner)}
    wanted = set(_keys(tags, 'tags'))
    if wanted:
        found = {name: source for name, source in found.items()
                 if wanted <= set(source_tags(source))}
    if names is None:
        return found
    return {name: found[name] for name in names if name in found}


def default_source_names(request):
    """The names ``GT_SEARCH_SOURCES`` gives for ``request``, or None."""
    hook = search_setting('SOURCES')
    if not hook:
        return None
    if isinstance(hook, str):
        hook = import_string(hook)
    names = hook(request)
    return None if names is None else list(names)


# -- paths and rendering ----------------------------------------------------

def check_path(model, path):
    """Fail on a search path that does not exist or repeats the object."""
    current = model
    for part in path.split('__'):
        if current is None:
            raise ImproperlyConfigured('%s: %r is not a field path'
                                       % (model._meta.label, path))
        try:
            field = current._meta.get_field(part)
        except FieldDoesNotExist:
            raise ImproperlyConfigured('%s has no field %r'
                                       % (model._meta.label, path)) from None
        if field.many_to_many or field.one_to_many:
            raise ImproperlyConfigured(
                '%s: %r crosses a to-many relation; the global search only '
                'follows foreign keys' % (model._meta.label, path))
        current = field.related_model if field.is_relation else None


def is_forward_path(model, path):
    """True if every step of ``path`` is a forward foreign key/one-to-one."""
    current = model
    for part in path.split('__'):
        try:
            field = current._meta.get_field(part)
        except (FieldDoesNotExist, AttributeError):
            return False
        if not field.concrete or not (field.many_to_one or field.one_to_one):
            return False
        current = field.related_model
    return True


def text_paths(spec):
    """The ORM paths a title or subtitle reads."""
    if not isinstance(spec, str):
        return []
    if '{' not in spec:
        return [spec]
    paths = []
    for _literal, name, _spec, _conv in string.Formatter().parse(spec):
        if name:
            paths.append(name.split('.')[0].split('[')[0])
    return paths


def resolve_path(obj, path):
    """The value at an ORM path (``'country__name'``) of ``obj``."""
    value = obj
    for part in path.split('__'):
        if value is None:
            return None
        value = getattr(value, part)
    return value() if callable(value) and not hasattr(value, 'pk') else value


class _ObjectFields(dict):
    """What a format string sees: the object's attributes and ORM paths."""

    def __init__(self, obj):
        super().__init__()
        self.obj = obj

    def __missing__(self, key):
        value = resolve_path(self.obj, key)
        return '' if value is None else value


def render_text(spec, obj):
    if callable(spec):
        value = spec(obj)
    elif '{' in spec:
        value = spec.format_map(_ObjectFields(obj))
    else:
        value = resolve_path(obj, spec)
    return '' if value is None else str(value)


def build_url(spec, obj):
    if spec is None:
        getter = getattr(obj, 'get_absolute_url', None)
        return getter() if getter else None
    if callable(spec):
        return spec(obj)
    if spec.startswith(PAGE_PREFIX):
        path = spec[len(PAGE_PREFIX):].strip('/')
        try:
            return reverse('gt-design-page',
                           kwargs={'path': '%s/%s' % (path, obj.pk)})
        except NoReverseMatch:
            return None
    if spec.startswith('/') or '{' in spec:
        return spec.format_map(_ObjectFields(obj))
    for args, kwargs in (([obj.pk], {}), ([], {'pk': obj.pk})):
        try:
            return reverse(spec, args=args, kwargs=kwargs)
        except NoReverseMatch:
            continue
    return None


def safe_url(url):
    """``url`` when it is relative or http(s); ``None`` otherwise."""
    if not url:
        return None
    url = str(url)
    # Browsers drop control characters and blanks inside a scheme
    # ("java\tscript:"), so they are dropped before looking at it.
    match = _SCHEME.match(re.sub(r'[\x00-\x20]', '', url))
    scheme = match.group(1).lower() if match else ''
    return url if scheme in SAFE_SCHEMES else None
