from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .core import Textarea, js_widget_name, update_kwargs


class MarkdownInput(Textarea):
    """A Markdown editor: a textarea with a small toolbar and a "Preview" tab.

    The preview is rendered by the server (``gtapis/markdown/preview/``,
    login required) through :func:`djgentelella.markdown.render_markdown`,
    which cleans the HTML; the browser never turns the text into markup. Show
    the saved text with ``{% load gtmarkdown %}{{ obj.text|markdown }}``.
    ``rows`` is the height of the textarea.
    """

    template_name = 'gentelella/widgets/markdown.html'

    def __init__(self, attrs=None, rows=8, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self),
                                  base_class='form-control gt-markdown-text ')
        super().__init__(attrs, extraskwargs=False)
        self.attrs['rows'] = str(rows)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['attrs']['data-preview-url'] = reverse(
            'gt-markdown-preview')
        context['texts'] = {'write': _('Write'), 'preview': _('Preview')}
        context['tools'] = [
            {'name': name, 'icon': icon, 'title': title}
            for name, icon, title in (
                ('bold', 'fa-bold', _('Bold')),
                ('italic', 'fa-italic', _('Italic')),
                ('heading', 'fa-header', _('Heading')),
                ('link', 'fa-link', _('Link')),
                ('list', 'fa-list-ul', _('List')),
                ('numbered', 'fa-list-ol', _('Numbered list')),
                ('quote', 'fa-quote-left', _('Quote')),
                ('code', 'fa-code', _('Code')),
            )]
        return context
