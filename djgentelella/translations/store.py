"""Reading and writing the translations of each kind of object (C20).

The translation screens, :mod:`djgentelella.translations.transfer` and the
commands go through these functions, which validate before writing:

- pages: :func:`page_texts`, :func:`page_translations`, :func:`save_page`;
- menu items: :func:`save_menu_item`;
- LOVs: :func:`lov_rows`, :func:`lov_translations`, :func:`save_lov`.

An update is ``{language: {key: text}}`` (a page), ``{language: title}``
(a menu item) or ``{value: {language: label}}`` (a LOV): the texts given
replace the stored ones, an empty text removes one, and what the update
does not name stays.
"""

from django.apps import apps
from django.db import transaction
from django.utils.translation import gettext as _

from djgentelella import lov
from djgentelella import translations as core
from djgentelella.designs.jsonschema import Error
from djgentelella.models import MENU_TITLE_LENGTH

__all__ = ['designs_installed', 'lov_rows', 'lov_translations', 'merge',
           'page_texts', 'page_translations', 'save_lov', 'save_menu_item',
           'save_page']


def designs_installed():
    return apps.is_installed('djgentelella.designs')


def merge(current, update):
    """``current`` (``{language: {key: text}}``) with ``update`` applied:
    a text replaces, an empty one removes."""
    result = {code: dict(texts) for code, texts in (current or {}).items()
              if isinstance(texts, dict)}
    for code, texts in update.items():
        target = result.setdefault(code, {})
        for key, text in texts.items():
            text = (text or '').strip()
            if text:
                target[key] = text
            else:
                target.pop(key, None)
        if not target:
            result.pop(code)
    return result


# -- design pages -------------------------------------------------------------------

def page_texts(page):
    """The translatable :class:`~djgentelella.designs.translations.Text`
    list of a Page."""
    from djgentelella.designs import translations  # noqa: PLC0415 optional app
    return translations.translatable_texts(page.document)


def page_translations(page):
    value = page.document.get('translations') if isinstance(page.document, dict) \
        else None
    return value if isinstance(value, dict) else {}


def save_page(page, update):
    """Apply ``update`` (``{language: {key: text}}``) to the translations of
    ``page`` and save it: ``[]``, or the errors and nothing saved.

    Only the document changes (and its hash): the publisher, and so the
    trust of the page (``engine.page_trust``), stays the same. A translation
    is plain text, it never needs that trust."""
    from djgentelella.designs import format, translations  # noqa: PLC0415 optional app
    errors = []
    for code, texts in update.items():
        errors.extend(core.validate_language(code, '$.%s' % code))
        if not isinstance(texts, dict):
            errors.append(Error('$.%s' % code, _('an object {key: text}')))
            continue
        # Before merge(), which strips each text.
        errors.extend(Error('$.%s[%r]' % (code, key), _('a translation is a text'))
                      for key, text in texts.items()
                      if text is not None and not isinstance(text, str))
    if errors:
        return errors
    document = dict(page.document)
    merged = merge(page_translations(page), update)
    document = translations.set_translations(document, merged)
    known = {text.key for text in translations.translatable_texts(document)}
    for code, texts in update.items():
        for key, text in texts.items():
            if key not in known:
                errors.append(Error('$.%s[%r]' % (code, key), _(
                    'the document has no translatable text %s') % key))
    errors.extend(translations.validate_translations(document))
    if errors:
        return errors
    if document != page.document:
        page.document = document
        page.hash = format.document_hash(document)
        page.save(update_fields=['document', 'hash', 'updated_at'])
    return []


# -- menu items ---------------------------------------------------------------------

def save_menu_item(item, update):
    """Apply ``update`` (``{language: title}``) to a MenuItem and save it:
    ``[]``, or the errors and nothing saved."""
    errors = core.validate_texts(
        {code: text or '' for code, text in update.items()}, '$',
        MENU_TITLE_LENGTH)
    if errors:
        return errors
    merged = merge({'_': item.translations or {}},
                   {'_': update}).get('_', {})
    if merged != (item.translations or {}):
        item.translations = merged
        item.save(update_fields=['translations'])
    return []


# -- LOVs ---------------------------------------------------------------------------

def _model():
    return apps.get_model('djgentelella', 'LOVTranslation')


def lov_translations(name):
    """``{value: {language: label}}`` of LOV ``name``."""
    result = {}
    for value, code, label in _model().objects.filter(lov=name).values_list(
            'value', 'language', 'label'):
        result.setdefault(value, {})[code] = label
    return result


def lov_rows(lov, request=None, limit=1000):
    """``[(value, label, {language: label})]``: the values of the LOV
    (:meth:`~djgentelella.lov.LOV.values`) and those with a translation
    that it did not return, labelled with the value itself."""
    stored = lov_translations(lov.name)
    rows, seen = [], set()
    for value, label in lov.values(request, limit=limit):
        value = str(value)
        if value in seen:
            continue
        seen.add(value)
        rows.append((value, label, stored.get(value, {})))
    for value in sorted(set(stored) - seen):
        rows.append((value, value, stored[value]))
    return rows


def save_lov(name, update):
    """Apply ``update`` (``{value: {language: label}}``) to LOV ``name``:
    ``[]``, or the errors and nothing written."""
    errors = []
    try:
        lov.get_lov(name)
    except LookupError:
        errors.append(Error('$', _('there is no LOV %s') % name))
    for value, texts in update.items():
        where = '$[%r]' % (value,)
        if not isinstance(value, str) or not value or len(value) > 255:
            errors.append(Error(where, _('a value is a text of 1 to 255 characters')))
        if not isinstance(texts, dict):
            errors.append(Error(where, _('an object {language: label}')))
            continue
        errors.extend(core.validate_texts(
            {code: text or '' for code, text in texts.items()}, where))
    if errors:
        return errors
    model = _model()
    with transaction.atomic():
        for value, texts in update.items():
            for code, text in texts.items():
                text = (text or '').strip()
                if text:
                    model.objects.update_or_create(
                        lov=name, value=value, language=code,
                        defaults={'label': text})
                else:
                    model.objects.filter(lov=name, value=value,
                                         language=code).delete()
    return []
