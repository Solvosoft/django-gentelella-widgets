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
"""

from collections.abc import Mapping

from django.template.context import BaseContext
from django.urls import NoReverseMatch, reverse

__all__ = ['PAGE_PREFIX', 'context_value', 'item_url']

#: The ``url_name`` prefix of an item that links a design page by its path.
PAGE_PREFIX = 'page:'


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
