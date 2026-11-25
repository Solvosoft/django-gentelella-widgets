"""Translations of a design document (C20).

They travel inside the document, so publishing, exporting (C14) and the
editor carry them with no extra step::

    "translations": {
        "en": {"meta.title": "Products",
               "products:title": "Our products",
               "products:column_labels.name": "Product",
               "products:row_links.0.title": "Open"}
    }

A key is ``meta.title`` (the page title) or ``<node id>:<path in its
props>``, the path dotted with list indexes. Only the texts a component
declares translatable (``RuntimeComponent.translatable_props``, by default
:data:`DEFAULT_TRANSLATABLE_PROPS`) can be translated -- never a field name,
a URL or HTML -- and only those the document has. A translation is plain
text: the component escapes it as it escapes the original.

:func:`translate_document` gives the document in a language; the engine
resolves pages with it, so the cache of resolved pages, which is already
keyed by the active language, keeps one resolution per language.
"""

import copy
import fnmatch

from django.utils.translation import gettext as _

from djgentelella import translations as core
from djgentelella.designs import format, registry
from djgentelella.designs.jsonschema import Error

__all__ = ['DEFAULT_TRANSLATABLE_PROPS', 'META_TRANSLATABLE', 'Text',
           'missing_translations', 'set_translations', 'translatable_texts',
           'translate_document', 'validate_translations']

#: The props a component translates unless it says otherwise: patterns of
#: dotted paths, ``*`` for any list index or object key.
DEFAULT_TRANSLATABLE_PROPS = (
    'title', 'subtitle', 'success_message',
    'row_links.*.title',
    'metrics.*.label', 'metrics.*.prefix', 'metrics.*.suffix',
    'steps.*.title', 'steps.*.description',
    'column_labels.*',
)
#: The translatable texts of ``meta``.
META_TRANSLATABLE = ('title',)


class Text:
    """One translatable text of a document: its ``key``, the ``original``
    text and where it is (``node_id``, ``path``; ``node_id`` is None for
    ``meta``)."""

    __slots__ = ('key', 'original', 'node_id', 'node_type', 'path')

    def __init__(self, key, original, node_id=None, node_type='', path=''):
        self.key = key
        self.original = original
        self.node_id = node_id
        self.node_type = node_type
        self.path = path

    def __repr__(self):
        return '<Text %s=%r>' % (self.key, self.original)


