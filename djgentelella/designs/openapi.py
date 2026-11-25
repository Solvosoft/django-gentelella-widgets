"""What the endpoints of a design read besides their serializers, described
for OpenAPI without depending on any generator.

Each viewset of :mod:`djgentelella.designs` (and the mixins code generated
from a design uses) declares ``openapi_parameters``: ``{action: [name]}``,
``'*'`` for every action, with names from :data:`PARAMETERS`. A subclass
adds to what its bases declare. :func:`openapi_parameters` gathers them as
OpenAPI parameter objects, so a schema generator -- djgentelella-editor's,
drf-spectacular's ``get_override_parameters``, a project's own -- describes
the C4 ``params`` document, ``gtfilters`` or ``bbox`` the same way::

    from djgentelella.designs.openapi import openapi_parameters
    from drf_spectacular.utils import OpenApiParameter

    def get_override_parameters(self):
        return [OpenApiParameter(item['name'], str, item['in'],
                                 description=item['description'])
                for item in openapi_parameters(self.view.__class__,
                                               self.view.action)]
"""

__all__ = ['PARAMETERS', 'openapi_parameters']

_QUERY_JSON = ('A JSON document of djgentelella.datasources.query (filters, '
               'search, ordering, columns...).')

#: ``{name: OpenAPI parameter object}``.
PARAMETERS = {
    'params': {'name': 'params', 'in': 'query', 'required': False,
               'description': _QUERY_JSON, 'schema': {'type': 'string'}},
    'gtfilters': {'name': 'gtfilters', 'in': 'query', 'required': False,
                  'description': 'A JSON list of filters of the query document, '
                                 'set by a facets panel.',
                  'schema': {'type': 'string'}},
    'search': {'name': 'search', 'in': 'query', 'required': False,
               'description': 'Text searched in the searchable columns.',
               'schema': {'type': 'string'}},
    'ordering': {'name': 'ordering', 'in': 'query', 'required': False,
                 'description': 'A column, with - for descending order.',
                 'schema': {'type': 'string'}},
    'columns': {'name': 'columns', 'in': 'query', 'required': False,
                'description': 'Comma separated columns to count.',
                'schema': {'type': 'string'}},
    'draw': {'name': 'draw', 'in': 'query', 'required': False,
             'description': 'The DataTables draw counter, echoed back.',
             'schema': {'type': 'integer'}},
    'offset': {'name': 'offset', 'in': 'query', 'required': False,
               'description': 'Rows to skip.', 'schema': {'type': 'integer'}},
    'limit': {'name': 'limit', 'in': 'query', 'required': False,
              'description': 'Rows of the page.', 'schema': {'type': 'integer'}},
    'start': {'name': 'start', 'in': 'query', 'required': False,
              'description': 'ISO date or datetime: the first moment shown.',
              'schema': {'type': 'string'}},
    'end': {'name': 'end', 'in': 'query', 'required': False,
            'description': 'ISO date or datetime: the last moment shown.',
            'schema': {'type': 'string'}},
    'bbox': {'name': 'bbox', 'in': 'query', 'required': False,
             'description': 'west,south,east,north of the visible map.',
             'schema': {'type': 'string'}},
    'parent': {'name': 'parent', 'in': 'query', 'required': False,
               'description': 'The node whose children are listed (empty: the '
                              'roots).', 'schema': {'type': 'string'}},
    'cursor': {'name': 'cursor', 'in': 'query', 'required': False,
               'description': 'Where the previous page ended.',
               'schema': {'type': 'string'}},
    'from': {'name': 'from', 'in': 'query', 'required': False,
             'description': 'ISO date: the first moment of the timeline.',
             'schema': {'type': 'string'}},
    'to': {'name': 'to', 'in': 'query', 'required': False,
           'description': 'ISO date: the last moment of the timeline.',
           'schema': {'type': 'string'}},
    'page': {'name': 'page', 'in': 'query', 'required': False,
             'description': 'Page number.', 'schema': {'type': 'integer'}},
    'page_size': {'name': 'page_size', 'in': 'query', 'required': False,
                  'description': 'Rows of the page.', 'schema': {'type': 'integer'}},
}


def openapi_parameters(viewset, action=None):
    """The OpenAPI parameter objects of ``action`` of ``viewset`` (a class or
    an instance): what ``openapi_parameters`` of it and its bases declare for
    the action and for ``'*'``, each once, in declaration order (bases
    first). Unknown names are skipped."""
    cls = viewset if isinstance(viewset, type) else type(viewset)
    names = []
    for klass in reversed(cls.__mro__):
        declared = klass.__dict__.get('openapi_parameters') or {}
        for key in ('*', action):
            for name in declared.get(key, ()) if key is not None else ():
                if name in PARAMETERS and name not in names:
                    names.append(name)
    return [dict(PARAMETERS[name]) for name in names]
