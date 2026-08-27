Changelog
===========

Unreleased
------------

New features
""""""""""""""""""

**Leaflet map widgets.** Two widgets sharing one JavaScript engine
(``gentelella/js/base/maplib.js``):

* :class:`~djgentelella.widgets.maps.MapPointInput` asks the user for a single
  GPS point -- click, marker drag, "use my location", address search or
  ``based_fields`` geocoding from other fields. It stores the plain string
  ``"latitude,longitude"``, so **no GeoDjango, GDAL or PostGIS is needed** and
  it works on SQLite. ``djgentelella.fields.maps`` adds the matching
  ``GTPointField`` model field (with a proper ``deconstruct()``) and
  ``GTPointFormField``.
* ``DJMap`` draws many points fetched from an API, the sibling of ``DJGraph``:
  marker popups, per-layer clustering, a heatmap and a layer switcher. Subclass
  :class:`~djgentelella.views.maps.BaseMapView` in ``<app>/gtmaps.py`` and
  include ``gentelella/widgets/djmap.html``. Filters use the same
  ``#selector`` / ``{funcName}`` ``data-*`` syntax as the chart widget.

Leaflet is always loaded. Marker clustering and the heatmap come with the new
``use_maps`` define in ``DEFAULT_JS_IMPORTS``; without it maps still work, with
clustered layers falling back to plain layer groups.

Four new bundles are produced by ``pylp``:
``djgentelella.maps.vendors.min.{js,css}`` and
``djgentelella.maps.plugins.min.{js,css}``. They are emitted **after** the
readonly bundle on purpose -- storymapjs embeds Leaflet 0.7.7 and assigns it to
``window.L``, so the reverse order silently downgrades every map.

See ``docs/source/widgets/maps.rst``.

Backwards incompatible
""""""""""""""""""""""""

**Country flags are no longer CSS classes.** ``<i class="fi fi-cr"></i>`` and
the ``use_flags`` define are gone, along with
``djgentelella.flags.vendors.min.css``. Replace them with the ``gtflags``
template tags::

    {% load gtflags %}
    {% flag 'cr' %}                  <!-- was <i class="fi fi-cr"></i> -->
    {% flag 'cr' square=True %}      <!-- was <i class="fi fi-cr fis"></i> -->

That stylesheet was 6.35 MB. It carried all 532 flag SVGs base64-inlined into
``background-image``, a 232x inflation of the 27 KB it started as, and a page
showing three flags downloaded every country in both aspect ratios before it
could render. The 532 SVGs were shipped a second time under
``static/vendors/flags/``, and ``loaddevstatic`` re-downloaded all of them from
a CDN on every run -- a network hiccup during a release quietly produced broken
flags.

Removing it also frees the ``.fi`` class, which flag-icons 6.6.6 and Friconix
both claim: with ``use_flags`` on, every Friconix ``<i class="fi fi-...">`` was
silently picking up flag-icons' ``background-size``, ``display`` and ``width``.

Projects that never used flags need to change nothing.

New features
""""""""""""""""""

**Country flags from a committed sprite, served on demand.** All 266 flags now
ship as one gzipped SVG sprite,
``static/gentelella/flags/flags.4x3.svg.gz`` (~650 KB), built by the new
``manage.py buildflagsprite`` command and committed to the repository -- nothing
is downloaded at build or install time.

* ``{% flag 'cr' %}`` (``djgentelella.templatetags.gtflags``) renders an
  ``<svg><use>`` into the sprite: one request serves every flag on the page,
  cached across pages. ``square=True``, ``css_class`` and ``title`` are
  supported, and an unknown code renders nothing.
* ``/flags/<code>.svg`` returns a single flag, with optional ``size``, ``shape``
  (``circle`` or ``rounded``) and ``title`` applied at request time.
  ``djgentelella.flags.flag_url()`` builds the URL from Python.
* ``/flags/sprite.svg`` serves the sprite, handed over still gzipped.
* Flags in a select2 autocomplete need no new JavaScript: a
  ``BaseSelectImg2View`` whose ``get_url()`` returns ``flag_url(obj.code)``
  makes ``AutocompleteSelectImage`` draw a flag per option. The demo shows it at
  ``/imageselect/create/``, where the same widget sits beside one fed by
  uploaded ``FileField`` images -- the only difference between them is what
  ``get_url()`` returns -- and on the person form, where it also has to survive
  being cloned into a formset row and a modal.

