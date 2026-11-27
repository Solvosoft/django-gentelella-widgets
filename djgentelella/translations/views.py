"""The translation screens (C20): one per object, what is missing per
language, and exporting and importing the JSON of
:mod:`djgentelella.translations.transfer`.

Each kind of object needs the permission to change it:
``gtdesigns.change_page`` for the pages, ``djgentelella.change_menuitem`` for
the menu and ``djgentelella.change_lovtranslation`` for the LOVs (and each
LOV's own permission). The index, the missing texts and the export show only
the kinds the user may change. Pages and menu items are those of the Site of
the request and the global ones (``site_q``), on every screen, the export and
the import.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from djgentelella import lov as lovs
from djgentelella import translations as core
from djgentelella.models import MenuItem
from djgentelella.sites import get_current_site, site_q
from djgentelella.translations import store, transfer

PAGE_PERM = 'gtdesigns.change_page'
MENU_PERM = 'djgentelella.change_menuitem'
LOV_PERM = 'djgentelella.change_lovtranslation'
#: The largest translations file the import screen takes, in bytes.
MAX_UPLOAD = 5 * 1024 * 1024


def allowed_sections(user):
    """The kinds of object ``user`` may translate: ``pages``, ``menus``,
    ``lovs``."""
    sections = []
    if store.designs_installed() and user.has_perm(PAGE_PERM):
        sections.append('pages')
    if user.has_perm(MENU_PERM):
        sections.append('menus')
    if user.has_perm(LOV_PERM):
        sections.append('lovs')
    return sections


def _require(request, section):
    if section not in allowed_sections(request.user):
        raise PermissionDenied


def _any_section(request):
    sections = allowed_sections(request.user)
    if not sections:
        raise PermissionDenied
    return sections


def _language_columns():
    return core.languages()


def _rows_from_post(request, count):
    """``[(key, {language: text})]`` of the rows the screen posted."""
    codes = [code for code, _name in _language_columns()]
    rows = []
    for index in range(count):
        key = request.POST.get('k%d' % index)
        if key is None:
            continue
        rows.append((key, {code: request.POST.get('v%d_%s' % (index, code), '')
                           for code in codes}))
    return rows


def _count(request):
    try:
        return max(0, min(int(request.POST.get('count', '0')), 10000))
    except ValueError:
        return 0


def _cells(texts):
    return [(code, name, (texts or {}).get(code, ''))
            for code, name in _language_columns()]


def _page_model():
    from djgentelella.designs.models import Page  # noqa: PLC0415 optional app
    return Page


def _site(request):
    return get_current_site(request)


def _pages(request):
    """The pages of the request's Site and the global ones."""
    return _page_model().objects.filter(site_q(_site(request)))


def _menu_items(request):
    """The menu items of the request's Site and the global ones."""
    return MenuItem.objects.filter(site_q(_site(request)))


@login_required
def translations_index(request):
    """What can be translated, with how much is missing per language."""
    sections = _any_section(request)
    languages = _language_columns()
    pages, menus, lov_list = [], [], []
    if 'pages' in sections:
        for page in _pages(request).select_related('site').order_by('path'):
            texts = store.page_texts(page)
            stored = store.page_translations(page)
            pages.append({'page': page, 'total': len(texts), 'missing': [
                sum(1 for text in texts
                    if not (stored.get(code) or {}).get(text.key))
                for code, _name in languages]})
    if 'menus' in sections:
        items = list(_menu_items(request).select_related('site'))
        menus = [{'total': len(items), 'missing': [
            sum(1 for item in items if not (item.translations or {}).get(code))
            for code, _name in languages]}]
    if 'lovs' in sections:
        for name, lov in sorted(lovs.get_lovs().items()):
            if not lov.has_permission(request):
                continue
            rows = store.lov_rows(lov, request)
            lov_list.append({'name': name, 'total': len(rows), 'missing': [
                sum(1 for _value, _label, found in rows if not found.get(code))
                for code, _name in languages]})
    return render(request, 'gentelella/translations/index.html', {
        'sections': sections, 'languages': languages, 'pages': pages,
        'menus': menus, 'lovs': lov_list,
        'default_language': core.default_language()})


def _back_url(request):
    """Where the form's *Back* link goes: ``?next=`` when it is a URL of this
    site (``url_has_allowed_host_and_scheme``), else the translations index.
    A project that links to a translation screen from its own page passes
    ``?next=<that page>`` and needs no copy of the template."""
    target = request.GET.get('next', '')
    if target and url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()},
            require_https=request.is_secure()):
        return target
    return reverse('gt_translations')


def _save(request, save, target, rows, success_url):
    update = {}
    for key, texts in rows:
        for code, text in texts.items():
            update.setdefault(code, {})[key] = text
    errors = save(target, update)
    if errors:
        for error in errors:
            messages.error(request, str(error))
        return None
    messages.success(request, _('The translations were saved.'))
    return redirect(success_url)


@login_required
@require_http_methods(['GET', 'POST'])
def translate_page(request, pk):
    """The translations of one design page, one row per translatable text."""
    _require(request, 'pages')
    page = get_object_or_404(_pages(request), pk=pk)
    if request.method == 'POST':
        response = _save(request, store.save_page, page,
                         _rows_from_post(request, _count(request)),
                         request.get_full_path())
        if response is not None:
            return response
    stored = store.page_translations(page)
    rows = [{'key': text.key, 'original': text.original,
             'where': text.node_id or 'meta', 'path': text.path,
             'cells': _cells({code: (values or {}).get(text.key, '')
                              for code, values in stored.items()})}
            for text in store.page_texts(page)]
    return render(request, 'gentelella/translations/form.html', {
        'title': _('Translations of page %s') % page.title, 'object': page,
        'kind': 'page', 'rows': rows, 'languages': _language_columns(),
        'back_url': _back_url(request)})


