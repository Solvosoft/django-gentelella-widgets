"""From a design document to a page: :func:`resolve`, then :func:`render`.

:func:`resolve` does everything that depends only on the document and the
project -- the envelope, the tree, each node's props and build, the forms, the
permissions -- and returns a :class:`ResolvedPage` or the list of errors.
:func:`render` turns a resolved page into a response for one request, inside
``gentelella/base.html``. :func:`resolve_page` keeps the resolution of a
published :class:`~djgentelella.designs.models.Page` by its hash, so serving
a page does not validate it again on every request.

A node may carry a condition of :mod:`djgentelella.authorization` in
``props.condition`` or ``meta.condition``. :func:`resolve` validates it
and keeps it out of the props the component sees; :func:`render` leaves out
the nodes whose condition does not hold for the request, children and media
included, and :func:`node_endpoints` does not serve their endpoints.
"""

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field

from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import render as render_template
from django.templatetags.static import static
from django.urls import Resolver404, URLResolver
from django.urls.resolvers import RegexPattern
from django.utils.safestring import mark_safe
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from rest_framework.routers import SimpleRouter

from djgentelella.authorization import evaluate_condition, validate_condition
from djgentelella.designs import conf, exposure, format, registry
from djgentelella.designs.components import ResolveContext
from djgentelella.designs.css import clean_css
from djgentelella.designs.jsonschema import Error

logger = logging.getLogger(__name__)

PAGE_TEMPLATE = 'gtdesigns/page.html'

#: What the URL of an endpoint that carries the object of the page has.
PARENT_GROUP = '(?P<parent_pk>'

__all__ = ['ObjectConditionResolver', 'ResolvedNode', 'ResolvedPage',
           'cached_page_trust', 'clear_cache',
           'make_context', 'node_condition', 'node_endpoints', 'page_context',
           'page_trust',
           'render', 'render_errors', 'resolve', 'resolve_page']


@dataclass
class ResolvedNode:
    id: str
    type: str
    path: str
    component: object
    build: object
    children: list = field(default_factory=list)
    #: The node's own condition (:mod:`djgentelella.authorization`), ``None``
    #: without one.
    condition: object = None
    #: Its condition and those of its ancestors, root first: all must hold.
    conditions: tuple = ()
    #: The conditions of the nodes it works on (``component.depends_on``),
    #: such as the table of a facets panel: they must hold too.
    requires: tuple = ()
    #: The ids of those nodes.
    depends: tuple = ()

    def visible(self, request, obj=None):
        """Whether the node exists for ``request``: every condition holds.

        ``obj`` is the object of a page about one object (``meta.parent``),
        which the conditions are evaluated with.
        """
        return all(evaluate_condition(cond, request, obj)
                   for cond in self.conditions + self.requires)


