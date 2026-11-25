from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from djgentelella.markdown import max_length, render_markdown


@login_required
@require_POST
def markdown_preview_view(request):
    """The preview of ``MarkdownInput``: ``{"html": ...}`` for the posted
    ``text``, cleaned like everything :func:`render_markdown` returns."""
    text = request.POST.get('text', '')
    if len(text) > max_length():
        return JsonResponse({'error': _('The text is too long to preview.')},
                            status=413)
    try:
        html = render_markdown(text)
    except ImproperlyConfigured:
        return JsonResponse({'error': _('Markdown is not installed.')}, status=501)
    return JsonResponse({'html': str(html)})