def _leaves(value, prefix=''):
    """``(dotted path, value)`` of every string under ``value``."""
    if isinstance(value, str):
        yield prefix, value
    elif isinstance(value, dict):
        for key in sorted(value):
            yield from _leaves(value[key], '%s.%s' % (prefix, key) if prefix
                               else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _leaves(item, '%s.%d' % (prefix, index) if prefix
                               else str(index))


def _patterns(component):
    patterns = getattr(component, 'translatable_props', None)
    return DEFAULT_TRANSLATABLE_PROPS if patterns is None else tuple(patterns)


def _matches(path, patterns):
    parts = path.split('.')
    for pattern in patterns:
        pieces = pattern.split('.')
        if len(pieces) == len(parts) and all(
                fnmatch.fnmatchcase(part, piece) for part, piece in zip(parts, pieces)):
            return True
    return False


def translatable_texts(document, components=None):
    """The :class:`Text` list of ``document``: ``meta.title`` first, then the
    nodes depth first. Empty texts are left out."""
    if not isinstance(document, dict):
        return []
    components = registry.get_components() if components is None else components
    texts = []
    meta = document.get('meta') if isinstance(document.get('meta'), dict) else {}
    for name in META_TRANSLATABLE:
        if isinstance(meta.get(name), str) and meta[name].strip():
            texts.append(Text('meta.' + name, meta[name], path=name))
    root = document.get('root')
    if not isinstance(root, dict):
        return texts
    for node, _parent, _path in format.walk(root):
        node_id = node.get('id')
        props = node.get('props')
        component = components.get(node.get('type'))
        if not isinstance(node_id, str) or not isinstance(props, dict) or \
                component is None:
            continue
        patterns = _patterns(component)
        for path, value in _leaves(props):
            if value.strip() and _matches(path, patterns):
                texts.append(Text('%s:%s' % (node_id, path), value, node_id,
                                  node.get('type'), path))
    return texts


def validate_translations(document, components=None):
    """The errors of ``document["translations"]``: known languages
    (:func:`djgentelella.translations.languages`), keys of texts the document
    has and may translate, plain strings."""
    value = document.get('translations') if isinstance(document, dict) else None
    if value is None:
        return []
    path = '$.translations'
    if not isinstance(value, dict):
        return [Error(path, _('an object {language: {key: text}}'))]
    known = {text.key for text in translatable_texts(document, components)}
    errors = []
    for code, texts in value.items():
        where = '%s.%s' % (path, code)
        errors.extend(core.validate_language(code, where))
        if not isinstance(texts, dict):
            errors.append(Error(where, _('an object {key: text}')))
            continue
        for key, text in texts.items():
            at = '%s[%r]' % (where, key)
            if key not in known:
                errors.append(Error(at, _('the document has no translatable text '
                                          '%s') % key))
            if not isinstance(text, str):
                errors.append(Error(at, _('a translation is a text')))
            elif len(text) > core.MAX_LENGTH:
                errors.append(Error(at, _('longer than %d characters')
                                    % core.MAX_LENGTH))
    return errors


def _set(container, path, text):
    parts = path.split('.')
    for part in parts[:-1]:
        container = container[int(part)] if isinstance(container, list) else \
            container[part]
    last = parts[-1]
    if isinstance(container, list):
        container[int(last)] = text
    else:
        container[last] = text


def translate_document(document, language=None, components=None):
    """``document`` with its texts in ``language`` (by default the active
    one; see :func:`djgentelella.translations.pick`). The argument is not
    changed; a document with nothing to translate comes back as it is.

    Keys that do not name a translatable text are ignored here:
    :func:`validate_translations` reports them.
    """
    value = document.get('translations') if isinstance(document, dict) else None
    if not value or not isinstance(value, dict):
        return document
    replacements = []
    for text in translatable_texts(document, components):
        by_language = {code: texts.get(text.key) for code, texts in value.items()
                       if isinstance(texts, dict)}
        chosen = core.pick(by_language, text.original, language)
        if chosen != text.original:
            replacements.append((text, chosen))
    if not replacements:
        return document
    result = copy.deepcopy(document)
    nodes = {node.get('id'): node for node, _parent, _path in
             format.walk(result['root'])}
    for text, chosen in replacements:
        if text.node_id is None:
            result['meta'][text.path] = chosen
        else:
            _set(nodes[text.node_id]['props'], text.path, chosen)
    return result


def missing_translations(document, language, components=None):
    """The :class:`Text` list of ``document`` without a translation to
    ``language``."""
    value = document.get('translations') if isinstance(document, dict) else None
    texts = (value or {}).get(language) or {}
    return [text for text in translatable_texts(document, components)
            if not (isinstance(texts.get(text.key), str) and texts[text.key].strip())]


def set_translations(document, translations, components=None):
    """A copy of ``document`` whose translations are ``translations``
    (``{language: {key: text}}``), without the empty texts and the keys the
    document has no text for. ``document`` is not changed."""
    known = {text.key for text in translatable_texts(document, components)}
    result = copy.deepcopy(document)
    cleaned = {}
    for code in sorted(translations):
        texts = {key: text.strip() for key, text in
                 (translations[code] or {}).items()
                 if key in known and isinstance(text, str) and text.strip()}
        if texts:
            cleaned[code] = texts
    if cleaned:
        result['translations'] = cleaned
    else:
        result.pop('translations', None)
    return result
