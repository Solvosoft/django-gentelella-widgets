"""Markdown to HTML that is safe to put in a page.

The text of a user is never marked safe: it is converted with Python-Markdown
and the result is cleaned by :func:`djgentelella.designs.sanitize.clean_html`
(nh3), the allow list of the design pages -- no ``<script>``, no ``on*``
handlers, no ``javascript:`` links. Only that cleaned output is marked safe.

Both libraries are optional (``pip install "djgentelella[markdown]"``) and
imported on use: djgentelella imports without them.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.safestring import mark_safe

from djgentelella.designs.sanitize import clean_html

#: Python-Markdown extensions: tables, fenced code, footnotes... and lists
#: that do not mix their markers.
EXTENSIONS = ['extra', 'sane_lists']


def max_length():
    """``GT_MARKDOWN_MAX_LENGTH``: the longest text the preview renders."""
    return getattr(settings, 'GT_MARKDOWN_MAX_LENGTH', 100000)


def render_markdown(text):
    """The cleaned HTML of the Markdown ``text``, as a safe string."""
    try:
        # Optional dependency: the [markdown] extra.
        import markdown  # noqa: PLC0415
    except ImportError:  # pragma: no cover - depends on the environment
        raise ImproperlyConfigured(
            'Markdown needs Python-Markdown and nh3: '
            'pip install "djgentelella[markdown]"') from None
    html = markdown.markdown(str(text or ''), extensions=EXTENSIONS,
                             output_format='html')
    # Safe because nh3 cleaned it: never the text of the user as is.
    return mark_safe(clean_html(html))