``cefta`` was missing from the download list, so ``.fi-cefta`` had been defined
in the CSS and 404ing since 6.6.6 landed; the sprite has it.

The wheel is 2.4 MB smaller to download (11.8 MB -> 9.5 MB) and about
11.9 MB smaller once installed, where the base64 and the SVGs were no
longer compressed.

See ``docs/source/icons.rst``.

Fixes
""""""""""""""""""

``loaddevstatic`` dropped the last chunk of its download queue whenever the
number of files was an exact multiple of the thread count, so a library could
silently never appear under ``vendors/``.

``MapPointInput`` leaked event handlers. The ``based_fields`` listeners are
bound on *other* fields, and ``destroy()`` only unbound the widget's own input,
so a re-rendered widget -- a formset row, a reopened modal -- left a live
handler on a sibling field closing over a map that no longer existed. A
malformed ``data-based-fields`` also threw out of ``JSON.parse`` and killed the
rest of the widget initialisation, leaving an input with no map; it now falls
back to no geocoding and reports the problem on the console.

``TrashViewSet.restore`` printed the exception to stdout instead of logging it,
so the reason a restore failed never reached the application log.

**Maps rendered as empty squares on a default Django project.** Django sets
``SECURE_REFERRER_POLICY = 'same-origin'``, so the browser sends no ``Referer``
on the cross-origin requests every tile is, and OpenStreetMap's tile policy
answers 403 without one. The demo now sets
``SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'`` and
``docs/source/widgets/maps.rst`` says why any project using these widgets has
to do the same. The demo also listed ``SecurityMiddleware`` twice.

**Material Design Icons, opt-in.** 7448 icons as a webfont, shipped inside the
package -- nothing is fetched from a CDN at runtime -- and loaded only where a
template asks for it::

    {% load gtsettings %}
    {% block pre_head %}{% define_true "use_mdi" %}{% endblock %}

    <i class="mdi mdi-home"></i>

Only the woff2 is downloaded. Upstream's ``@font-face`` also lists eot, woff and
ttf -- the same glyphs in three encodings no supported browser would pick -- so
``loaddevstatic`` rewrites the rule to the woff2 alone instead of shipping
2.3 MB of fonts. It is deliberately not part of any pylp bundle: ``urlreplace``
would base64 the font into ``djgentelella.vendors.min.css``, and the point of a
webfont is that the browser fetches one 403 KB file and caches it.

**A reference page per icon set**, under an **Icons** menu in the demo sidebar:
``/icons/fontawesome`` (786), ``/icons/friconix`` (1559), ``/icons/mdi`` (7448)
and ``/icons/flags`` (266). Each is searchable, and each reads its set from what
the browser already loaded -- friconix's ``paths`` global, the CSS rules Font
Awesome and MDI declare, the ``<symbol>`` elements of the flags sprite -- so no
list can drift from the version ``loaddevstatic`` downloaded. The flags page
also previews the ``square``, ``circle`` and ``rounded`` shapes, and the
friconix page lets you try a mask against every icon at once.

Dependencies
""""""""""""""""""

Eleven frontend libraries moved up, all within a compatible range and verified
against the browser suite (57 Selenium tests):

* ``select2`` 4.1.0-**rc.0** -> 4.1.0 -- the bundle had been shipping a release
  candidate.
* ``moment.js`` 2.13.0 -> 2.30.1. The pin was from 2016 and sat below every
  security fix in the 2.29.x line.
* ``bootstrap`` 5.2.0 -> 5.3.8 and ``@popperjs/core`` 2.11.5 -> 2.11.8.
* ``parsley.js`` 2.3.13 -> 2.9.2, ``@yaireo/tagify`` 4.33.2 -> 4.38.0,
  ``htmx.org`` 2.0.4 -> 2.0.10, ``squirrelly`` 9.0.0 -> 9.1.1,
  ``spark-md5`` 3.0.0 -> 3.0.2, ``iCheck`` 1.0.2 -> 1.0.3,
  ``interact.js`` 1.10.27 -> 1.10.28.

``interact.js`` was also being downloaded twice, once from an **unpinned**
``cdn.jsdelivr.net/npm/interactjs/`` that resolved to whatever was current that
day. Both copies are now pinned to 1.10.28.

