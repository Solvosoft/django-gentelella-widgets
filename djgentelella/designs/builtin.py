"""The structural components: ``page``, ``row``, ``col`` and ``html``.

They behave like djgentelella-editor's ``PageSpec``, ``RowSpec``, ``ColSpec``
and ``HtmlSpec``, but render final HTML instead of template source. The
components with data (tables, charts, stats) are in their own modules.
"""

from dataclasses import dataclass

from django.template import Context, Template, TemplateSyntaxError
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from djgentelella.designs.components import NodeBuild, RuntimeComponent
from djgentelella.designs.sanitize import clean_html

__all__ = ['BUILTIN_COMPONENTS', 'ColComponent', 'HtmlBuild', 'HtmlComponent',
           'PageComponent', 'RowComponent']


class PageComponent(RuntimeComponent):
    type = 'page'
    label = 'Page'
    icon = 'fa fa-file-o'
    container = True
    parent_types = ()

    def render(self, build, rctx, children):
        return format_html('<div class="gtdesign-page" data-gtdesign="{}">{}</div>',
                           rctx.design.get('slug', build.id), children)


class RowComponent(RuntimeComponent):
    type = 'row'
    label = 'Row'
    icon = 'fa fa-columns'
    container = True
    parent_types = ('page', 'col')

    def render(self, build, rctx, children):
        return format_html('<div class="row" data-gtdesign="{}">{}</div>',
                           build.id, children)


class ColComponent(RuntimeComponent):
    type = 'col'
    label = 'Column'
    icon = 'fa fa-square-o'
    container = True
    parent_types = ('row',)
    props_schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {'width': {'type': 'integer', 'minimum': 1, 'maximum': 12,
                                 'title': 'Width (1-12, empty = auto)'}},
    }
    default_props = {'width': 12}

    def render(self, build, rctx, children):
        width = build.props.get('width')
        css = 'col-md-%d' % width if width else 'col'
        return format_html('<div class="{}" data-gtdesign="{}">{}</div>',
                           css, build.id, children)


@dataclass
class HtmlBuild(NodeBuild):
    #: The cleaned markup, or the template source in template mode.
    html: str = ''
    #: A compiled Django template: only for a trusted publisher (template mode).
    template: object = None


class HtmlComponent(RuntimeComponent):
    """Free markup, cleaned to an allow list (:mod:`~djgentelella.designs.sanitize`).

    It is **not** a Django template: ``{% ... %}`` and ``{{ ... }}`` stay
    text. With ``GT_DESIGNS_ALLOW_TEMPLATES`` and a page published by a user
    with ``gtdesigns.publish_template`` it is rendered as a template (with
    ``request`` and ``user`` in its context), and the result is cleaned all
    the same.
    """

    type = 'html'
    label = 'HTML'
    icon = 'fa fa-code'
    props_schema = {
        'type': 'object',
        'required': ['html'],
        'additionalProperties': False,
        'properties': {'html': {'type': 'string', 'x-widget': 'textarea',
                                'title': 'HTML'}},
    }
    default_props = {'html': '<p>New text</p>'}

    def resolve(self, node, rctx, path):
        props = dict(node.get('props') or {})
        source = props.get('html', '')
        build = HtmlBuild(node['id'], node['type'], props)
        if rctx.allow_templates:
            try:
                build.template = Template(source)
            except TemplateSyntaxError as error:
                rctx.error(path + '.props.html',
                           'not a valid Django template: %s' % error)
            build.html = source
        else:
            build.html = clean_html(source)
        return build

    def render(self, build, rctx, children):
        if build.template is not None:
            context = Context({'request': rctx.request, 'user': rctx.user},
                              autoescape=True)
            markup = clean_html(build.template.render(context))
        else:
            markup = build.html
        return format_html('<div data-gtdesign="{}">{}</div>',
                           build.id, mark_safe(markup))


BUILTIN_COMPONENTS = [PageComponent, RowComponent, ColComponent, HtmlComponent]
