"""The link of a :class:`~djgentelella.models.MenuItem`, as the menus build it.

:func:`item_url` is what the ``top_menu``, ``sidebar_menu`` and
``footer_sidebar_menu`` tags put in each ``href``, public so that other views
of the menu tree (breadcrumbs, a site map) link items the same way:

* ``is_reversed``: ``url_name`` reversed with ``reversed_args`` and
  ``reversed_kwargs``, whose values are read from the template context
  (``"literal"``, a plain word, or a dotted path such as ``request.user.pk``);
* ``is_widget``: ``''`` -- a widget draws its own markup;
* ``page:<path>``: the design page published at that path
  (:mod:`djgentelella.designs`, URL name ``gt-design-page``); the text as it
  is when that route does not exist (the app is not installed), so a menu
  that names a page never breaks the pages that draw it;
* anything else: ``url_name`` as it is (a path or an absolute URL).

:func:`menu_tree` is the menu of one Site loaded once per request -- every
item, its permissions and their content types in three queries --, which the
menu tags walk instead of querying each item and its children, and
:func:`visible_items` the items a user sees in it, for breadcrumbs or a site
map.

Menu widgets (an item with ``is_widget``) are classes the project declares:
:func:`register_menu_widget`, a class defined in the ``menu_widgets`` module
of an installed app, or a dotted path listed in ``settings.GT_MENU_WIDGETS``.
:func:`get_menu_widget` finds one by the ``url_name`` of its item and never
imports a path that is none of those, so whoever edits a menu item cannot make
the menu import and call any class of the project.
"""

import inspect
import logging
import threading
from importlib import import_module
from collections import defaultdict
from collections.abc import Mapping

from django.apps import apps
from django.contrib.sites.requests import RequestSite
from django.conf import settings
from django.db import router, transaction
from django.db.models import Prefetch, Q
from django.template.context import BaseContext
from django.urls import NoReverseMatch, reverse
from django.utils.module_loading import import_string
from django.utils.text import slugify
from django.utils.translation import gettext as _

from djgentelella.authorization import evaluate_condition, validate_condition
from djgentelella.autodiscover import autodiscover_once
from djgentelella.designs.jsonschema import Error
from djgentelella.sites import get_current_site, resolve_site, site_pk, site_q

__all__ = ['MAX_MENU_DEPTH', 'MENU_FIELDS', 'MENU_WIDGETS_MODULE', 'PAGE_PREFIX',
           'PLACEHOLDER_URL_NAMES', 'MenuTree', 'context_value', 'export_tree',
           'get_menu_widget', 'import_tree', 'is_menu_widget', 'item_permissions',
           'item_url', 'item_visible', 'menu_tree', 'menu_widget_name',
           'override_identity', 'register_menu_widget', 'registered_menu_widgets',
           'scope_items', 'validate_tree', 'visible_items']

logger = logging.getLogger(__name__)

#: The ``url_name`` prefix of an item that links a design page by its path.
PAGE_PREFIX = 'page:'

# url_names that do not name a page: items that only open a dropdown, or
# point nowhere yet, share them. They are no identity on their own.
PLACEHOLDER_URL_NAMES = frozenset(('', '/', '#'))

# Where menu_tree() keeps the tree of a request, keyed by Site id.
_REQUEST_ATTR = '_gt_menu_trees'


def _lookup(obj, name):
    """``obj.name`` -- called when it is callable -- or the key ``name`` of a
    template context or a dict; ``(found, value)``."""
    if hasattr(obj, name):
        value = getattr(obj, name)
        return True, value() if callable(value) else value
    if isinstance(obj, (Mapping, BaseContext)) and name in obj:
        return True, obj[name]
    return False, None


def context_value(text, context):
    """The value one of ``reversed_args`` / ``reversed_kwargs`` names.

    ``"text"`` is the literal text, a word without dots is itself, and a
    dotted path (``request.user.pk``) is read from ``context`` attribute by
    attribute (or key by key in a template context or a dict); ``None`` when
    a step is missing.
    """
    text = text.strip()
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    if '.' not in text:
        return text
    obj = context
    for name in text.split('.'):
        found, obj = _lookup(obj, name)
        if not found:
            return None
    return None if obj is context else obj


