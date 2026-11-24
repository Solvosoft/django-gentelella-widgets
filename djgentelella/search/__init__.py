"""Global search over the data sources (C13).

A :class:`~djgentelella.datasources.base.DataSource` becomes searchable with a
:class:`GlobalSearch` (the ``global_search`` attribute, or the
:func:`searchable` decorator); :func:`search` asks every searchable source the
request may read, one query each, and returns the hits grouped by source.
The results page is ``search/`` (``gt-search``), the JSON for an
autocomplete ``gtapis/search/`` (``gt-search-api``), and
``{% global_search_box %}`` (``gtsearch``) draws the box of the top bar.
See ``docs/source/global_search.rst``.
"""
from .base import GlobalSearch, searchable, searchable_sources
from .engine import (
    SearchGroup, SearchResult, reset_trigram_cache, search, trigram_available,
)

__all__ = ['GlobalSearch', 'SearchGroup', 'SearchResult', 'reset_trigram_cache',
           'search', 'searchable', 'searchable_sources', 'trigram_available']
