"""Data sources: a Python object that stands where APEX puts a SELECT.

A :class:`~djgentelella.datasources.base.DataSource` names a queryset, the
columns it exposes and who may read it. On top of it ``query`` runs the JSON
query parameters (filters, search, ordering, grouping, aggregates, pivot and
facets) and ``export`` writes the result as CSV, XLSX, JSON or PDF. The REST
endpoints under ``gtapis/datasources/<name>/`` and the facet widgets are thin
layers over those two modules. See ``docs/source/datasources.rst``.
"""
