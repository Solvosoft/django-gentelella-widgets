Changelog
===========

0.6.0
-------

Breaking changes
""""""""""""""""""

**Django 5.2 (LTS) is now the minimum**, along with Django REST Framework
3.15.2. Python 3.11 remains the floor.

**``InlineAjaxCRUD`` was removed**, together with the ``inlines`` attribute of
``CRUDView``, the ``crud_inline_url`` template tag and the
``templates/cruds/ajax/`` template set. It rendered the children of an object as
server side HTML fragments swapped in with djangoajax, a pattern nothing else in
the project used. Replace it with
:class:`~djgentelella.objectmanagement.BaseInlineObjectManagement`, which manages
the same relation through the regular ``ObjectCRUD`` javascript over a queryset
scoped to one parent::

    class NoteManagement(BaseInlineObjectManagement):
        queryset = Note.objects.all()
        parent_model = Project
        parent_field = 'project'

    router.register(r'project/(?P<parent_pk>[^/.]+)/note',
                    NoteManagement, 'api-project-note')

See ``docs/source/object_management.rst`` for the full example.

**django-markitup is gone from the blog.** ``Entry.resume`` and
``Entry.content`` are plain ``TextField``\ s edited with ``EditorTinymce``.
Remove ``'markitup'`` from ``INSTALLED_APPS`` and drop the ``MARKITUP_FILTER``,
``MARKITUP_SET`` and ``markitup_preview`` URL entries. Existing databases are
migrated by ``blog.0002``, which moves the HTML held in the ``_resume_rendered``
and ``_content_rendered`` columns into ``resume``/``content`` and then drops
those columns; without it every insert fails on them (they are NOT NULL) and the
markdown source would be served verbatim. The migration cannot be reversed, and
its raw ``DROP COLUMN`` needs SQLite 3.35 or newer — **back up the blog tables
before upgrading**.

.. warning::

   Entry bodies are now stored and served as HTML written in TinyMCE, and
   gentelella does not sanitize them. Anyone holding ``blog.add_entry`` or
   ``blog.change_entry`` can therefore place arbitrary HTML and JavaScript on
   the public entry list and detail pages, which carry no permission check.
   Grant those permissions to trusted authors only, or wrap the fields in your
   own sanitizer if the blog is open to untrusted writers.

**The tree select fields are form fields, not widgets.**
``GentelellaTreeNodeChoiceField`` and ``GentelellaTreeNodeMultipleChoiceField``
now derive from ``ModelChoiceField``/``ModelMultipleChoiceField`` instead of
``forms.Select``, so they are declared as the field, not passed as ``widget=``::

    # before (never actually worked)
    node = forms.ModelChoiceField(queryset=..., widget=GentelellaTreeNodeChoiceField(...))
    # now
    node = GentelellaTreeNodeChoiceField(queryset=...)

In practice nothing breaks: the previous code called
``forms.Select.__init__(queryset)`` and raised ``AttributeError`` on
construction, and it read MPTT internals that have not been a dependency since
2022.

**The transcription endpoint answers 403 json instead of redirecting.**
``voice_transcribe`` enforces authentication itself and must not be wrapped in
``login_required``: its caller is the widget's ``fetch``, which would follow the
302 and fail parsing the login page as json.

**Dependencies dropped**: ``djangoajax``, ``django-markitup`` and ``markdown``
are no longer installed, and the dead ``static/django_ajax/`` files were
removed. The ``firmador`` extra now uses lower bounds instead of ``==`` pins,
which made it unresolvable next to any project needing a newer ``requests``,
``channels`` or ``django-cors-headers``.

New features
""""""""""""""

**Voice dictation widgets** (``VoiceDictation``, ``VoiceEditorTinymce``) with
progressive Web Audio + VAD capture, and a transcription endpoint
(``voice_transcribe``) with two interchangeable backends selected
by ``GENTELELLA_ASR_BACKEND``::

    pip install "djgentelella[asr]"          # local, in-process Parakeet-v3
    pip install "djgentelella[asr-remote]"   # forward to an external ASR API

Neither extra is needed to install or import djgentelella; without the matching
one the endpoint answers ``501`` naming it. See
``docs/source/widgets/voice.rst``.

**``BaseInlineObjectManagement``** for REST-driven CRUD over the children of a
parent object, scoped by the queryset so a child of another parent answers 404.

**``celery`` extra** for the ``async_notification`` queue backend. Without it
notifications are dispatched in-process by ``SyncBackend``, with nothing to
configure.

The project is now classified **Production/Stable** rather than Beta.

Fixes
"""""""

- The tree select fields are rebuilt on ``django-tree-queries`` (see the
  breaking change above). Options are now indented at any depth: the themes only
  defined ``.l2`` and ``.l3``, so levels 0, 1 and 4+ rendered flush left.
  ``TreeSelectMultiple`` was never registered in ``widgets.js`` and did not
  indent at all. ``disableN`` accepts any depth and honours its value, so
  ``disable1=False`` no longer disables level 1. Replacing ``field.queryset``
  after construction — the usual way to scope a field inside a form's
  ``__init__`` — keeps the tree depths; it used to silently flatten the whole
  tree.
- ``BaseObjectManagement.list`` counted ``recordsTotal`` from the class level
  ``queryset`` instead of ``get_queryset()``, so any subclass narrowing the
  queryset reported the unfiltered total.
- ``decore_form_instance`` carried a branch comparing ``type(field)`` against a
  string, dead since the MPTT removal in 2022; removed.
- The ASR backend selection treats an empty setting as unset, since both it and
  the remote URL are usually wired to ``os.getenv``.
- ``MANIFEST.in`` grafts the whole package, so a module cannot be released
  without its templates. ``async_notification``'s 23 templates and 3 static
  files were absent from the build; ``make check-dist`` now fails the release
  when any tree is missing.
- ``make release`` no longer passes ``twine upload -s``: PyPI stopped accepting
  GPG signatures in 2023. ``make sdist`` runs ``makemigrations --check``
  instead of ``makemigrations``, so a release fails on model drift rather than
  shipping a migration nobody reviewed.
