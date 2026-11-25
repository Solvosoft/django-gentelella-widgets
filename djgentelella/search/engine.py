"""The global search: one query per searchable source, grouped hits.

Engines, chosen per source:

* **PostgreSQL** with ``django.contrib.postgres``: full-text (``SearchVector``
  with the weights of the fields, ``SearchRank``) and, when the ``pg_trgm``
  extension is there, trigram word similarity, so a typo still finds the
  object. A hit matches either one; its score is the rank plus the
  similarity.
* **Any other database** (or a source with ``search_mode = 'icontains'``):
  every word of the text has to be in one of the fields (``icontains``); the
  score adds the weight of each field that equals, starts with or contains
  the text, and of each field that contains a word.

Every source is read through its own ``get_queryset(request)``, so a row the
user may not see never matches, and only when ``has_permission(request)``
says yes: a source the user may not read is not queried at all. Everything
is ORM; the user's text only travels as a query parameter.
"""

import functools
import logging
import operator
from dataclasses import dataclass, field as dc_field

from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.db import connections
from django.db.models import (
    Case, F, FloatField, Q, TextField, Value, When,
)
from django.db.models.functions import Cast, Coalesce, Greatest

from djgentelella.datasources.base import project_model_of
from djgentelella.datasources.query import fulltext_query

from .base import (
    WEIGHT_VALUES, default_source_names, search_setting, searchable_sources,
)

logger = logging.getLogger(__name__)

#: Words of the text the icontains engine looks at; the rest are ignored.
MAX_WORDS = 8

_trigram_cache = {}


@dataclass
class SearchResult:
    """One hit: what the box and the results page show."""
    title: str
    subtitle: str
    url: str
    score: float
    pk: object

    def as_dict(self):
        return {'title': self.title, 'subtitle': self.subtitle,
                'url': self.url, 'score': round(self.score, 6),
                'pk': str(self.pk)}


@dataclass
class SearchGroup:
    """The hits of one source, best first."""
    source: str
    label: str
    icon: str = ''
    results: list = dc_field(default_factory=list)
    #: There are more hits after these (the "see more" link).
    has_more: bool = False

    @property
    def score(self):
        return max((r.score for r in self.results), default=0.0)

    def as_dict(self):
        return {'source': self.source, 'label': self.label, 'icon': self.icon,
                'has_more': self.has_more,
                'results': [r.as_dict() for r in self.results]}


def clean_text(text):
    """The text to search: stripped, blanks collapsed, cut to
    ``GT_SEARCH_MAX_LENGTH``."""
    text = ' '.join(str(text or '').split())
    return text[:int(search_setting('MAX_LENGTH'))].strip()


def search(request, query, sources=None, limit=None, offset=0):
    """Search ``query`` in the searchable sources ``request`` may read.

    :param sources: names of the sources to search (unknown or not
        searchable names are ignored). ``None``: what ``GT_SEARCH_SOURCES``
        says for the request, or every searchable source.
    :param limit: hits per group; each source's own limit by default.
    :param offset: hits to skip in each group (the pages of "see more").
    :return: a list of :class:`SearchGroup`, groups without hits left out,
        the group with the best hit first.

    Each source costs one query, plus one per process and database to
    detect ``pg_trgm`` (see ``GT_SEARCH_TRIGRAM``). A text shorter than
    ``GT_SEARCH_MIN_LENGTH`` costs none and finds nothing.
    """
    text = clean_text(query)
    if len(text) < int(search_setting('MIN_LENGTH')):
        return []
    if isinstance(sources, str):
        sources = [sources]
    if sources is None:
        sources = default_source_names(request)
    groups = []
    for name, source in searchable_sources(sources).items():
        if not source.has_permission(request):
            continue
        group = search_source(source, request, text, limit=limit, offset=offset)
        if group is not None and group.results:
            groups.append(group)
    groups.sort(key=lambda group: (-group.score, group.label))
    return groups


def search_source(source, request, text, limit=None, offset=0):
    """The :class:`SearchGroup` of one source, in one query; ``None`` when
    the source refuses the request.

    It does not check ``has_permission``: :func:`search` does, before.
    """
    spec = source.global_search
    limit = int(limit or spec.get_limit())
    offset = max(int(offset or 0), 0)
    try:
        queryset = source.get_queryset(request)
    except PermissionDenied:
        return None
    fields = spec.weighted_fields(source, request)
    group = SearchGroup(source=source.name, label=spec.get_group(source),
                        icon=spec.icon)
    if not fields:
        return group
    if use_fulltext(source, queryset):
        queryset = fulltext_search(source, queryset, fields, text)
    else:
        queryset = icontains_search(queryset, fields, text)
    related = spec.related(project_model_of(source) or queryset.model)
    if related:
        queryset = queryset.select_related(*related)
    rows = list(queryset.order_by('-_gt_score', 'pk')[offset:offset + limit + 1])
    group.has_more = len(rows) > limit
    group.results = [
        SearchResult(title=spec.render_title(obj),
                     subtitle=spec.render_subtitle(obj),
                     url=spec.render_url(obj),
                     score=float(obj._gt_score or 0), pk=obj.pk)
        for obj in rows[:limit]]
    return group


