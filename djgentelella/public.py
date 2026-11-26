"""Views that anybody reaches, signed in or not, marked as such.

djgentelella's stylesheet of a theme, the logo, the manifest and service
worker of the PWA, the JavaScript catalog, the flags, the login and the
password reset are read by a browser before anybody signs in. A middleware of
a project that asks for a login (or for access to an application) on every
request lets them through by asking :func:`is_public_view` about the matched
view, instead of listing their URL names::

    from djgentelella.public import is_public_view

    class AccessMiddleware:
        def process_view(self, request, view_func, view_args, view_kwargs):
            if is_public_view(request.resolver_match):
                return None
            ...

A view of the project joins them with :func:`public_view` (a function) or
``gt_public = True`` (a class-based view or a DRF viewset).
"""

__all__ = ['PUBLIC_ATTRIBUTE', 'is_public_view', 'public_view']

#: The attribute that marks a view as public.
PUBLIC_ATTRIBUTE = 'gt_public'


def public_view(view):
    """Mark ``view`` (the callable a URL pattern names) as public; returns it.

    Apply it last (the outermost decorator, or around ``as_view()``): a
    decorator applied after it copies the mark with ``functools.wraps``, but
    one that builds a new function without it loses it.
    """
    setattr(view, PUBLIC_ATTRIBUTE, True)
    return view


def is_public_view(match):
    """Whether the view of ``match`` is public.

    ``match`` is a ``ResolverMatch`` (``request.resolver_match``, or what
    ``django.urls.resolve()`` returns) or the view callable itself. A view is
    public when the callable, its class-based view (``view_class``) or its DRF
    viewset (``cls``) has ``gt_public = True``. ``None`` is not public.
    """
    if match is None:
        return False
    view = getattr(match, 'func', match)
    for holder in (view, getattr(view, 'view_class', None),
                   getattr(view, 'cls', None)):
        if holder is not None and getattr(holder, PUBLIC_ATTRIBUTE, False) is True:
            return True
    return False
