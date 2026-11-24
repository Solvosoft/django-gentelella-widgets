"""``{% global_search_box %}``: the search box of the top bar.

Drawn by ``gentelella/app/top_navigation.html`` only when the global search
is on for the request (``GT_SEARCH_NAVBAR`` or the Site's ``global_search``
setting); ``{% global_search_box force=True %}`` draws it anyway, for a
project that places it elsewhere.
"""
from django import template

from djgentelella.search.base import search_setting
from djgentelella.search.views import navbar_enabled

register = template.Library()


@register.inclusion_tag('gentelella/search/navbar_box.html', takes_context=True)
def global_search_box(context, force=False):
    request = context.get('request')
    enabled = bool(force) or (request is not None and navbar_enabled(request))
    query = ''
    if enabled and request is not None:
        match = getattr(request, 'resolver_match', None)
        if match is not None and match.url_name == 'gt-search':
            query = request.GET.get('q', '')
    return {'enabled': enabled, 'query': query,
            'min_length': search_setting('MIN_LENGTH')}
