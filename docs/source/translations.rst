Translations of metadata
========================

Django's ``.po`` files translate the texts written in code. What an
administrator writes as *data* -- the title of a design page and of its
nodes, the header of a column, a button, a menu item, the label of a value of
a LOV -- is not in any ``.po`` file. ``djgentelella.translations`` keeps those
texts by language next to the data, and every user sees them in the active
language.

The written text is the **original**: the text of the project's default
language (``LANGUAGE_CODE``). A translation never replaces it; it is shown
instead of it while its language is active.

.. contents::
   :local:

Where each translation lives
----------------------------

=====================  ===================================================
Object                 Translations
=====================  ===================================================
design page            ``document["translations"]``, inside the document
                       (:doc:`designs`): they travel with the page when it
                       is published, exported and imported
menu item              ``MenuItem.translations``, a JSON field
                       ``{language: title}``
LOV value              the ``LOVTranslation`` table: LOV name, value,
                       language and label
=====================  ===================================================

``MenuItem.translations`` and ``LOVTranslation`` come with the migration
``djgentelella/0028_translations``.

Languages and resolution
------------------------

The languages a text can be translated to are ``GT_TRANSLATION_LANGUAGES``
(a list of ``(code, name)``), or else ``settings.LANGUAGES``. A translation to
any other language is an error wherever it is validated: the document of a
page, a menu, the import file, the admin.

The text shown is chosen by ``djgentelella.translations.pick(texts,
original, language=None)``, for the active language
(``django.utils.translation.get_language()``):

#. the translation of the active language (``pt-br``);
#. of its base language (``pt``);
#. of the default language (``LANGUAGE_CODE``), so a project whose texts
   were written in another language can still show them in its own;
#. the original.

A translation is plain text. It is escaped wherever it is shown, exactly
like the original; HTML in a translation is shown as text.

djgentelella does not choose the language of a request: that is Django's
``LocaleMiddleware`` (or any middleware that activates a language). The demo
uses ``demoapp.middleware.LanguageCookieMiddleware``, which only honours the
cookie that ``set_language`` (``/i18n/setlang/``) writes, and a switcher in
the top bar (``demoapp.menu_widgets.LanguageMenu``).

Design pages
------------

The translations of a page are part of its document::

    "translations": {
        "en": {
            "meta.title": "Translated catalogue",
            "count:title": "Products",
            "catalogue:title": "Product catalogue",
            "catalogue:column_labels.name": "Product name",
            "catalogue:row_links.0.title": "Open"
        }
    }

A key is ``meta.title`` (the page title) or ``<node id>:<path in its
props>``, dotted, with list indexes. Only the texts the node's component
declares translatable can be translated, and only those the document has:
a translation of ``catalogue:model``, of an ``html`` node or of a column the
table does not have is an error of the document. A component declares them
in ``RuntimeComponent.translatable_props`` (patterns, ``*`` for any index or
key); by default (``DEFAULT_TRANSLATABLE_PROPS``):

``title``, ``subtitle``, ``success_message``, ``row_links.*.title``,
``metrics.*.label``, ``metrics.*.prefix``, ``metrics.*.suffix``,
``steps.*.title``, ``steps.*.description`` and ``column_labels.*``.

A component of a project lists there only the props it escapes when it
renders them. The ``html`` node is never translatable: its markup is not
plain text.

**Column headers.** ``object_management``, ``inline_object_management`` and
``interactive_grid`` take ``column_labels``, ``{column: header}``, the header
of a column instead of the name of its field (``verbose_name``, which the
``.po`` files already translate). Those headers are translatable.

**Resolution and cache.** ``engine.resolve()`` resolves the document in the
active language (``translate=False`` keeps the written texts, what a code
generator wants; the translations are validated either way). The process
cache of published pages (``engine.resolve_page``) already keys every
resolution by the active language, so each language is resolved once and
then served from the cache. The hash of a resolved page is the hash of the
written document, the same in every language.

The functions behind it are in ``djgentelella.designs.translations``:
``translatable_texts(document)``, ``validate_translations(document)``,
``translate_document(document, language=None)``,
``missing_translations(document, language)`` and
``set_translations(document, translations)``.

Menus
-----

``MenuItem.translated_title(language=None)`` is the title in that language;
the menu tags (``top_menu``, ``sidebar_menu``, ``footer_sidebar_menu``) show
it. ``export_tree()`` adds ``translations`` to the items that have any,
``validate_tree()`` checks their languages and length (500) and
``import_tree()`` writes them, so they travel with the menu of an App (C14).

LOVs
----