@dataclass
class ResolvedPage:
    document: dict
    root: ResolvedNode
    #: ``{node id: ResolvedNode}``.
    nodes: dict
    #: ``app.codename`` permissions ``meta.permissions`` asks to see the page.
    permissions: list
    hash: str
    preview: bool = False
    #: Whether the ``html`` nodes are templates and ``assets.js`` is served
    #: (see :func:`page_trust`).
    allow_templates: bool = False
    allow_js: bool = False
    #: The FormBuilds of ``document["forms"]``, by key.
    forms: dict = field(default_factory=dict)
    #: The :class:`ResolveContext` class it was resolved with; :func:`render`
    #: renders it with a new one of the same class.
    context_class: type = ResolveContext
    #: The :class:`ResolveContext` instance :func:`resolve` was given, if
    #: any: :func:`render` renders with a copy of it
    #: (:meth:`ResolveContext.copy_for`), so a subclass whose ``__init__``
    #: takes other arguments needs no ``context=`` again.
    context: object = field(default=None, repr=False)
    #: Filled on first use, under ``_lock``: a resolved page is cached and
    #: shared by the requests of every thread.
    _resolvers: dict = field(default_factory=dict, repr=False)
    _takes_parent: dict = field(default_factory=dict, repr=False)
    _lock: object = field(default_factory=threading.RLock, repr=False,
                          compare=False)

    @property
    def title(self):
        return self.document['meta']['title']

    @property
    def assets(self):
        return self.document.get('assets') or {}

    def walk(self, node=None):
        node = self.root if node is None else node
        yield node
        for child in node.children:
            yield from self.walk(child)

    def node_visible(self, node_id, request, obj=None):
        """Whether node ``node_id`` exists and its conditions hold for
        ``request`` (and ``obj``, the object of a page about one).

        Each node's conditions get the object only when its endpoints carry
        it (:meth:`condition_object`), and so do those of the nodes it
        depends on: the page and the API decide the same.
        """
        node = self.nodes.get(node_id)
        if node is None:
            return False
        own = self.condition_object(node_id, obj)
        if not all(evaluate_condition(cond, request, own)
                   for cond in node.conditions):
            return False
        return self.dependencies_hold(node, request, obj)

    def dependencies_hold(self, node, request, obj=None):
        """Whether the conditions of the nodes ``node`` depends on hold, each
        with the object it takes (:meth:`condition_object`)."""
        if not node.depends:
            own = self.condition_object(node.id, obj)
            return all(evaluate_condition(cond, request, own)
                       for cond in node.requires)
        for other_id in node.depends:
            other = self.nodes.get(other_id)
            if other is None:
                continue
            other_obj = self.condition_object(other_id, obj)
            if not all(evaluate_condition(cond, request, other_obj)
                       for cond in other.conditions):
                return False
        return True

    def takes_parent(self, node_id):
        """Whether the endpoints of node ``node_id`` carry the object of a
        page about one (a ``parent_pk`` in their URL, as inline tables and
        their facets do). A node without endpoints takes it too: only the
        page evaluates its conditions."""
        if node_id not in self._takes_parent:
            with self._lock:
                if node_id not in self._takes_parent:
                    node = self.nodes.get(node_id)
                    endpoints = node.component.endpoints(node.build) if node \
                        else []
                    self._takes_parent[node_id] = all(
                        PARENT_GROUP in endpoint.suffix for endpoint in endpoints)
        return self._takes_parent[node_id]

    def condition_object(self, node_id, obj):
        """The object the conditions of node ``node_id`` -- its own, its
        ancestors', and those of its columns and actions -- are evaluated
        with: ``obj``, the object of the page, only when its endpoints carry
        it (:meth:`takes_parent`). An endpoint without it could not check a
        condition about the object, so the page does not either."""
        if obj is None or not self.takes_parent(node_id):
            return None
        return obj

    def exposure(self, label):
        """The exposure of ``label`` as the context of the resolution sees
        it (``exposure(label, None)`` of its context, or of a new one of its
        ``context_class``)."""
        context = self.context
        if context is None:
            context = self.context_class(self.document, None, self.preview,
                                         allow_templates=self.allow_templates)
        return context.exposure(label, None)

    @property
    def parent_model(self):
        """The model of ``meta.parent``, for a page about one object, or
        ``None``."""
        parent = self.document['meta'].get('parent')
        found = self.exposure(parent.get('model')) if parent else None
        return found.model if found is not None else None

    def has_permission(self, user):
        return not self.permissions or (
            user is not None and user.has_perms(self.permissions))

    def endpoint_resolver(self, node_id):
        """A URL resolver over the endpoints of node ``node_id``, or ``None``.

        Built on first use and kept with the page, so the viewsets a component
        makes for its build are made once per resolution.
        """
        if node_id not in self._resolvers:
            with self._lock:
                if node_id not in self._resolvers:
                    self._resolvers[node_id] = self._build_resolver(node_id)
        return self._resolvers[node_id]

    def _build_resolver(self, node_id):
        node = self.nodes.get(node_id)
        endpoints = node.component.endpoints(node.build) if node else []
        if not endpoints:
            return None
        router = SimpleRouter()
        # The node's own '' endpoint last: its detail route would take
        # 'chart/' for a pk.
        for endpoint in sorted(endpoints, key=lambda item: item.suffix == ''):
            router.register(endpoint.suffix, endpoint.viewset,
                            basename=endpoint.basename)
        return URLResolver(RegexPattern(r'^'), router.urls)


# -- resolve ----------------------------------------------------------------------

def node_condition(node):
    """``(condition, path suffix)`` of a node: ``props.condition`` or
    ``meta.condition``; ``(None, None)`` without one."""
    for holder in ('props', 'meta'):
        values = node.get(holder)
        if isinstance(values, dict) and values.get('condition') is not None:
            return values['condition'], '.%s.condition' % holder
    return None, None


def _component_node(node):
    """The node as its component sees it: without ``props.condition``, which
    is the engine's, so a component's ``props_schema`` needs no room for it."""
    props = node.get('props')
    if isinstance(props, dict) and 'condition' in props:
        node = dict(node)
        node['props'] = {key: value for key, value in props.items()
                         if key != 'condition'}
    return node


