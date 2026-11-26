"""Exporting and importing translations as one JSON file (C20).

The format, for translators and for moving them between installations::

    {"format": "djgentelella.translations", "version": 1,
     "languages": ["en"],
     "pages": [{"site": null, "path": "products",
                "texts": [{"key": "meta.title", "original": "Productos",
                           "translations": {"en": "Products"}}]}],
     "menus": [{"site": "example.com", "key": "products",
                "original": "Productos", "translations": {"en": "Products"}}],
     "lovs": [{"lov": "countries", "value": "pa", "original": "Panamá",
               "translations": {"en": "Panama"}}]}

Objects are named by natural key, never by pk: a page by Site domain and
path, a menu item by Site domain and ``key`` (items without a key are not
exported), a LOV value by LOV name and value. ``original`` is informative
-- what the translator translates -- and is ignored on import.

:func:`import_translations` validates everything first and writes nothing
when there is an error; then it writes in one transaction. An empty text
removes that translation; languages and keys the file does not name stay.

Both take ``site``: by default every Site (the commands); a Site or ``None``
limits them to that Site's objects and the global ones (``site_q``), as the
screens do with the Site of the request.
"""

from django.contrib.sites.models import Site
from django.db import transaction
from django.utils.translation import gettext as _

from djgentelella import lov as lovs
from djgentelella import translations as core
from djgentelella.designs.jsonschema import Error
from djgentelella.models import MenuItem
from djgentelella.sites import site_q
from djgentelella.translations import store

__all__ = ['ALL_SITES', 'FORMAT', 'VERSION', 'export_translations',
           'import_translations', 'validate_translations_data']

FORMAT = 'djgentelella.translations'
VERSION = 1
SECTIONS = ('pages', 'menus', 'lovs')
#: ``site`` of the functions of this module: the objects of every Site.
ALL_SITES = object()


def _scoped(queryset, site):
    """``queryset`` limited to ``site`` and the global rows, unless ``site``
    is :data:`ALL_SITES`."""
    return queryset if site is ALL_SITES else queryset.filter(site_q(site))


def _domain(site_id, domains):
    return None if site_id is None else domains.get(site_id)


def _only(texts, languages):
    texts = texts if isinstance(texts, dict) else {}
    if languages is None:
        return dict(texts)
    return {code: text for code, text in texts.items() if code in languages}


def _pages(site=ALL_SITES):
    if not store.designs_installed():
        return []
    from djgentelella.designs.models import Page  # noqa: PLC0415 optional app
    return _scoped(Page.objects.select_related('site'), site).order_by(
        'site_id', 'path')


def export_translations(*, languages=None, sections=SECTIONS, request=None,
                        empty=True, site=ALL_SITES):
    """The translations as the JSON-friendly ``dict`` of the module's format.

    ``languages`` limits them to those codes (default: every language
    stored). ``sections`` picks ``pages``, ``menus`` and ``lovs``. With
    ``empty`` (the default) every translatable text is exported, translated
    or not, so a translator can fill the gaps; without it, only the texts
    with a translation. With ``request``, only the LOVs its user may open;
    with ``site``, only the pages and menu items of that Site and the global
    ones.
    """
    languages = None if languages is None else list(languages)
    domains = dict(Site.objects.values_list('pk', 'domain'))
    data = {'format': FORMAT, 'version': VERSION,
            'languages': languages if languages is not None else
            [code for code in core.language_codes()
             if code != core.default_language()]}
    if 'pages' in sections:
        pages = []
        for page in _pages(site):
            stored = store.page_translations(page)
            texts = []
            for text in store.page_texts(page):
                found = _only({code: values.get(text.key)
                               for code, values in stored.items()
                               if isinstance(values, dict) and values.get(text.key)},
                              languages)
                if found or empty:
                    texts.append({'key': text.key, 'original': text.original,
                                  'translations': found})
            if texts:
                pages.append({'site': _domain(page.site_id, domains),
                              'path': page.path, 'texts': texts})
        data['pages'] = pages
    if 'menus' in sections:
        menus = []
        for item in _scoped(MenuItem.objects.filter(key__isnull=False),
                            site).order_by('site_id', 'key'):
            found = _only(item.translations, languages)
            if found or empty:
                menus.append({'site': _domain(item.site_id, domains),
                              'key': item.key, 'original': item.title,
                              'translations': found})
        data['menus'] = menus
    if 'lovs' in sections:
        rows = []
        for name, lov in sorted(lovs.get_lovs().items()):
            if request is not None and not lov.has_permission(request):
                continue
            for value, label, found in store.lov_rows(lov, request):
                found = _only(found, languages)
                if found or empty:
                    rows.append({'lov': name, 'value': value, 'original': label,
                                 'translations': found})
        data['lovs'] = rows
    return data


def _page(domain, path, site=ALL_SITES):
    from djgentelella.designs.models import Page  # noqa: PLC0415 optional app
    query = _scoped(Page.objects.filter(path=path), site)
    return (query.filter(site__isnull=True) if domain is None
            else query.filter(site__domain=domain)).first()


def _menu_item(domain, key, site=ALL_SITES):
    try:
        return _scoped(MenuItem.objects.all(), site).get_by_natural_key(key, domain)
    except MenuItem.DoesNotExist:
        return None