A LOV (:doc:`lov`) answers ``(value, label)`` pairs. ``LOV.page()``,
``LOV.find()`` and ``LOV.label()`` replace each label by its
``LOVTranslation`` in the active language, with the same fallback, in one
query per page. The endpoint, ``LOVSelect`` and ``LOVChoiceField`` answer in
the language of the request. The search (``q``) still runs on the original
labels.

The translation screen lists the values of a LOV with ``LOV.values()``:
what it answers without parents. A LOV whose options depend on its parents
gives ``register_lov(..., all_values=fn)``, ``fn(request)`` returning every
``(value, label)``; without it, only the values already translated are
listed.

Translation screens
-------------------

``djgentelella.urls`` brings them under ``gt-translations/``:

======================================  =========================================
URL (name)                              What
======================================  =========================================
``gt-translations/``                    what can be translated, with what is
(``gt_translations``)                   missing per language; export and import
``gt-translations/page/<pk>/``          one row per text of a page, one column
(``gt_translations_page``)              per language
``gt-translations/menu/``               the titles of every menu item
(``gt_translations_menu``)
``gt-translations/lov/<name>/``         the labels of the values of a LOV
(``gt_translations_lov``)
``gt-translations/missing/<lang>/``      every text without a translation to
(``gt_translations_missing``)           ``<lang>``
``gt-translations/export/``             the JSON file (``?language=``,
(``gt_translations_export``)            ``?missing=0``)
``gt-translations/import/``             ``POST`` a JSON file (``dry_run``)
(``gt_translations_import``)
======================================  =========================================

Each kind of object needs the permission to change it:
``gtdesigns.change_page`` for pages, ``djgentelella.change_menuitem`` for the
menu and ``djgentelella.change_lovtranslation`` for LOVs (and the LOV's own
permission). The index, the missing texts and the export show only the kinds
the user may change; importing a file with a section the user may not change
is a 403.

Saving the translations of a page changes its document and its hash, never
its publisher (``updated_by``): the trust of the page (templates, JavaScript)
stays as it was, and a translation needs none.

Export and import
-----------------

One JSON file, for translators and for moving translations between
installations (``djgentelella.translations.transfer``)::

    {"format": "djgentelella.translations", "version": 1,
     "languages": ["en"],
     "pages": [{"site": null, "path": "translated",
                "texts": [{"key": "meta.title", "original": "Catálogo traducido",
                           "translations": {"en": "Translated catalogue"}}]}],
     "menus": [{"site": null, "key": "designs-translated",
                "original": "Catálogo traducido",
                "translations": {"en": "Translated catalogue"}}],
     "lovs": [{"lov": "demo_countries", "value": "pa", "original": "Panamá",
               "translations": {"en": "Panama"}}]}

Objects are named by natural key, never by pk: a page by the domain of its
Site (``null``: global) and its path, a menu item by the domain of its Site
and its ``key`` (items without a key are not exported), a LOV value by LOV and
value. ``original`` is for the translator and is ignored on import.

``export_translations(languages=None, sections=('pages', 'menus', 'lovs'),
request=None, empty=True)`` exports every translatable text, translated or
not (``empty=False``: only the translated ones). ``import_translations(data,
dry_run=False)`` returns ``(summary, [])`` or ``(None, errors)``: it validates
the whole file before writing and writes it in one transaction. An empty text
removes that translation; the languages and keys the file does not name stay.
``validate_translations_data(data)`` only validates.

The same from the command line::

    python manage.py gttranslations_export --language en -o translations.json
    python manage.py gttranslations_import translations.json --dry-run
    python manage.py gttranslations_import translations.json

Contract (C20)
--------------

* Texts per language with the default language and the original as the
  fallback (``pick``), for design pages (``document["translations"]``), menu
  items (``MenuItem.translations``) and LOV values (``LOVTranslation``).
* Resolution by ``get_language()``; the cache of resolved pages is per
  language.
* They travel in the public serializers (``publishing.export_page`` /
  ``import_page`` carry the document; ``menu.export_tree`` / ``import_tree``
  carry ``translations``) and so in an App's export (C14); unknown languages
  are errors.
* Never HTML: a translation is escaped like the original.

Demo
----

``/designs/translated/`` is a page written in Spanish with its English
translation: its title, a stat, the title of a table and two column headers.
Its menu item (*Designs* in the sidebar) and the ``demo_countries`` LOV
(*Panamá* / *Panama*) are translated too; the *Translations* item (under *Theme and
feedback* in the top bar), whose English title has a Spanish translation,
opens the screens. The
**ES / EN** buttons of the top bar switch the language.
