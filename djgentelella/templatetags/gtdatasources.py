"""Tags of the data source widgets (``static/gentelella/js/base/gt_facets.js``).

::

    {% load gtdatasources %}
    {% gt_facet_chips 'demoapp.person' 'country,num_children' %}
    {% gt_datasource_export 'demoapp.person' %}
    {% gt_facets 'demoapp.person' 'country,num_children,born_date' %}
    <table id="people" class="table"></table>
    <script>
      gtCreateDataSourceTable('#people', '{% gt_datasource_url "demoapp.person" %}');
    </script>

Every widget over the same source (and ``group``) shares its filters; the
optional ``params`` is a base parameter document (a dict) they all start from.
"""
import json

from django import template
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from djgentelella.datasources.export import EXPORTERS, available_formats

register = template.Library()


@register.simple_tag
def gt_datasource_url(name, endpoint=''):
    """The url of a source (``endpoint=''``) or of one of its endpoints."""
    if endpoint:
        return reverse('gtdatasource-' + endpoint, args=[name])
    return reverse('gtdatasource', args=[name])


def _widget(widget, name, group, params, **attrs):
    extra = format_html_join('', ' data-{}="{}"',
                             [(key, value) for key, value in attrs.items() if value])
    if params:
        extra = format_html('{} data-params="{}"', extra, json.dumps(params))
    return format_html('<div data-widget="{}" data-url="{}" data-group="{}"{}></div>',
                       widget, gt_datasource_url(name), group or '', extra)


@register.simple_tag
def gt_facets(name, columns, group='', params=None):
    """The facets side panel over ``columns`` (comma separated)."""
    return _widget('GTFacets', name, group, params, columns=columns)


@register.simple_tag
def gt_facet_chips(name, columns, group='', params=None):
    """The smart filter chips over ``columns`` (comma separated)."""
    return _widget('GTFacetChips', name, group, params, columns=columns)


@register.simple_tag(takes_context=True)
def gt_datasource_export(context, name, formats=None, group='', params=None):
    """The export menu of a source.

    ``formats`` (comma separated) are the formats it offers; by default every
    format the request has (``export.available_formats``: the registered
    exporters and those of the resolvers for this request).
    """
    if formats is None:
        request = context.get('request')
        formats = ','.join(available_formats(request)) if request is not None \
            else ','.join(sorted(EXPORTERS))
    elif not isinstance(formats, str):
        formats = ','.join(formats)
    return _widget('GTDataSourceExport', name, group, params, formats=formats)