def _check_translations(value, where, errors):
    if not isinstance(value, dict):
        errors.append(Error(where, _('an object {language: text}')))
        return False
    errors.extend(core.validate_texts(value, where))
    return True


def _plan(data, request=None, site=ALL_SITES):
    """``(work, errors)``: what importing ``data`` writes, as
    ``[(kind, object, update)]``. An object out of ``site`` is not found, and
    a LOV the user of ``request`` may not open is refused."""
    errors, work = [], []
    if not isinstance(data, dict):
        return [], [Error('$', _('a translations file is a JSON object'))]
    if data.get('format') != FORMAT:
        errors.append(Error('$.format', _('must be %r') % FORMAT))
    if data.get('version') != VERSION:
        errors.append(Error('$.version', _('version %r is not supported') %
                            (data.get('version'),)))
    for name in sorted(set(data) - {'format', 'version', 'languages'} -
                       set(SECTIONS)):
        errors.append(Error('$.' + name, _('unknown field')))
    if errors:
        return [], errors
    for index, entry in enumerate(data.get('pages') or []):
        where = '$.pages[%d]' % index
        if not store.designs_installed():
            errors.append(Error(where, _('djgentelella.designs is not installed')))
            break
        if not isinstance(entry, dict) or not isinstance(entry.get('path'), str) \
                or not isinstance(entry.get('texts'), list):
            errors.append(Error(where, _('a page is {site, path, texts}')))
            continue
        page = _page(entry.get('site'), entry['path'], site)
        if page is None:
            errors.append(Error(where, _('there is no page %(path)s in %(site)s') % {
                'path': entry['path'], 'site': entry.get('site') or _('global')}))
            continue
        update = {}
        for number, text in enumerate(entry['texts']):
            at = '%s.texts[%d]' % (where, number)
            if not isinstance(text, dict) or not isinstance(text.get('key'), str):
                errors.append(Error(at, _('a text is {key, translations}')))
                continue
            if _check_translations(text.get('translations', {}),
                                   at + '.translations', errors):
                for code, value in text.get('translations', {}).items():
                    update.setdefault(code, {})[text['key']] = value
        work.append(('page', page, update, where))
    for index, entry in enumerate(data.get('menus') or []):
        where = '$.menus[%d]' % index
        if not isinstance(entry, dict) or not isinstance(entry.get('key'), str):
            errors.append(Error(where, _('a menu item is {site, key, translations}')))
            continue
        item = _menu_item(entry.get('site'), entry['key'], site)
        if item is None:
            errors.append(Error(where, _('there is no menu item %(key)s in '
                                         '%(site)s') % {
                'key': entry['key'], 'site': entry.get('site') or _('global')}))
            continue
        if _check_translations(entry.get('translations', {}),
                               where + '.translations', errors):
            work.append(('menu', item, entry.get('translations', {}), where))
    by_lov = {}
    for index, entry in enumerate(data.get('lovs') or []):
        where = '$.lovs[%d]' % index
        if not isinstance(entry, dict) or not isinstance(entry.get('lov'), str) \
                or not isinstance(entry.get('value'), str):
            errors.append(Error(where, _('a LOV value is {lov, value, translations}')))
            continue
        try:
            lov = lovs.get_lov(entry['lov'])
        except LookupError:
            errors.append(Error(where, _('there is no LOV %s') % entry['lov']))
            continue
        if request is not None and not lov.has_permission(request):
            errors.append(Error(where, _('you may not translate the LOV %s')
                                % entry['lov']))
            continue
        if _check_translations(entry.get('translations', {}),
                               where + '.translations', errors):
            by_lov.setdefault(entry['lov'], {})[entry['value']] = \
                entry.get('translations', {})
    for name, update in sorted(by_lov.items()):
        work.append(('lov', name, update, '$.lovs'))
    return work, errors


def validate_translations_data(data, *, request=None, site=ALL_SITES):
    """The :class:`~djgentelella.designs.jsonschema.Error` list of a
    translations file; empty means :func:`import_translations` takes it."""
    return _plan(data, request, site)[1]


def import_translations(data, *, dry_run=False, request=None, site=ALL_SITES):
    """Write the translations of ``data``: ``(summary, [])``, or
    ``(None, errors)`` and nothing written. ``summary`` counts the pages,
    menu items and LOVs touched. ``dry_run`` validates everything (each
    object's own checks included) and rolls back. With ``request``, a LOV its
    user may not open is an error; with ``site``, so is an object of another
    Site."""
    work, errors = _plan(data, request, site)
    if errors:
        return None, errors
    summary = {'pages': 0, 'menus': 0, 'lovs': 0}
    savers = {'page': (store.save_page, 'pages'),
              'menu': (store.save_menu_item, 'menus'),
              'lov': (store.save_lov, 'lovs')}
    try:
        with transaction.atomic():
            for kind, target, update, where in work:
                save, section = savers[kind]
                found = save(target, update)
                if found:
                    errors.extend(Error(where + error.path.lstrip('$'),
                                        error.message) for error in found)
                else:
                    summary[section] += 1
            if errors or dry_run:
                raise _Rollback()
    except _Rollback:
        if errors:
            return None, errors
    return summary, []


class _Rollback(Exception):
    pass