def _check_condition(node, rctx, path):
    props, meta = node.get('props'), node.get('meta')
    if (isinstance(props, dict) and props.get('condition') is not None
            and isinstance(meta, dict) and meta.get('condition') is not None):
        rctx.error(path, _('a node has props.condition or meta.condition, not both'))
        return
    condition, suffix = node_condition(node)
    if condition is not None:
        rctx.errors.extend(validate_condition(condition, path + suffix))


def _check_tree(root, components, rctx):
    """Ids unique, known types, each node where its component allows it."""
    seen = {}
    for node, parent, path in format.walk(root):
        node_id = node.get('id')
        if node_id in seen:
            rctx.error(path + '.id', _('duplicate id %(id)r, also at %(path)s') % {
                'id': node_id, 'path': seen[node_id]})
        else:
            seen[node_id] = path
        component = components.get(node.get('type'))
        if component is None:
            rctx.error(path + '.type',
                       _('unknown component type %r') % (node.get('type'),))
            continue
        if parent is None:
            if component.parent_types != ():
                rctx.error(path + '.type', _('the root must be a page, not a %r')
                           % (component.type,))
        elif component.parent_types == ():
            rctx.error(path + '.type',
                       _('a %r can only be the root') % (component.type,))
        elif parent.get('type') not in component.parent_types:
            rctx.error(path + '.type', _('a %(type)r cannot go in a %(parent)r '
                                         '(only in %(allowed)s)') % {
                'type': component.type, 'parent': parent.get('type'),
                'allowed': ', '.join(component.parent_types)})
        if node.get('children') and not component.container:
            rctx.error(path + '.children', _('a %r cannot have children')
                       % (component.type,))
        _check_condition(node, rctx, path)
        for error in component.check_props(_component_node(node), path):
            rctx.errors.append(error)


def _check_permissions(perms, rctx, path):
    if perms:
        rctx.check_permissions(path, perms)


def _resolve_node(node, rctx, path, components, nodes, conditions=()):
    component = components[node['type']]
    build = component.resolve(_component_node(node), rctx, path)
    condition, _suffix = node_condition(node)
    if condition is not None:
        conditions = conditions + (condition,)
    resolved = ResolvedNode(node['id'], node['type'], path, component, build,
                            condition=condition, conditions=conditions)
    nodes[node['id']] = resolved
    for index, child in enumerate(node.get('children') or []):
        resolved.children.append(_resolve_node(
            child, rctx, '%s.children[%d]' % (path, index), components, nodes,
            conditions))
    return resolved


def _add_dependencies(nodes):
    """A node that works on other nodes -- ``component.depends_on(build)``,
    their ids -- exists only where they do: it gets their conditions."""
    for node in nodes.values():
        depends_on = getattr(node.component, 'depends_on', None)
        if depends_on is None:
            continue
        requires = []
        depends = []
        for other_id in depends_on(node.build) or ():
            other = nodes.get(other_id)
            if other is None:
                continue
            depends.append(other_id)
            for cond in other.conditions:
                if cond not in node.conditions and cond not in requires:
                    requires.append(cond)
        node.requires = tuple(requires)
        node.depends = tuple(depends)


def make_context(document, request=None, preview=False, *, context=None,
                 allow_templates=False, site=None):
    """The :class:`ResolveContext` a design is resolved or rendered with.

    ``context`` is ``None`` (a plain :class:`ResolveContext`), a subclass of
    it (instantiated here) or an instance, which is used as it is with
    ``document`` as its ``design``. ``site``, when given, is the Site of a
    context built here instead of the request's (an instance keeps its own).
    """
    if context is None:
        context = ResolveContext
    if isinstance(context, type):
        if not issubclass(context, ResolveContext):
            raise TypeError('context must be a ResolveContext or a subclass, not %r'
                            % (context,))
        kwargs = {'allow_templates': allow_templates}
        if site is not None:
            kwargs['site'] = site
        return context(document, request, preview, **kwargs)
    if not isinstance(context, ResolveContext):
        raise TypeError('context must be a ResolveContext or a subclass, not %r'
                        % (context,))
    context.design = document
    return context


