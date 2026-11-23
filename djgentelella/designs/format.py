"""The design document: its envelope, its versions and how to upgrade them.

A design is the JSON djgentelella-editor writes to
``<app>/gtdesign/<slug>.json``::

    {"schema_version": 1, "app": "ventas", "slug": "clientes", "kind": "page",
     "meta": {"title": "...", "url": "clientes/", "url_name": "clientes",
              "permissions": {"view": ["ventas.view_cliente"]}},
     "assets": {"css": "", "js": ""},
     "forms": {"<key>": {"model": "ventas.Cliente", "fields": [...]}},
     "root": {"type": "page", "id": "page", "children": [...]}}

The document carries ``schema_version``. When the format changes, the version
goes up and a function in :data:`UPGRADES` takes a document from the previous
version to the new one. :func:`upgrade` runs them in order, so the rest of the
engine only ever sees the :data:`CURRENT` format.

:func:`validate_envelope` checks the shape (``schema_v1.json``); the props of
each node are checked by its component (:mod:`djgentelella.designs.components`).
"""

import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from django.utils.translation import gettext as _

from djgentelella.designs.jsonschema import Error, validate

SCHEMA_PATH = Path(__file__).resolve().parent / 'schema_v1.json'

#: The version this engine reads and writes.
CURRENT = 1

#: ``{version: function(document) -> document at version + 1}``. Each function
#: gets its own copy and may change it in place.
UPGRADES = {}

__all__ = ['CURRENT', 'UPGRADES', 'Error', 'UpgradeError', 'document_hash',
           'load_schema', 'normalize', 'upgrade', 'validate_envelope',
           'view_permissions', 'walk']


class UpgradeError(ValueError):
    pass


@lru_cache(maxsize=1)
def _schema_text():
    return SCHEMA_PATH.read_text(encoding='utf-8')


def load_schema():
    """The JSON Schema of the envelope, a fresh copy each call."""
    return json.loads(_schema_text())


def upgrade(document, current=None, upgrades=None):
    """``document`` at the :data:`CURRENT` version; the argument is not changed.

    A document without a usable ``schema_version`` is returned as is: that is
    for :func:`validate_envelope` to report. Raises :class:`UpgradeError` for a
    document newer than this engine, or a version nothing here can upgrade.
    """
    current = CURRENT if current is None else current
    upgrades = UPGRADES if upgrades is None else upgrades
    if not isinstance(document, dict):
        return document
    version = document.get('schema_version')
    if not isinstance(version, int) or isinstance(version, bool):
        return document
    if version > current:
        raise UpgradeError(_('schema_version %(version)d is newer than this '
                             'djgentelella (%(current)d): upgrade djgentelella.')
                           % {'version': version, 'current': current})
    while version < current:
        step = upgrades.get(version)
        if step is None:
            raise UpgradeError(_('no upgrade from schema_version %d.') % version)
        document = step(copy.deepcopy(document))
        version += 1
        document['schema_version'] = version
    return document


def validate_envelope(document):
    """The :class:`Error` list of the document's shape; empty means valid."""
    if not isinstance(document, dict):
        return [Error('$', _('a design must be a JSON object'))]
    return validate(document, load_schema())


def walk(node, path='$.root', parent=None):
    """Yield ``(node, parent, path)`` depth first, ``node`` included.

    Children that are not objects are skipped: :func:`validate_envelope`
    reports them.
    """
    yield node, parent, path
    children = node.get('children') if isinstance(node, dict) else None
    if isinstance(children, list):
        for index, child in enumerate(children):
            if isinstance(child, dict):
                yield from walk(child, '%s.children[%d]' % (path, index), node)


def normalize(document):
    """The canonical JSON text of a document: sorted keys, no whitespace."""
    return json.dumps(document, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False)


def document_hash(document):
    """sha256 of :func:`normalize`, the ``Page.hash`` the engine caches by."""
    return hashlib.sha256(normalize(document).encode('utf-8')).hexdigest()


def view_permissions(document):
    """The ``meta.permissions`` to see the page, as a list of ``app.codename``.

    ``{"view": [...]}`` is the editor's form; a plain list means the same.
    """
    meta = document.get('meta') if isinstance(document, dict) else None
    permissions = meta.get('permissions') if isinstance(meta, dict) else None
    if isinstance(permissions, dict):
        permissions = permissions.get('view')
    if not isinstance(permissions, list):
        return []
    return [perm for perm in permissions if isinstance(perm, str)]
