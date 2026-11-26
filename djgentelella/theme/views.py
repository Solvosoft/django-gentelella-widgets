"""The theme roller page, the stylesheet of a theme and its logo."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.sites.models import Site
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET

from djgentelella.models import SiteTheme
from djgentelella.public import public_view
from djgentelella.sites import get_current_site
from djgentelella.theme import values
from djgentelella.theme.css import render_css
from djgentelella.theme.forms import SiteThemeForm

#: A versioned URL never changes its content: cached for a year.
LONG_CACHE = 'public, max-age=31536000, immutable'


def _cached(response, request, version):
    if request.GET.get('v') == str(version):
        response['Cache-Control'] = LONG_CACHE
    else:
        # An old or missing version: answer the current one, but not for long.
        response['Cache-Control'] = 'no-cache'
    response['ETag'] = '"gttheme-%s"' % version
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@public_view
@require_GET
def theme_css(request, pk):
    """The stylesheet of the theme ``pk``: public, like any stylesheet."""
    theme = get_object_or_404(SiteTheme, pk=pk)
    if request.headers.get('If-None-Match') == '"gttheme-%s"' % theme.version:
        return _cached(HttpResponse(status=304), request, theme.version)
    response = HttpResponse(render_css(theme), content_type='text/css; charset=utf-8')
    return _cached(response, request, theme.version)


@public_view
@require_GET
def theme_logo(request, pk):
    """The logo of the theme ``pk``, with the content type of its (validated)
    format."""
    theme = get_object_or_404(SiteTheme, pk=pk)
    content_type = values.logo_content_type(theme.logo.name) if theme.logo else None
    if content_type is None:
        raise Http404()
    try:
        handle = theme.logo.open('rb')
    except (FileNotFoundError, OSError):
        raise Http404() from None
    response = FileResponse(handle, content_type=content_type)
    response['Content-Disposition'] = 'inline'
    return _cached(response, request, theme.version)


def _scope(request):
    """``(site, value)``: the Site the roller edits (``?site=``), the request's
    by default; ``value`` is what goes back in ``?site=`` (``'global'``)."""
    raw = request.POST.get('site', request.GET.get('site'))
    if raw is None:
        site = get_current_site(request)
    elif raw in ('', 'global'):
        site = None
    else:
        try:
            site = Site.objects.filter(pk=int(raw)).first()
        except (TypeError, ValueError):
            site = None
        if site is None:
            raise Http404()
    return site, (str(site.pk) if site else 'global')


@login_required
@permission_required('djgentelella.change_sitetheme', raise_exception=True)
def theme_preview(request):
    """The CSS of the values being edited, for the live preview: the same
    writer as the saved stylesheet, so only valid values ever reach it."""
    data = {name: values.normalize_color(request.GET.get(name, ''))
            for name in values.COLORS}
    data['font'] = request.GET.get('font', '')
    radius = request.GET.get('border_radius', '')
    data['border_radius'] = int(radius) if radius.isdigit() else None
    response = HttpResponse(render_css(data), content_type='text/css; charset=utf-8')
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
@permission_required(['djgentelella.change_sitetheme', 'djgentelella.add_sitetheme'],
                     raise_exception=True)
def theme_roller(request):
    """Edit the theme of a Site (or the global one), with a live preview."""
    site, scope = _scope(request)
    theme = SiteTheme.objects.filter(site=site).first()
    here = '%s?%s' % (reverse('gt_theme_roller'), urlencode({'site': scope}))
    if request.method == 'POST' and request.POST.get('reset'):
        if theme is not None:
            theme.delete()
            messages.success(request, _('The theme was removed: the default '
                                        'one applies.'))
        return redirect(here)
    form = SiteThemeForm(request.POST or None, request.FILES or None,
                         instance=theme or SiteTheme(site=site))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Theme saved.'))
        return redirect(here)
    return render(request, 'gentelella/theme/roller.html', {
        'form': form, 'theme': theme, 'site': site, 'scope': scope,
        'sites': Site.objects.order_by('domain'),
        'preview_url': reverse('gt_theme_preview'),
        'gt_theme_preview': True,
        'fonts': values.FONTS,
    })