def _reverse_args(item, context):
    if not item.reversed_args:
        return None
    return [context_value(text, context) for text in item.reversed_args.split(',')]


def _reverse_kwargs(item, context):
    if not item.reversed_kwargs:
        return None
    kwargs = {}
    for text in item.reversed_kwargs.split(','):
        key, value = text.split(':')
        kwargs[key.strip()] = context_value(value, context)
    return kwargs


def _url(item, context):
    if item.is_reversed:
        return reverse(item.url_name, args=_reverse_args(item, context),
                       kwargs=_reverse_kwargs(item, context))
    if item.is_widget:
        return ''
    url_name = item.url_name or ''
    if url_name.startswith(PAGE_PREFIX):
        path = url_name[len(PAGE_PREFIX):].strip().strip('/')
        if not path:
            return ''
        try:
            return reverse('gt-design-page', args=[path])
        except NoReverseMatch:
            return url_name
    return url_name


def item_url(item, context=None, *, fail_silently=False):
    """The ``href`` of the menu item ``item`` (see the module docstring).

    ``context`` is the template context the menu is rendered in (or a dict,
    such as ``{'request': request}``); only reversed items read it.
    A reverse that fails raises ``NoReverseMatch`` -- a menu that links a
    view that is gone should be noticed --, unless ``fail_silently``, which
    returns ``''`` instead (as do ``reversed_kwargs`` that are not
    ``key:value`` pairs).
    """
    try:
        return _url(item, context if context is not None else {})
    except (NoReverseMatch, ValueError, TypeError):
        if fail_silently:
            return ''
        raise


def override_identity(item):
    """What a Site item must share with a global one to replace it.

    ``(url_name, category)``; when ``url_name`` is a placeholder (``''``,
    ``'/'``, ``'#'``) the ``title`` too, or one Site item with ``url_name='/'``
    would hide every global placeholder item of its level.
    """
    url_name = (item.url_name or '').strip()
    if url_name in PLACEHOLDER_URL_NAMES:
        return (url_name, item.category, item.title)
    return (url_name, item.category)


def scope_items(items, site):
    """The ``items`` of one level of the tree visible on ``site``, in order.

    Global items (``site=NULL``) and the Site's own ones; an item of the Site
    replaces the global one with the same :func:`override_identity`, children
    included. ``items`` is a list, already limited to those two kinds.
    """
    if site is None:
        return items
    overridden = {override_identity(i) for i in items if i.site_id is not None}
    return [i for i in items
            if i.site_id is not None or override_identity(i) not in overridden]


def item_permissions(item):
    """``['app_label.codename', ...]`` of ``item``: free when they were
    prefetched (as :func:`menu_tree` does), one query when not."""
    return ['%s.%s' % (p.content_type.app_label, p.codename)
            for p in item.permission.all()]


def item_visible(item, request):
    """Whether ``request.user`` may see ``item`` alone, not its ancestors: all
    of its permissions *and* its condition (:mod:`djgentelella.authorization`),
    when it has them."""
    perms = item_permissions(item)
    if perms and not request.user.has_perms(perms):
        return False
    return item.condition is None or evaluate_condition(item.condition, request)


class MenuTree:
    """Every menu item of one Site, loaded together.

    Three queries -- the items, their permissions, the content types of those
    -- however many items and levels there are; the tree is then walked in
    memory. Roots are ordered by ``position`` and children by ``id``, as the
    database returned them before.
    """

    def __init__(self, site=None):
        menu_item = apps.get_model('djgentelella', 'MenuItem')
        permission = apps.get_model('auth', 'Permission')
        self.site = site
        items = list(
            menu_item.objects.filter(site_q(site)).order_by('pk').prefetch_related(
                Prefetch('permission', queryset=permission.objects.select_related(
                    'content_type'))))
        self._children = defaultdict(list)
        for item in items:
            self._children[item.parent_id].append(item)

    def roots(self, category):
        """The root items of ``category`` visible on the Site, by position."""
        roots = sorted((i for i in self._children[None] if i.category == category),
                       key=lambda i: i.position)
        return scope_items(roots, self.site)

    def children(self, item):
        """The children of ``item`` visible on the Site."""
        return scope_items(self._children.get(item.pk, []), self.site)