def resolve(document, request=None, preview=False, *, allow_templates=False,
            allow_js=False, context=None, components=None, site=None):
    """``(ResolvedPage, [])`` for a valid design, ``(None, errors)`` otherwise.

    ``request`` is ``None`` when validating offline (``gtdesigns_publish``);
    ``preview`` makes querysets go empty, for the editor. ``allow_templates``
    and ``allow_js`` come from :func:`page_trust`: both default to the safe
    side.

    The hooks of whoever resolves designs another way (djgentelella-editor,
    an application builder):

    ``context``
        a :class:`ResolveContext` subclass, or an instance of one, whose
        hooks (``exposure``, ``check_permissions``, ``lookups``, ``form``,
        ``flow``...) every component asks. An instance gets the upgraded document as its
        ``design`` and keeps what it collected, errors included, so the
        caller can read it afterwards. Its ``request``, ``preview`` and
        ``allow_templates`` are its own: the arguments of the same name only
        build a context that is not given.
    ``components``
        ``{type: RuntimeComponent instance}`` instead of the registry's
        (:func:`djgentelella.designs.registry.get_components`).
    ``site``
        the Site the design is resolved for, by default the request's (none
        offline): what the design names that only exists in one Site -- a
        ``flow:`` row link to a flow published there -- is looked up in it.
        A ``context`` instance keeps its own.
    """
    try:
        document = format.upgrade(document)
    except format.UpgradeError as error:
        return None, [Error('$.schema_version', str(error))]
    errors = format.validate_envelope(document)
    if errors:
        return None, errors
    if document.get('kind', 'page') != 'page':
        return None, [Error('$.kind', _('only "page" designs can be served'))]

    components = dict(registry.get_components() if components is None
                      else components)
    rctx = make_context(document, request, preview, context=context,
                        allow_templates=allow_templates, site=site)
    rctx.components = components
    preview, allow_templates = rctx.preview, rctx.allow_templates
    _check_tree(document['root'], components, rctx)
    if rctx.errors:
        return None, rctx.errors

    # Every form, used or not: a design must not carry a form of a model it
    # could not use.
    forms = {key: rctx.form(key, '$.forms.' + key)
             for key in sorted(document.get('forms') or {})}
    parent = document['meta'].get('parent')
    if parent:
        rctx.model(parent['model'], '$.meta.parent.model')
    permissions = format.view_permissions(document)
    _check_permissions(permissions, rctx, '$.meta.permissions')

    nodes = {}
    root = _resolve_node(document['root'], rctx, '$.root', components, nodes)
    if rctx.errors:
        return None, rctx.errors
    _add_dependencies(nodes)
    return ResolvedPage(document, root, nodes, permissions,
                        format.document_hash(document), preview=preview,
                        allow_templates=allow_templates, allow_js=allow_js,
                        forms=forms, context_class=type(rctx),
                        context=context if isinstance(context, ResolveContext)
                        else None), []


# -- the cache by hash ---------------------------------------------------------------

_cache = OrderedDict()
_cache_lock = threading.Lock()
# (page pk, publisher id, updated_at, settings) -> (expires at, trust)
_trust_cache = OrderedDict()


def clear_cache():
    """Forget the resolved pages and the trust of their publishers."""
    with _cache_lock:
        _cache.clear()
        _trust_cache.clear()


def page_trust(page):
    """``(allow_templates, allow_js)`` for a Page.

    Each needs its setting (``GT_DESIGNS_ALLOW_TEMPLATES``,
    ``GT_DESIGNS_ALLOW_JS``) *and* a publisher -- ``page.updated_by`` -- who
    still holds ``gtdesigns.publish_template`` / ``gtdesigns.publish_js``.
    A page published from the command line without ``--user`` gets neither.
    """
    wants_templates, wants_js = conf.allow_templates(), conf.allow_js()
    if not (wants_templates or wants_js) or page.updated_by_id is None:
        return False, False
    user = page.updated_by
    if not user.is_active:
        return False, False
    return (wants_templates and user.has_perm('gtdesigns.publish_template'),
            wants_js and user.has_perm('gtdesigns.publish_js'))


def cached_page_trust(page):
    """:func:`page_trust`, kept in the process for ``GT_DESIGNS_TRUST_TTL``
    seconds by ``(page.pk, page.updated_by_id, page.updated_at)``.

    Saving the page or changing its publisher is a new key, so it takes
    effect at once; taking a permission away from the publisher, or
    deactivating them, takes effect within the TTL. ``0`` turns the cache off.
    A page that is not saved is never cached.
    """
    wants = (conf.allow_templates(), conf.allow_js())
    ttl = conf.trust_ttl()
    if not any(wants) or page.updated_by_id is None or page.pk is None or ttl <= 0:
        return page_trust(page)
    key = (page.pk, page.updated_by_id, page.updated_at, wants)
    now = time.monotonic()
    with _cache_lock:
        entry = _trust_cache.get(key)
        if entry is not None and entry[0] > now:
            return entry[1]
    trust = page_trust(page)
    with _cache_lock:
        _trust_cache[key] = (now + ttl, trust)
        _trust_cache.move_to_end(key)
        while len(_trust_cache) > max(conf.cache_size(), 1):
            _trust_cache.popitem(last=False)
    return trust