def postgres_search_available(queryset):
    return (connections[queryset.db].vendor == 'postgresql'
            and apps.is_installed('django.contrib.postgres'))


def use_fulltext(source, queryset):
    """Full-text unless the source asks for icontains or the database is not
    PostgreSQL with ``django.contrib.postgres``. A source with
    ``search_mode = 'fulltext'`` elsewhere falls back to icontains: one
    misconfigured source must not break the search of the others."""
    if getattr(source, 'search_mode', 'auto') == 'icontains':
        return False
    return postgres_search_available(queryset)


def trigram_available(using='default'):
    """True when the database ``using`` has the ``pg_trgm`` extension.

    ``GT_SEARCH_TRIGRAM`` (``True``/``False``) answers without asking; with
    ``None`` (the default) the catalog is asked once per process and
    database, and the answer cached (:func:`reset_trigram_cache`).
    """
    forced = search_setting('TRIGRAM')
    if forced is not None:
        return bool(forced)
    connection = connections[using]
    if connection.vendor != 'postgresql':
        return False
    key = (using, connection.settings_dict.get('NAME'))
    if key not in _trigram_cache:
        # The catalog has no model; a constant query with no user input.
        with connection.cursor() as cursor:
            cursor.execute('SELECT EXISTS (SELECT 1 FROM pg_extension '
                           'WHERE extname = %s)', ['pg_trgm'])
            _trigram_cache[key] = bool(cursor.fetchone()[0])
    return _trigram_cache[key]


def reset_trigram_cache():
    """Forget what :func:`trigram_available` found (after installing or
    dropping the extension in a running process)."""
    _trigram_cache.clear()


def fulltext_search(source, queryset, fields, text):
    # Optional dependency: importing it needs psycopg, which only a
    # PostgreSQL project has installed.
    from django.contrib.postgres.search import (  # noqa: PLC0415
        SearchRank, SearchVector, TrigramWordSimilarity,
    )
    config = getattr(source, 'search_config', None)
    vector = functools.reduce(operator.add, [
        SearchVector(path, weight=weight, config=config)
        for path, weight in fields])
    query = fulltext_query(text, config)
    # alias(), not annotate(): the vector is only needed by the WHERE.
    queryset = queryset.alias(_gt_vector=vector)
    match = Q(_gt_vector=query)
    score = SearchRank(vector, query)
    if trigram_available(queryset.db):
        similarities = [TrigramWordSimilarity(text, Cast(path, TextField()))
                        for path, _weight in fields]
        similarity = (Greatest(*similarities) if len(similarities) > 1
                      else similarities[0])
        queryset = queryset.alias(_gt_similarity=similarity)
        threshold = float(search_setting('TRIGRAM_THRESHOLD'))
        match |= Q(_gt_similarity__gte=threshold)
        score = score + Coalesce(F('_gt_similarity'), Value(0.0))
    return queryset.filter(match).annotate(
        _gt_score=Cast(score, FloatField()))


def icontains_search(queryset, fields, text):
    words = text.split()[:MAX_WORDS]
    match = Q()
    for word in words:
        anywhere = Q()
        for path, _weight in fields:
            anywhere |= Q(**{path + '__icontains': word})
        match &= anywhere
    parts = []
    for path, weight in fields:
        value = WEIGHT_VALUES[weight]
        parts.append(Case(
            When(Q(**{path + '__iexact': text}), then=Value(4 * value)),
            When(Q(**{path + '__istartswith': text}), then=Value(3 * value)),
            When(Q(**{path + '__icontains': text}), then=Value(2 * value)),
            default=Value(0.0), output_field=FloatField()))
        if len(words) > 1:
            for word in words:
                parts.append(Case(
                    When(Q(**{path + '__icontains': word}),
                         then=Value(value / len(words))),
                    default=Value(0.0), output_field=FloatField()))
    score = functools.reduce(operator.add, parts)
    return queryset.filter(match).annotate(_gt_score=score)