``pdf.js`` 4.6.82 -> 6.2.108. The API in use is three calls wide --
``getDocument``, ``getViewport``, ``render`` -- and ``globalThis.pdfjsLib`` is
still exposed by the ``.mjs`` build, so the jump is smaller than the version
numbers suggest; verified rendering a document in a browser on 6.2.108.
``pdf_viewer.min.css`` is gone from the bundle: 6.x no longer publishes it, and
it styled only the text, annotation and XFA layers, none of which anything here
renders. Its 15 ``images/`` SVGs went with it -- they existed solely to feed its
``url()``\ s.

Two more moved a major version each, both verified in a browser rather than by
version number alone: ``autosize`` 3.0.15 -> 6.0.1 (the global still takes a
textarea and still grows it) and ``sweetalert2`` 10.10.0 -> 11.26.25
(``Swal.fire``, ``Swal.mixin``, ``stopTimer``/``resumeTimer`` and the
``didOpen`` hook all survive; none of the options v11 dropped were in use).

``patternfly-bootstrap-treeview`` was downloaded from the **master branch** and
is now pinned to ``v2.1.10``, which is byte-identical to what master serves
today -- a pin that swaps nothing.

**Checksums for the sources that cannot be pinned.** Knightlab's StoryMap and
Timeline are fetched from ``latest``, and friconix from a URL with no version at
all, so two builds of the same commit could differ with nothing to show for it.
``loaddevstatic`` now records a SHA-256 for each and reports, in a summary block
at the end of the run, any that changed since they were last vetted.

Knightlab's numbered releases are deliberately **not** used: ``latest`` is the
current webpack build of StoryMapJS (260 KB, ``KLStoryMap`` namespace) while its
newest tag, 0.7.1, is unminified 2019 code on the old ``VCO`` architecture at
twice the size. Pinning to it would be a four-year downgrade, not a pin --
and it embeds a different Leaflet, which ``maplib.js`` asserts against at
runtime.

Removed from ``loaddevstatic``:

* **summernote 0.8.18** -- downloaded and packaged, but in no bundle and no
  template. The only caller was ``uploadFile()`` in
  ``gentelella/js/base/wysiwyg.js``, which nothing called either and which would
  have thrown ``$(...).summernote is not a function`` if it had. Both are gone;
  the wysiwyg widgets use TinyMCE's own upload endpoints.
* **Bootstrap 3 glyphicons** (216 KB, five font files from the retired MaxCDN)
  -- no bundled stylesheet has ever referenced one. ``vendors/fonts/`` now holds
  only the Font Awesome faces that ``font-awesome.min.css`` actually reaches.
* A ``bootstrap-datetimepicker`` sourcemap that has always 404ed, printing a
  ``FAILED`` line on every run.

**pdf.js parsed every document on the main thread.** The worker was loaded as a
second ``<script type="module">``, which downloads a megabyte into the page and
leaves ``GlobalWorkerOptions.workerSrc`` empty -- so pdf.js silently fell back
to its fake worker and blocked the UI while parsing. It is now handed to pdf.js
as a URL, and the parsing really does happen off-thread.

Fixes
""""""""""""""""""

**Friconix icons never appeared on anything built after page load.** Friconix
hooks ``document.onreadystatechange``, scans once and has no
``MutationObserver``, so an ``<i class="fi-...">`` inside a formset row, a
reopened modal or a DataTables redraw stayed an empty element. djgentelella now
rescans from ``gt_find_initialize()`` -- the hook every widget already
re-initialises through -- and exposes ``gt_friconix_refresh()`` for markup
injected by hand. Removing the flag-icons stylesheet helps here too: it defined
``.fi``, the same class friconix marks its icons with.

The demo gained a searchable grid of all 1559 icons at ``/friconix``, and
``docs/source/icons.rst`` now documents the six-letter mask grammar instead of
pointing at an external site.

Tooling
""""""""""""""""""

``make test-selenium`` now runs inside its own X server (``xvfb-run -a``), so
the browser the tests drive cannot steal focus from the developer's session.
``SELENIUM_HEADLESS=0`` draws a real Chrome inside it -- useful for the
Leaflet, canvas and TinyMCE widgets -- and ``make test-selenium-run`` keeps the
old behaviour of running on the caller's display.

``make coverage`` and ``make coverage-all`` measure the package, the second one
combining the unit and the browser suites into a single report. Configuration
lives in ``pyproject.toml``; ``coverage`` is not a declared dependency, install
it yourself. The unused ``[tool.black]`` section was dropped -- the formatter
this project actually uses is ``ruff format``.

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
