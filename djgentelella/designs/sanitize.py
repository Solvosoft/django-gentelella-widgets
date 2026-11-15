"""HTML of a design, cleaned to an allow list before it reaches a page.

A design is data: whoever publishes one must not be able to run script in the
browser of whoever opens the page. :func:`clean_html` keeps the markup a page
body needs -- Bootstrap layout, text, tables, images, links -- and drops the
rest: ``<script>``, ``<style>``, ``<iframe>``, forms, every ``on*`` handler,
``javascript:`` URLs and the ``data-*`` attributes that are not Bootstrap's.
It runs on nh3 (the ``designs`` extra: ``pip install djgentelella[designs]``).
"""

from django.core.exceptions import ImproperlyConfigured

#: Tags kept; anything else is removed and its text kept.
TAGS = frozenset({
    'a', 'abbr', 'address', 'article', 'aside', 'b', 'blockquote', 'br',
    'caption', 'cite', 'code', 'col', 'colgroup', 'dd', 'del', 'details', 'div',
    'dl', 'dt', 'em', 'figcaption', 'figure', 'footer', 'h1', 'h2', 'h3', 'h4',
    'h5', 'h6', 'header', 'hr', 'i', 'img', 'ins', 'kbd', 'li', 'mark', 'nav',
    'ol', 'p', 'pre', 'q', 's', 'section', 'small', 'span', 'strong', 'sub',
    'summary', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead', 'time',
    'tr', 'u', 'ul',
})
#: Tags removed together with everything inside them.
CLEAN_CONTENT_TAGS = frozenset({'script', 'style', 'template', 'noscript'})
#: Attributes kept, per tag; ``'*'`` applies to every tag.
ATTRIBUTES = {
    '*': {'class', 'id', 'title', 'role', 'lang', 'dir', 'style'},
    'a': {'href', 'target'},
    'img': {'src', 'alt', 'width', 'height', 'loading'},
    'td': {'colspan', 'rowspan', 'headers'},
    'th': {'colspan', 'rowspan', 'headers', 'scope'},
    'col': {'span'},
    'colgroup': {'span'},
    'ol': {'start', 'reversed'},
    'time': {'datetime'},
    'details': {'open'},
}
#: ``aria-*`` is kept on every tag.
ATTRIBUTE_PREFIXES = frozenset({'aria-'})
#: The only ``data-*`` attributes kept, on every tag: the ones Bootstrap reads
#: to toggle, collapse, dismiss and slide (``data-bs-*`` and the older names).
#: Any other ``data-*`` could configure a widget the page initialises --
#: ``data-widget``, ``data-url``, ``data-gt-dynamic`` -- with values chosen by
#: the author of the design; so are ``data-bs-html``, ``data-bs-sanitize`` and
#: ``data-bs-template``, which let a tooltip or popover render markup.
DATA_ATTRIBUTES = frozenset({
    'data-bs-toggle', 'data-bs-target', 'data-bs-dismiss', 'data-bs-parent',
    'data-bs-placement', 'data-bs-slide', 'data-bs-slide-to', 'data-bs-ride',
    'data-bs-interval', 'data-bs-pause', 'data-bs-wrap', 'data-bs-keyboard',
    'data-bs-backdrop', 'data-bs-trigger', 'data-bs-title', 'data-bs-content',
    'data-bs-offset', 'data-bs-spy', 'data-bs-smooth-scroll',
    'data-toggle', 'data-target', 'data-dismiss', 'data-parent',
    'data-placement', 'data-slide', 'data-slide-to', 'data-ride',
})
URL_SCHEMES = frozenset({'http', 'https', 'mailto', 'tel'})
#: CSS properties kept in ``style``: layout and text, nothing that loads a URL.
STYLE_PROPERTIES = frozenset({
    'color', 'background-color', 'font-weight', 'font-style', 'font-size',
    'text-align', 'text-decoration', 'vertical-align', 'white-space',
    'width', 'max-width', 'min-width', 'height', 'max-height', 'min-height',
    'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
    'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'border', 'border-color', 'border-width', 'border-style', 'border-radius',
    'display', 'float', 'clear', 'gap', 'list-style-type',
})


def clean_html(html):
    """``html`` with only the allowed tags, attributes and URL schemes left."""
    try:
        # Optional dependency: the [designs] extra.
        import nh3  # noqa: PLC0415
    except ImportError:  # pragma: no cover - depends on the environment
        raise ImproperlyConfigured(
            'djgentelella.designs needs nh3 to clean the HTML of designs: '
            'pip install "djgentelella[designs]"') from None
    return nh3.clean(
        html,
        tags=set(TAGS),
        clean_content_tags=set(CLEAN_CONTENT_TAGS),
        attributes={tag: set(names) | (DATA_ATTRIBUTES if tag == '*' else set())
                    for tag, names in ATTRIBUTES.items()},
        generic_attribute_prefixes=set(ATTRIBUTE_PREFIXES),
        url_schemes=set(URL_SCHEMES),
        filter_style_properties=set(STYLE_PROPERTIES),
        link_rel='noopener noreferrer',
    )