def menu_tree(request=None, site=None):
    """The :class:`MenuTree` of ``site`` -- by default the Site of
    ``request`` --, built once per request and kept on it.

    So the menus of one page share three queries. An item created during the
    request shows from the next one.
    """
    if site is None:
        site = get_current_site(request)
    trees = getattr(request, _REQUEST_ATTR, None) if request is not None else None
    key = site_pk(site)
    if trees is not None and key in trees:
        return trees[key]
    tree = MenuTree(site)
    if request is not None:
        if trees is None:
            trees = {}
            try:
                setattr(request, _REQUEST_ATTR, trees)
            except AttributeError:
                return tree
        trees[key] = tree
    return tree


def visible_items(request, category, site=None):
    """``[(item, level), ...]``: the items of ``category`` the user of
    ``request`` sees, depth first, as the menus draw them.

    An item shows when it and all of its ancestors are visible
    (:func:`item_visible`) on the Site; ``level`` 0 is a root. Built on
    :func:`menu_tree`, so it costs no query once a menu of the page has been
    drawn.
    """
    tree = menu_tree(request, site)
    found = []

    def walk(items, level):
        for item in items:
            if item_visible(item, request):
                found.append((item, level))
                walk(tree.children(item), level + 1)

    walk(tree.roots(category), 0)
    return found


# -- menu widgets ----------------------------------------------------------------

#: The module of an installed app whose classes are menu widgets by convention.
MENU_WIDGETS_MODULE = 'menu_widgets'

# The widgets of djgentelella itself, registered when their module loads.
_BUILTIN_WIDGET_MODULES = ('djgentelella.menu_widgets.palette',
                           'djgentelella.notification.widgets')

_widgets = {}
_widgets_lock = threading.RLock()
_discovered = False
_warned = set()


def menu_widget_name(widget):
    """The ``url_name`` a menu item gives to name ``widget``: its dotted path."""
    return '%s.%s' % (widget.__module__, widget.__qualname__)


def register_menu_widget(widget=None, *, name=None):
    """Declare ``widget`` a menu widget, by its dotted path and by ``name``.

    Usable as ``@register_menu_widget`` or ``@register_menu_widget(name='x')``
    on the class. A widget is a class built with the item's context (``id``,
    ``item`` and the menu environment) whose ``render()`` returns its markup,
    and that may have ``render_js``, ``render_content``,
    ``render_external_html`` and, in the footer, ``get_title``, ``get_link``,
    ``get_icon`` and ``get_menu_item``.
    """
    def register(cls):
        with _widgets_lock:
            _widgets[menu_widget_name(cls)] = cls
            if name:
                _widgets[name] = cls
        return cls

    return register if widget is None else register(widget)


def _module_widgets(module):
    """The classes defined in ``module`` that look like a menu widget."""
    return [value for key, value in vars(module).items()
            if not key.startswith('_') and inspect.isclass(value)
            and value.__module__ == module.__name__
            and callable(getattr(value, 'render', None))]


def _discover():
    """Import djgentelella's widgets and the ``menu_widgets`` module of each
    installed app, once."""
    global _discovered
    if _discovered:
        return
    with _widgets_lock:
        if _discovered:
            return
        for path in _BUILTIN_WIDGET_MODULES:
            import_module(path)
        autodiscover_once(MENU_WIDGETS_MODULE)
        for config in apps.get_app_configs():
            module = getattr(config.module, MENU_WIDGETS_MODULE, None)
            if inspect.ismodule(module):
                for widget in _module_widgets(module):
                    register_menu_widget(widget)
        _discovered = True


