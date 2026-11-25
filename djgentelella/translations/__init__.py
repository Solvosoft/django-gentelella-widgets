"""Translations of metadata: what an administrator writes as data.

Titles of design pages and of their nodes, column labels, buttons, menu items
and the labels of LOVs are data, not code, so ``.po`` files cannot translate
them. Each one keeps its texts by language next to it:

- a design page in its document, ``document["translations"]``
  (:mod:`djgentelella.designs.translations`);
- a menu item in ``MenuItem.translations``;
- a LOV in the ``LOVTranslation`` table, by LOV and value.

The written text -- the title, the label -- is the original, the text of the
project's default language (``LANGUAGE_CODE``). A translation is always plain
text: it is escaped wherever it is shown, like the original.

:func:`pick` is the resolution every one of them uses: the translation of
the active language (``get_language()``), else of its base language (``en``
for ``en-us``), else of the default language, else the original.
"""

from django.conf import settings
from django.utils.translation import get_language
from django.utils.translation import gettext as _

from djgentelella.designs.jsonschema import Error

__all__ = ['Error', 'MAX_LENGTH', 'candidates', 'default_language',
           'is_known_language', 'language_codes', 'languages', 'normalize',
           'pick', 'validate_language', 'validate_texts']

#: The longest translated text a design or LOV takes.
MAX_LENGTH = 1000


def normalize(code):
    """``code`` as Django writes language codes: lower case, ``-``."""
    return str(code or '').strip().lower().replace('_', '-')


def languages():
    """``[(code, name)]`` the metadata may be translated to:
    ``GT_TRANSLATION_LANGUAGES`` or else ``settings.LANGUAGES``."""
    value = getattr(settings, 'GT_TRANSLATION_LANGUAGES', None)
    if value is None:
        value = settings.LANGUAGES
    return [(normalize(code), str(name)) for code, name in value]


def language_codes():
    return [code for code, _name in languages()]


def default_language():
    """The language the written texts are in: ``LANGUAGE_CODE``."""
    return normalize(settings.LANGUAGE_CODE)


def is_known_language(code):
    return isinstance(code, str) and normalize(code) == code and \
        code in language_codes()


def validate_language(code, path):
    if not isinstance(code, str) or normalize(code) != code:
        return [Error(path, _('%r is not a language code (lower case, e.g. "en" '
                              'or "pt-br")') % (code,))]
    if code not in language_codes():
        return [Error(path, _('unknown language %(code)s: the project offers '
                              '%(known)s') % {
            'code': code, 'known': ', '.join(language_codes()) or '-'})]
    return []


def candidates(language=None):
    """The languages tried, in order, for ``language`` (by default the active
    one): itself, its base language, the default language and its base."""
    if language is None:
        language = get_language()
    result = []
    default = default_language()
    for code in (language, default):
        code = normalize(code)
        if not code:
            continue
        for option in (code, code.split('-')[0]):
            if option and option not in result:
                result.append(option)
    return result


def pick(texts, original, language=None):
    """The text of ``language`` (the active one by default) in ``texts``
    (``{code: text}``), following :func:`candidates`; ``original`` when
    there is none. Empty texts do not count."""
    if texts and isinstance(texts, dict):
        for code in candidates(language):
            text = texts.get(code)
            if isinstance(text, str) and text.strip():
                return text
    return original


def validate_texts(value, path, max_length=MAX_LENGTH):
    """The errors of ``{language: text}``: known languages, plain strings
    no longer than ``max_length``."""
    if value is None:
        return []
    if not isinstance(value, dict):
        return [Error(path, _('the translations are an object {language: text}'))]
    errors = []
    for code, text in value.items():
        where = '%s.%s' % (path, code)
        errors.extend(validate_language(code, where))
        if not isinstance(text, str):
            errors.append(Error(where, _('a translation is a text')))
        elif len(text) > max_length:
            errors.append(Error(where, _('longer than %d characters') % max_length))
    return errors
