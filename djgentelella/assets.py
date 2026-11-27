"""URLs of djgentelella's static files that change with each release.

A browser keeps a stylesheet or a script by its URL: after an upgrade it
would go on running the old file until its cache expires. The templates add
``?v={% get_version %}``; the code that builds a URL itself uses
:func:`versioned_static`, which adds the same parameter.
"""
from django.templatetags.static import static

from djgentelella import __version__


def versioned(url):
    """``url`` with ``v=<djgentelella version>`` in its query string."""
    if not url:
        return url
    return '%s%sv=%s' % (url, '&' if '?' in url else '?', __version__)


def versioned_static(path):
    """The static URL of ``path`` with the djgentelella version."""
    return versioned(static(path))