def _setting_widgets():
    return tuple(getattr(settings, 'GT_MENU_WIDGETS', None) or ())


def registered_menu_widgets():
    """``{name: class}`` of every menu widget the project declares, those of
    ``GT_MENU_WIDGETS`` included."""
    _discover()
    with _widgets_lock:
        found = dict(_widgets)
    for path in _setting_widgets():
        if path not in found:
            try:
                found[path] = import_string(path)
            except ImportError:
                logger.warning('GT_MENU_WIDGETS names %r, which cannot be '
                               'imported.', path)
    return found


def is_menu_widget(name):
    """Whether ``name`` (the ``url_name`` of an item) is a declared menu
    widget; it never imports ``name`` unless the project listed it."""
    return get_menu_widget(name) is not None


def get_menu_widget(name):
    """The class of the menu widget ``name``, or ``None`` -- with a warning in
    the log, once per name -- when the project does not declare it."""
    name = (name or '').strip()
    _discover()
    with _widgets_lock:
        widget = _widgets.get(name)
    if widget is None and name in _setting_widgets():
        try:
            widget = import_string(name)
        except ImportError:
            widget = None
    if widget is None and name not in _warned:
        _warned.add(name)
        logger.warning(
            'The menu widget %r is not registered, so the menu does not draw '
            'it: register it with djgentelella.menu.register_menu_widget, '
            'move it to the menu_widgets module of its app or list it in '
            'GT_MENU_WIDGETS.', name)
    return widget


# -- exporting and importing a menu ------------------------------------------------

#: The fields of a menu item that an exported menu carries, besides its
#: ``permissions`` (``['app_label.codename', ...]``), its ``children`` and,
#: for a root of a Site item under a global one, ``global_parent``.
MENU_FIELDS = ('key', 'title', 'url_name', 'category', 'is_reversed',
               'reversed_kwargs', 'reversed_args', 'is_widget', 'icon',
               'only_icon', 'position', 'condition')
#: Deepest menu :func:`import_tree` takes.
MAX_MENU_DEPTH = 10

# name -> (accepted types, default when missing, longest text)
_FIELD_SPECS = {
    'key': ((str, type(None)), None, 100),
    'title': ((str,), None, 500),
    'url_name': ((str,), None, 500),
    'category': ((str,), 'main', 200),
    'is_reversed': ((bool,), False, None),
    'reversed_kwargs': ((str, type(None)), None, 500),
    'reversed_args': ((str, type(None)), None, 500),
    'is_widget': ((bool,), False, None),
    'icon': ((str, type(None)), None, 50),
    'only_icon': ((bool,), False, None),
    'position': ((int,), 0, None),
    'condition': ((dict, type(None)), None, None),
}
_PARENT_FIELDS = ('key', 'title', 'url_name', 'category')


def _menu_model():
    return apps.get_model('djgentelella', 'MenuItem')


def _scope(site):
    site_id = site_pk(site)
    if site_id is None:
        return Q(site__isnull=True)
    return Q(site_id=site_id)


def _permission_label(permission):
    return '%s.%s' % (permission.content_type.app_label, permission.codename)


def _parent_reference(item):
    return {field: getattr(item, field) for field in _PARENT_FIELDS}


def _is_site_scope(site):
    """Whether ``site`` names the menu of a Site rather than the global one.

    Unlike :func:`~djgentelella.sites.site_pk` it takes a Site not saved yet,
    so a menu can be validated before its Site exists."""
    return site is not None and not isinstance(site, RequestSite)


