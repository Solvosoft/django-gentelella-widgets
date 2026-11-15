"""A small JSON Schema validator: the subset the design documents use.

Moved from djgentelella-editor (``gteditor.jsonschema``), which imports it from
here. Written instead of depending on ``jsonschema`` to keep the engine free of
runtime dependencies. Supported keywords: ``type`` (one or a list),
``properties``, ``required``, ``additionalProperties`` (boolean or schema),
``items``, ``enum``, ``const``, ``pattern``, ``minLength``, ``minimum``,
``maximum``, ``minItems``, ``$ref`` (``#/$defs/<name>`` only) and ``$defs``.
Anything else in a schema is ignored, so a schema written for a full validator
-- the ``x-widget`` hints of the editor included -- still loads here.

Problems are reported as :class:`Error`, a ``(path, message)`` tuple.
"""

import re
from collections import namedtuple


class Error(namedtuple('Error', 'path message')):
    """One problem of a document: where (``$.root.children[0].props``) and what."""

    __slots__ = ()

    def __str__(self):
        return '%s: %s' % (self.path, self.message)


TYPES = {
    'object': lambda value: isinstance(value, dict),
    'array': lambda value: isinstance(value, list),
    'string': lambda value: isinstance(value, str),
    'boolean': lambda value: isinstance(value, bool),
    'null': lambda value: value is None,
    # bool is an int in Python, but not a number in JSON.
    'integer': lambda value: isinstance(value, int) and not isinstance(value, bool),
    'number': lambda value: (isinstance(value, (int, float))
                             and not isinstance(value, bool)),
}


def resolve_ref(ref, root):
    prefix = '#/$defs/'
    if not ref.startswith(prefix):
        raise ValueError('Only local "#/$defs/..." references are supported: %s' % ref)
    return root['$defs'][ref[len(prefix):]]


def validate(value, schema, path='$', root=None):
    """Return a list of :class:`Error`; empty means valid."""
    root = schema if root is None else root
    if '$ref' in schema:
        return validate(value, resolve_ref(schema['$ref'], root), path, root)

    errors = []
    expected = schema.get('type')
    if expected is not None:
        names = expected if isinstance(expected, list) else [expected]
        if not any(TYPES[name](value) for name in names):
            return [Error(path, 'expected %s, got %s' % (
                ' or '.join(names), type(value).__name__))]

    if 'const' in schema and value != schema['const']:
        errors.append(Error(path, 'must be %r' % (schema['const'],)))
    if 'enum' in schema and value not in schema['enum']:
        errors.append(Error(path, '%r is not one of %s' % (
            value, ', '.join(repr(item) for item in schema['enum']))))

    if isinstance(value, str):
        if 'minLength' in schema and len(value) < schema['minLength']:
            errors.append(Error(path, 'shorter than %d' % schema['minLength']))
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            errors.append(Error(path, '%r does not match %s' % (
                value, schema['pattern'])))

    if TYPES['number'](value):
        if 'minimum' in schema and value < schema['minimum']:
            errors.append(Error(path, 'less than %s' % schema['minimum']))
        if 'maximum' in schema and value > schema['maximum']:
            errors.append(Error(path, 'greater than %s' % schema['maximum']))

    if isinstance(value, list):
        if 'minItems' in schema and len(value) < schema['minItems']:
            errors.append(Error(path, 'fewer than %d items' % schema['minItems']))
        if 'items' in schema:
            for index, item in enumerate(value):
                errors += validate(item, schema['items'],
                                   '%s[%d]' % (path, index), root)

    if isinstance(value, dict):
        for name in schema.get('required', []):
            if name not in value:
                errors.append(Error(path, 'missing required %r' % name))
        properties = schema.get('properties', {})
        additional = schema.get('additionalProperties', True)
        for name, item in value.items():
            child = '%s.%s' % (path, name)
            if name in properties:
                errors += validate(item, properties[name], child, root)
            elif additional is False:
                errors.append(Error(child, 'unexpected property'))
            elif isinstance(additional, dict):
                errors += validate(item, additional, child, root)
    return errors