def resolve_page(page):
    """:func:`resolve` for a Page, cached in the process by ``page.hash``.

    The key also holds what the resolution depends on outside the document:
    the publisher's trust (:func:`cached_page_trust`), the generations of
    the component registry and of the exposed models, and the active
    language, which the errors and the labels of the builds are written in.
    ``page.document`` is read only when the cache misses, so the page may come
    with it deferred.

    A page of a Site is resolved for that Site (``resolve(..., site=)``), as
    :func:`~djgentelella.designs.publishing.publish` validated it: what only
    exists there -- a flow published in that Site -- is found. A global page
    is resolved without a Site, so it may only name global things. The Site
    is part of the key: the same document in two Sites is resolved twice.
    """
    registry.get_components()  # loading the registry changes its generation
    allow_templates, allow_js = cached_page_trust(page)
    key = (page.hash, page.site_id, allow_templates, allow_js,
           registry.generation(), exposure.generation(), get_language())
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    result = resolve(page.document, allow_templates=allow_templates,
                     allow_js=allow_js,
                     site=page.site if page.site_id is not None else None)
    if result[1]:
        logger.warning('Design page %s (%s) does not resolve: %s', page.pk,
                       page.path, '; '.join(str(error) for error in result[1]))
    with _cache_lock:
        _cache[key] = result
        while len(_cache) > max(conf.cache_size(), 1):
            _cache.popitem(last=False)
    return result


# -- render ---------------------------------------------------------------------

def _asset_url(url):
    """Absolute URLs and paths as they are; anything else is a static file."""
    if url.startswith(('/', 'http://', 'https://')):
        return url
    return static(url)


def _inline(code):
    """Code safe inside ``<style>``/``<script>``: no ``</`` can close the tag."""
    return mark_safe(code.replace('</', '<\\/').replace('<!--', '<\\!--'))


def _assets_css(assets, allow_js):
    """``assets.css``, cleaned unless the page may also serve ``assets.js``
    (see :mod:`djgentelella.designs.css`)."""
    css = assets.get('css') or ''
    return css if allow_js and isinstance(css, str) else clean_css(css)


def _visible(node, rctx, obj):
    resolved = rctx.resolved
    if resolved is None or obj is None:
        # The ancestors' conditions held already: only the node's own is
        # left, and those of the nodes it depends on.
        if node.condition is not None and not evaluate_condition(
                node.condition, rctx.request, obj):
            return False
        return all(evaluate_condition(cond, rctx.request, obj)
                   for cond in node.requires)
    if not resolved.takes_parent(node.id):
        # Its endpoints cannot check a condition about the object: all its
        # conditions, the ancestors' too, are evaluated without it, as they
        # will be when its endpoints are called.
        return resolved.node_visible(node.id, rctx.request, obj)
    if node.condition is not None and not evaluate_condition(
            node.condition, rctx.request, obj):
        return False
    return resolved.dependencies_hold(node, rctx.request, obj)


def _render_node(node, rctx, media, obj=None):
    if not _visible(node, rctx, obj):
        return ''
    children = mark_safe(''.join(
        _render_node(child, rctx, media, obj) for child in node.children))
    node_media = node.component.media(node.build, rctx) or {}
    for kind in ('css', 'js'):
        for url in node_media.get(kind, ()):
            url = _asset_url(url)
            if url not in media[kind]:
                media[kind].append(url)
    if node_media.get('inline_js'):
        media['inline_js'].append(node_media['inline_js'])
    return node.component.render(node.build, rctx, children)