@login_required
@require_http_methods(['GET', 'POST'])
def translate_menu(request):
    """The translations of the menu items' titles."""
    _require(request, 'menus')
    items = {str(item.pk): item for item in
             _menu_items(request).select_related('site').order_by(
                 'site_id', 'category', 'position', 'pk')}
    if request.method == 'POST':
        errors = []
        for key, texts in _rows_from_post(request, _count(request)):
            item = items.get(key)
            if item is None:
                continue
            errors.extend(store.save_menu_item(item, texts))
        if errors:
            for error in errors:
                messages.error(request, str(error))
        else:
            messages.success(request, _('The translations were saved.'))
            return redirect(request.get_full_path())
    rows = [{'key': key, 'original': item.title,
             'where': item.site.domain if item.site_id else _('global'),
             'path': item.key or '', 'cells': _cells(item.translations)}
            for key, item in items.items()]
    return render(request, 'gentelella/translations/form.html', {
        'title': _('Translations of the menu'), 'kind': 'menu', 'rows': rows,
        'languages': _language_columns(), 'back_url': _back_url(request)})


@login_required
@require_http_methods(['GET', 'POST'])
def translate_lov(request, name):
    """The labels of one LOV's values."""
    _require(request, 'lovs')
    try:
        lov = lovs.get_lov(name)
    except LookupError:
        raise Http404() from None
    if not lov.has_permission(request):
        raise PermissionDenied
    if request.method == 'POST':
        update = {}
        for value, texts in _rows_from_post(request, _count(request)):
            update[value] = texts
        errors = store.save_lov(name, update)
        if errors:
            for error in errors:
                messages.error(request, str(error))
        else:
            messages.success(request, _('The translations were saved.'))
            return redirect(request.get_full_path())
    rows = [{'key': value, 'original': label, 'where': name, 'path': value,
             'cells': _cells(found)}
            for value, label, found in store.lov_rows(lov, request)]
    return render(request, 'gentelella/translations/form.html', {
        'title': _('Translations of the list %s') % name, 'kind': 'lov',
        'rows': rows, 'languages': _language_columns(),
        'back_url': _back_url(request)})


@login_required
def translations_missing(request, language):
    """Every text without a translation to ``language``."""
    sections = _any_section(request)
    if language not in core.language_codes():
        raise Http404()
    data = transfer.export_translations(languages=[language], sections=sections,
                                        request=request, site=_site(request))
    pages = [{'page': entry, 'texts': [text for text in entry['texts']
                                       if not text['translations']]}
             for entry in data.get('pages', [])]
    pages = [entry for entry in pages if entry['texts']]
    if pages:
        found = {(page.site.domain if page.site_id else None, page.path): page.pk
                 for page in _pages(request).select_related('site')}
        for entry in pages:
            entry['pk'] = found.get((entry['page']['site'], entry['page']['path']))
    menus = [entry for entry in data.get('menus', []) if not entry['translations']]
    unnamed = []
    if 'menus' in sections:
        # Items without a key are not exported, but they are translated too.
        unnamed = [item for item in _menu_items(request).filter(key__isnull=True)
                   if not (item.translations or {}).get(language)]
    lov_rows = [entry for entry in data.get('lovs', []) if not entry['translations']]
    return render(request, 'gentelella/translations/missing.html', {
        'language': language, 'language_name': dict(core.languages())[language],
        'languages': core.languages(), 'pages': pages, 'menus': menus,
        'unnamed': unnamed, 'lovs': lov_rows, 'sections': sections})


@login_required
def translations_export(request):
    """The translations as a JSON file: ``?language=`` (repeatable) limits
    the languages, ``?missing=0`` leaves out the texts without one."""
    sections = _any_section(request)
    languages = [code for code in request.GET.getlist('language')
                 if code in core.language_codes()] or None
    data = transfer.export_translations(
        languages=languages, sections=sections, request=request,
        empty=request.GET.get('missing', '1') != '0', site=_site(request))
    response = HttpResponse(json.dumps(data, ensure_ascii=False, indent=2),
                            content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="translations.json"'
    return response


@login_required
@require_POST
def translations_import(request):
    """Import a JSON file of translations; ``dry_run`` only validates it.
    Each section of the file needs the permission of its kind."""
    sections = _any_section(request)
    upload = request.FILES.get('file')
    if upload is None or upload.size > MAX_UPLOAD:
        messages.error(request, _('Choose a JSON file of translations (at most '
                                  '%d MB).') % (MAX_UPLOAD // (1024 * 1024)))
        return redirect('gt_translations')
    try:
        data = json.loads(upload.read().decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        messages.error(request, _('The file is not valid JSON.'))
        return redirect('gt_translations')
    if isinstance(data, dict):
        refused = [name for name in transfer.SECTIONS
                   if data.get(name) and name not in sections]
        if refused:
            raise PermissionDenied
    summary, errors = transfer.import_translations(
        data, dry_run=bool(request.POST.get('dry_run')), request=request,
        site=_site(request))
    if errors:
        for error in errors[:50]:
            messages.error(request, str(error))
        return redirect('gt_translations')
    if request.POST.get('dry_run'):
        messages.info(request, _('The file is valid: %(pages)d pages, %(menus)d '
                                 'menu items and %(lovs)d lists would change.')
                      % summary)
    else:
        messages.success(request, _('Imported: %(pages)d pages, %(menus)d menu '
                                    'items and %(lovs)d lists.') % summary)
    return redirect('gt_translations')
