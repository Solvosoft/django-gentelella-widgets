"""The JSON Schema of flow definitions (``schema_v2.json``) and its validator.

The validator is the one of the design documents,
:func:`djgentelella.designs.jsonschema.validate` (a plain module: it works
without ``djgentelella.designs`` in ``INSTALLED_APPS``). Here it returns the
problems as ``"<path>: <problem>"`` strings, ``str()`` of its ``Error``.
"""

import json
from functools import lru_cache
from pathlib import Path

from djgentelella.designs import jsonschema

SCHEMA_PATH = Path(__file__).with_name('schema_v2.json')
#: The ``schema_version`` this djgentelella writes and reads.
CURRENT = 2


def validate(instance, schema, path='$', root=None):
    """Return a list of ``"<path>: <problem>"`` strings; empty means valid."""
    return [str(error) for error in jsonschema.validate(instance, schema, path, root)]


@lru_cache(maxsize=1)
def flow_schema():
    """``schema_v2.json``, parsed."""
    with open(SCHEMA_PATH, encoding='utf-8') as handle:
        return json.load(handle)


def validate_document(document):
    """The problems of a flow definition against ``schema_v2.json``."""
    return validate(document, flow_schema())