def render(resolved, request, *, template_name=PAGE_TEMPLATE, extra_context=None,
           context=None):
    """The response for ``request`` of a resolved page.

    The page is rendered in ``gentelella/base.html`` (``base_template``, see
    :func:`djgentelella.designs.conf.base_template`): the nodes go in the
    ``content`` block, their media and ``assets.css`` in ``extra_css`` and
    ``js``; ``assets.js`` only when the page allows it.

    The conditions of a page about one object are evaluated with it,
    ``request.gtdesign_parent``, where the endpoints of the node can check
    them too (:meth:`ResolvedPage.condition_object`); the others without it.
    ``context`` is the :class:`ResolveContext` (class or instance) the
    components render with; by default a copy of the instance the page was
    resolved with (:meth:`ResolveContext.copy_for`) or else a new one of
    the class it was resolved with.
    """
    if context is None and resolved.context is not None:
        context = resolved.context.copy_for(request)
    rctx = make_context(resolved.document, request, resolved.preview,
                        context=context or resolved.context_class,
                        allow_templates=resolved.allow_templates)
    rctx.resolved = resolved
    media = {'css': [], 'js': [], 'inline_js': []}
    content = _render_node(resolved.root, rctx, media,
                           getattr(request, 'gtdesign_parent', None))
    assets = resolved.assets
    context = {
        'base_template': conf.base_template(),
        'design': resolved.document,
        'resolved': resolved,
        'title': resolved.title,
        'content': content,
        'media': media,
        'inline_js': _inline('\n'.join(media['inline_js'])),
        'assets_css': _inline(_assets_css(assets, resolved.allow_js)),
        'assets_js': _inline(assets.get('js') or '') if resolved.allow_js else '',
    }
    context.update(extra_context or {})
    return render_template(request, template_name, context)


class ObjectConditionResolver:
    """The endpoint resolver of a node of a page about one object: its
    conditions are evaluated once the URL is matched, with the object its
    ``parent_pk`` names -- or without one for an endpoint that takes none."""

    def __init__(self, resolver, resolved, node_id, request):
        self.resolver = resolver
        self.resolved = resolved
        self.node_id = node_id
        self.request = request

    def resolve(self, path):
        match = self.resolver.resolve(path)
        obj = None
        model = self.resolved.parent_model
        parent_pk = match.kwargs.get('parent_pk')
        if model is not None and parent_pk is not None and \
                self.resolved.takes_parent(self.node_id):
            try:
                obj = model._default_manager.filter(pk=parent_pk).first()
            except (ValueError, TypeError, DjangoValidationError):
                obj = None
        if not self.resolved.node_visible(self.node_id, self.request, obj):
            raise Resolver404({'path': path})
        return match


#: What the engine and the page view put in the context of a design page:
#: :func:`page_context` cannot replace it.
RESERVED_CONTEXT = ('design', 'resolved', 'title', 'content', 'media', 'inline_js',
                    'assets_css', 'assets_js', 'page', 'parent', 'is_preview')


def page_context(request, page):
    """What ``GT_DESIGNS_PAGE_CONTEXT`` adds to the context of ``page``.

    ``{}`` without the setting. The keys the page itself needs
    (:data:`RESERVED_CONTEXT`) are left out, so the hook can give the page a
    theme, ``breadcrumbs`` or a ``base_template`` but never its content.
    """
    hook = conf.page_context_hook()
    if hook is None:
        return {}
    extra = hook(request, page)
    if extra is None:
        return {}
    if not isinstance(extra, dict):
        raise ImproperlyConfigured('GT_DESIGNS_PAGE_CONTEXT must return a dict, not %s'
                                   % type(extra).__name__)
    ignored = sorted(key for key in extra if key in RESERVED_CONTEXT)
    if ignored:
        logger.warning('GT_DESIGNS_PAGE_CONTEXT cannot set %s: ignored',
                       ', '.join(ignored))
    return {key: value for key, value in extra.items()
            if key not in RESERVED_CONTEXT}


def node_endpoints(resolved, node_id, request):
    """The URL resolver of node ``node_id``'s endpoints for ``request``, or
    ``None``: a node hidden by its conditions, or by an ancestor's, serves
    none.

    On a page about one object (``meta.parent``) the conditions hold the
    object the endpoint's ``parent_pk`` names, as they do when the page is
    rendered; the check then waits for the URL to be matched.
    """
    if resolved.document['meta'].get('parent'):
        if node_id not in resolved.nodes:
            return None
        resolver = resolved.endpoint_resolver(node_id)
        if resolver is None:
            return None
        return ObjectConditionResolver(resolver, resolved, node_id, request)
    if not resolved.node_visible(node_id, request):
        return None
    return resolved.endpoint_resolver(node_id)


def render_errors(page, errors, request):
    """The page an editor of designs sees instead of a page that does not
    resolve: what is wrong with it, nothing of its content."""
    return render_template(request, 'gtdesigns/errors.html',
                           {'page': page, 'errors': errors}, status=503)
