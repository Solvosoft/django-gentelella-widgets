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
"""

from collections import defaultdict
from collections.abc import Mapping

from django.apps import apps
from django.db.models import Prefetch
from django.template.context import BaseContext
from django.urls import NoReverseMatch, reverse

from djgentelella.authorization import evaluate_condition
from djgentelella.sites import get_current_site, site_pk, site_q

__all__ = ['PAGE_PREFIX', 'PLACEHOLDER_URL_NAMES', 'MenuTree', 'context_value',
           'item_permissions', 'item_url', 'item_visible', 'menu_tree',
           'override_identity', 'scope_items', 'visible_items']

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