def export_tree(site=None, *, warnings=None):
    """The menu items of ``site`` (a Site, its id, or ``None``: the global
    items) as a list of trees, the format :func:`import_tree` reads.

    Each node has the :data:`MENU_FIELDS`, ``permissions`` and ``children``,
    roots and children in the order the menus draw them (``position``, then
    ``id``). A root of a Site under a global item names that parent in
    ``global_parent`` (``key``, ``title``, ``url_name``, ``category``); an
    item under an item of another Site is exported as a root. No pk travels:
    ``key`` is what names an item again on import.

    ``warnings``, a list, receives an
    :class:`~djgentelella.designs.jsonschema.Error` (with the path of the
    node in the data) for every item exported as a root although it had a
    parent the data cannot name: an item of another Site, or of a Site in
    the global menu. The value returned is the same with or without it.
    """
    permission = apps.get_model('auth', 'Permission')
    items = list(_menu_model().objects.filter(_scope(site)).select_related(
        'parent').prefetch_related(Prefetch(
            'permission', queryset=permission.objects.select_related(
                'content_type'))).order_by('position', 'pk'))
    ids = {item.pk for item in items}
    children = defaultdict(list)
    roots = []
    for item in items:
        if item.parent_id in ids:
            children[item.parent_id].append(item)
        else:
            roots.append(item)

    def node(item):
        data = {field: getattr(item, field) for field in MENU_FIELDS}
        data['permissions'] = sorted(_permission_label(perm)
                                     for perm in item.permission.all())
        data['children'] = [node(child) for child in children[item.pk]]
        parent = item.parent
        if item.parent_id not in ids and parent is not None and \
                parent.site_id is None and site_pk(site) is not None:
            data['global_parent'] = _parent_reference(parent)
        return data

    data = [node(item) for item in roots]
    if warnings is not None:
        for index, (item, exported) in enumerate(zip(roots, data)):
            if item.parent_id is not None and 'global_parent' not in exported:
                parent = item.parent
                warnings.append(Error('$[%d]' % index, _(
                    '"%(title)s" hangs from "%(parent)s" of another scope '
                    '(%(scope)s) and is exported as a root') % {
                        # A global parent is exported as global_parent.
                        'title': item.title, 'parent': parent.title,
                        'scope': parent.site.domain}))
    return data


def _find_permissions(labels):
    """``({label: Permission}, [labels that are none])``."""
    permission = apps.get_model('auth', 'Permission')
    query = Q(pk__in=[])
    for label in labels:
        app_label, _dot, codename = label.partition('.')
        query |= Q(content_type__app_label=app_label, codename=codename)
    found = {_permission_label(perm): perm for perm in
             permission.objects.filter(query).select_related('content_type')}
    return found, [label for label in labels if label not in found]


def _global_parent(reference):
    """The global item ``reference`` names: by ``key`` when it has one, else
    the first with its ``title``, ``url_name`` and ``category``."""
    items = _menu_model().objects.filter(site__isnull=True)
    if reference.get('key'):
        return items.filter(key=reference['key']).first()
    return items.filter(title=reference.get('title'),
                        url_name=reference.get('url_name'),
                        category=reference.get('category', 'main')).order_by(
        'pk').first()


