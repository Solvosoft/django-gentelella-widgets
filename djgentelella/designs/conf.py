"""Settings of djgentelella.designs, read on each use so tests can override them.

``GT_DESIGN_COMPONENTS``
    Dotted paths of :class:`~djgentelella.designs.components.RuntimeComponent`
    subclasses, registered after the ``gtdesigns.py`` modules: a ``type`` here
    replaces the one registered before.
``GT_DESIGNS_ALLOW_TEMPLATES`` (``False``)
    Lets the ``html`` component be a Django template, when the page was
    published by a user with ``gtdesigns.publish_template``.
``GT_DESIGNS_ALLOW_JS`` (``False``)
    Lets ``assets.js`` reach the page, when the page was published by a user
    with ``gtdesigns.publish_js``.
``GT_DESIGNS_LOGIN_REQUIRED`` (``True``)
    Whether a page without permissions still needs a signed-in user.
``GT_DESIGNS_CACHE_SIZE`` (``128``)
    How many resolved pages each process keeps, by ``Page.hash``.
``GT_DESIGNS_BASE_TEMPLATE`` (``'gentelella/base.html'``)
    The template ``gtdesigns/page.html`` extends.
``GT_DESIGNS_PAGE_CONTEXT`` (``None``)
    A callable ``(request, page) -> dict``, or its dotted path, whose result
    is added to the context of every design page served: the theme and the
    breadcrumbs of whatever mounts the pages (an application, a site), or a
    ``base_template`` of its own.
"""

from django.conf import settings
from django.utils.module_loading import import_string


def components():
    return list(getattr(settings, 'GT_DESIGN_COMPONENTS', []))


def allow_templates():
    return bool(getattr(settings, 'GT_DESIGNS_ALLOW_TEMPLATES', False))


def allow_js():
    return bool(getattr(settings, 'GT_DESIGNS_ALLOW_JS', False))


def login_required():
    return bool(getattr(settings, 'GT_DESIGNS_LOGIN_REQUIRED', True))


def cache_size():
    return int(getattr(settings, 'GT_DESIGNS_CACHE_SIZE', 128))


def base_template():
    return getattr(settings, 'GT_DESIGNS_BASE_TEMPLATE', None) or 'gentelella/base.html'


def page_context_hook():
    """The ``GT_DESIGNS_PAGE_CONTEXT`` callable, or ``None``."""
    hook = getattr(settings, 'GT_DESIGNS_PAGE_CONTEXT', None)
    if isinstance(hook, str):
        hook = import_string(hook)
    return hook
