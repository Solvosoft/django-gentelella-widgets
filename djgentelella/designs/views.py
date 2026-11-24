"""The catch-all page view and the router of node endpoints."""

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.urls import Resolver404
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt

from djgentelella.designs import conf, engine
from djgentelella.designs.models import Page, normalize_path
from djgentelella.sites import get_current_site, site_q

CHANGE_PERMISSION = 'gtdesigns.change_page'


class Refused(Exception):
    """Why a request cannot see a page: ``status`` is 401, 403 or 404."""

    def __init__(self, status):
        self.status = status
        super().__init__(status)


def can_preview(user):
    return user is not None and user.has_perm(CHANGE_PERMISSION)


def check_access(request, page, resolved=None):
    """Raise :class:`Refused` unless ``request.user`` may see ``page``.

    An unpublished page does not exist for whoever lacks
    ``gtdesigns.change_page``. Then the page's permissions, the M2M and
    ``meta.permissions``; and a signed-in user even without any, unless
    ``GT_DESIGNS_LOGIN_REQUIRED`` is off.
    """
    user = request.user
    if not page.is_published and not can_preview(user):
        raise Refused(404)
    perms = set(page.required_permissions())
    if resolved is not None:
        perms.update(resolved.permissions)
    if (perms or conf.login_required()) and not user.is_authenticated:
        raise Refused(401)
    if perms and not user.has_perms(sorted(perms)):
        raise Refused(403)


def served_pages():
    """Pages as a request serves them: with their publisher, whose trust
    :func:`~djgentelella.designs.engine.resolve_page` checks, and without the
    document, which it reads only when its cache misses."""
    return Page.objects.select_related('updated_by').defer('document')


def find_page(path, site):
    """``(page, parent_pk)`` of a page URL.

    The page at ``path``, or -- for a page about one object (``meta.parent``)
    -- the page at ``path`` without its last segment, which is then the pk
    of the parent object.
    """
    page = served_pages().find(path, site)
    if page is not None:
        return page, None
    head, _slash, tail = normalize_path(path).rpartition('/')
    if head and tail:
        # Its document says whether it takes a parent: loaded with the page.
        page = Page.objects.select_related('updated_by').find(head, site)
        if page is not None and isinstance(page.document, dict) and \
                (page.document.get('meta') or {}).get('parent'):
            return page, tail
    return None, None


def parent_object(request, resolved, parent_pk):
    """The object a page with ``meta.parent`` is about; 404 without one, 403
    without the view permissions of its model."""
    parent = resolved.document['meta'].get('parent')
    if not parent:
        return None
    found = resolved.exposure(parent['model'])
    if parent_pk is None or found is None:
        raise Http404(_('No page at this path.'))
    if not request.user.has_perms(found.permissions('view')):
        raise PermissionDenied
    try:
        obj = found.model._default_manager.filter(pk=parent_pk).first()
    except (ValueError, TypeError, ValidationError):
        obj = None
    if obj is None:
        raise Http404(_('No page at this path.'))
    return obj


def design_page(request, path):
    page, parent_pk = find_page(path, get_current_site(request))
    if page is None:
        raise Http404(_('No page at this path.'))
    resolved, errors = engine.resolve_page(page)
    try:
        check_access(request, page, resolved)
    except Refused as refused:
        if refused.status == 401:
            return redirect_to_login(request.get_full_path())
        if refused.status == 403:
            raise PermissionDenied
        raise Http404(_('No page at this path.')) from None
    if errors:
        if not can_preview(request.user):
            raise Http404(_('No page at this path.'))
        return engine.render_errors(page, errors, request)
    parent = parent_object(request, resolved, parent_pk)
    # What the components of the page read while rendering: the page (the
    # URLs of their endpoints) and the object it is about.
    request.gtdesign_page = page
    request.gtdesign_parent = parent
    # What mounts the page (GT_DESIGNS_PAGE_CONTEXT): its theme, breadcrumbs...
    extra_context = engine.page_context(request, page)
    extra_context.update({'page': page, 'parent': parent,
                          'is_preview': not page.is_published})
    return engine.render(resolved, request, extra_context=extra_context)


@csrf_exempt  # the viewsets do their own CSRF check (SessionAuthentication)
def design_endpoint(request, page_id, node_id, rest=''):
    """Dispatch ``gtapis/designs/<page>/<node>/<rest>`` to the node's viewset.

    The page is the one the Site would serve at its path (the Site rule): a
    page of another Site is not found, nor a global one that a page of the
    current Site overrides at the same path.
    """
    site = get_current_site(request)
    pages = served_pages().filter(site_q(site), pk=page_id)
    if site is not None:
        shadowed = Page.objects.filter(site=site).values('path')
        pages = pages.exclude(Q(site__isnull=True) & Q(path__in=shadowed))
    page = pages.first()
    if page is None:
        return JsonResponse({'detail': _('Not found.')}, status=404)
    resolved, errors = engine.resolve_page(page)
    try:
        check_access(request, page, resolved)
    except Refused as refused:
        status = 404 if refused.status == 404 else 403
        return JsonResponse({'detail': _('Not found.') if status == 404 else
                             _('You do not have permission to perform this action.')},
                            status=status)
    if errors:
        return JsonResponse({'detail': _('Not found.')}, status=404)
    resolver = engine.node_endpoints(resolved, node_id, request)
    if resolver is None:
        return JsonResponse({'detail': _('Not found.')}, status=404)
    try:
        match = resolver.resolve(rest)
    except Resolver404:
        return JsonResponse({'detail': _('Not found.')}, status=404)
    request.gtdesign_page = page
    request.gtdesign_resolved = resolved
    request.gtdesign_node = resolved.nodes[node_id]
    request.gtdesign_build = resolved.nodes[node_id].build
    return match.func(request, *match.args, **match.kwargs)