def _check_node(node, path, depth, site, errors, keys):
    if not isinstance(node, dict):
        errors.append(Error(path, _('a menu item is an object')))
        return
    if depth > MAX_MENU_DEPTH:
        errors.append(Error(path, _('the menu is deeper than %d levels')
                            % MAX_MENU_DEPTH))
        return
    known = set(MENU_FIELDS) | {'permissions', 'children', 'global_parent'}
    for name in sorted(set(node) - known):
        errors.append(Error('%s.%s' % (path, name), _('unknown field')))
    # A title that is not empty; a url_name, empty or not (a dropdown).
    if not node.get('title'):
        errors.append(Error(path + '.title', _('required')))
    if 'url_name' not in node:
        errors.append(Error(path + '.url_name', _('required')))
    for name, (types, _default, longest) in _FIELD_SPECS.items():
        if name not in node:
            continue
        value = node[name]
        if not isinstance(value, types) or (bool not in types and
                                            isinstance(value, bool)):
            errors.append(Error('%s.%s' % (path, name), _('wrong type')))
        elif longest and isinstance(value, str) and len(value) > longest:
            errors.append(Error('%s.%s' % (path, name),
                                _('longer than %d characters') % longest))
    key = node.get('key')
    if isinstance(key, str) and key:
        if slugify(key) != key:
            errors.append(Error(path + '.key', _('a key is a slug: letters, '
                                                 'digits, - and _')))
        elif key in keys:
            errors.append(Error(path + '.key', _('the key %s is repeated') % key))
        keys.add(key)
    if isinstance(node.get('condition'), dict):
        errors.extend(validate_condition(node['condition'], path + '.condition'))
    if node.get('is_widget') is True and isinstance(node.get('url_name'), str) \
            and not is_menu_widget(node['url_name']):
        errors.append(Error(path + '.url_name', _(
            '%s is not a registered menu widget') % node['url_name']))
    permissions = node.get('permissions', [])
    if not isinstance(permissions, list) or not all(
            isinstance(label, str) for label in permissions):
        errors.append(Error(path + '.permissions',
                            _('a list of "app_label.codename"')))
    else:
        for label in _find_permissions(permissions)[1]:
            errors.append(Error(path + '.permissions',
                                _('no permission %s') % label))
    if 'global_parent' in node:
        reference = node['global_parent']
        if depth > 1 or not _is_site_scope(site):
            errors.append(Error(path + '.global_parent', _(
                'only a root of a Site menu hangs from a global item')))
        elif not isinstance(reference, dict) or _global_parent(reference) is None:
            errors.append(Error(path + '.global_parent', _(
                'there is no such global menu item')))
    children = node.get('children', [])
    if not isinstance(children, list):
        errors.append(Error(path + '.children', _('a list of menu items')))
        return
    for index, child in enumerate(children):
        _check_node(child, '%s.children[%d]' % (path, index), depth + 1, site,
                    errors, keys)


def validate_tree(data, site=None):
    """The :class:`~djgentelella.designs.jsonschema.Error` list of a menu in
    the format of :func:`export_tree`; empty means :func:`import_tree` takes
    it. Widget items must name a registered menu widget, permissions must
    exist and conditions be valid.

    ``site`` is a Site, its id or ``None`` (the global menu); a ``Site`` not
    saved yet is taken too, to check a menu before its Site is created
    (:func:`import_tree` needs it saved)."""
    if not isinstance(data, list):
        return [Error('$', _('a menu is a list of menu items'))]
    errors = []
    keys = set()
    for index, node in enumerate(data):
        _check_node(node, '$[%d]' % index, 1, site, errors, keys)
    return errors


def import_tree(data, site=None, *, replace=True):
    """Write the menu ``data`` (the format of :func:`export_tree`) in the
    scope of ``site`` (``None``: the global items). ``(roots, [])`` once
    written, ``(None, errors)`` -- nothing written -- when
    :func:`validate_tree` finds problems.

    An item whose ``key`` already names an item of that scope updates it in
    place (it keeps its pk); any other is created. With ``replace`` the items
    of the scope the data does not name are deleted, so the scope ends up
    with exactly that menu; without it they stay. The whole import is one
    transaction.
    """
    errors = validate_tree(data, site)
    if errors:
        return None, errors
    model = _menu_model()
    site = resolve_site(site)
    with transaction.atomic(using=router.db_for_write(model)):
        existing = {item.key: item for item in
                    model.objects.filter(_scope(site), key__isnull=False)}
        written = []

        def write(node, parent):
            if 'global_parent' in node:
                parent = _global_parent(node['global_parent'])
            item = existing.get(node.get('key')) if node.get('key') else None
            if item is None:
                item = model(site=site)
            for name, (_types, default, _longest) in _FIELD_SPECS.items():
                setattr(item, name, node.get(name, default))
            item.parent = parent
            item.save()
            written.append(item.pk)
            item.permission.set(_find_permissions(node.get('permissions', []))[0]
                                .values())
            for child in node.get('children', []):
                write(child, item)
            return item

        roots = [write(node, None) for node in data]
        if replace:
            model.objects.filter(_scope(site)).exclude(pk__in=written).delete()
    return roots, []
