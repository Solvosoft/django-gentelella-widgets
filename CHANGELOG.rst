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

**Two generic javascript components.** Both are classes concatenated into
``base.js`` by ``createbasejs``, with a stylesheet of their own linked from
``gentelella/statics/stylesheets.html``.

* ``PositionsGrid`` (``gentelella/js/base/positionsgrid.js``) draws a matrix of
  rows and cells where each cell holds zero or more opaque items. **Rows are
  irregular on purpose**: a row of two cells is half the width of a row of four,
  cells stay left aligned and nothing is padded out to a rectangle, because the
  shape is the host's data and not a grid the widget imposes. The widget keeps
  no state of its own and serialises nothing -- every mutation goes out through
  a handler that resolves with the new state and the grid repaints with that, so
  a rejected handler leaves the screen showing exactly what the server last
  confirmed and fires ``pg:error``. Moving an item is two taps (pick, then
  destination), not a drag, so it works on a phone and from the keyboard; the
  desktop drag is the same code path.
* ``BreadcrumbNav`` (``gentelella/js/base/breadcrumbnav.js``) fills the
  ``{% block breadcrumbs %}`` of ``base.html`` and ``plain.html``, which had been
  empty since the theme was ported. A view that puts ``breadcrumbs`` in its
  context now gets the path server-rendered from
  ``gentelella/blocks/breadcrumb.html``; pages that do not are unaffected, the
  include renders nothing.

The demo warehouse at ``/positionsgrid_view`` wires all seven handlers to real
endpoints and refuses to delete a row that still holds boxes, which is the only
way to see the rejection path on screen.

See ``docs/source/appwidgets/positionsgrid.rst``.

**The history knows what an entry was about.** A ``LogEntry`` only points at
the object that changed, so an application that wants "everything that happened
in this laboratory" had nowhere to hang that context and ended up matching on
the translated ``change_message``. The new ``HistoryRelation`` model (migration
``0019``) attaches any number of objects to one log entry through a generic
foreign key, plus a ``data`` JSONField per relation:

* ``add_log()`` takes ``related_objects=`` (model instances, or
  ``(instance, data)`` tuples -- a bare pk raises ``ValueError``, because a pk
  alone does not say which model it belongs to) and ``extra=``, and it now
  *returns* the ``LogEntry`` it created. A custom ``change_message`` on a
  DELETE is no longer overwritten.
* Entries logged with no authenticated user go to the username in the new
  ``GT_HISTORY_ANONYMOUS_USERNAME`` setting, so a project can point them at its
  own sentinel account instead of losing the entry.
* ``HistoryViewSet`` gained a ``scope_queryset()`` hook, the
  ``related_contenttype`` / ``related_id`` filters and an ``?extra={"k": v}``
  filter that chains one to many keys against the *same* relation row (and
  works on SQLite). Its ``recordsTotal`` is now the scoped universe: the global
  count leaked the platform's volume to every tenant. A project without
  ``GT_HISTORY_ALLOWED_MODELS`` no longer hits a ``TypeError``.
* ``BaseViewSetWithLogs`` was repaired throughout: ``models_log`` replaces the
  attribute that never existed, ``perform_destroy`` passes ``delete(user=)`` for
  ``DeletedWithTrash`` models, ``perform_update`` resolves fields by ``source``,
  and ``get_log_related_objects()`` / ``get_log_extra()`` let a subclass add
  context without overriding the whole method. With ``log_request_metadata``
  the browser, IP, method and path are captured on their own.

**The trash records the context of a deletion, and can be scoped.**
``TrashRelation`` (migration ``0020``) is to ``Trash`` what ``HistoryRelation``
is to ``LogEntry``: ``DeletedWithTrash.delete(..., related_objects=[...])`` --
and the queryset-level ``delete(user=, related_objects=)`` -- record which
objects the deletion belonged to. The first deletion wins: re-deleting
something already in the trash keeps the standing context, and a restore
cascades it away so the next deletion records afresh.

``TrashViewSet`` mirrors the history viewset: the same
``related_contenttype`` / ``related_id`` filters, the same ``scope_queryset()``
hook, and a scoped ``recordsTotal``. Because ``restore`` and ``destroy``
resolve through ``get_object()``, the hook narrows those actions too, which is
what a multi-tenant project needs to keep one tenant out of another's trash.
Restore now respects scoped subclasses, an entry whose object is gone answers
``410`` instead of failing, its permission check is aligned with
``change_trash``, and entries can be filtered by ``deleted_by``.

Both models are registered in the admin. ``djgentelella.utils
.contenttypes_from_labels`` is the single place where ``app_label.model``
strings become ContentTypes, shared by history and trash.

See ``docs/source/history.rst`` and ``docs/source/trash.rst``.

Backwards incompatible
""""""""""""""""""""""""

**The help palette showed its own template placeholders.** The panel builds
each entry by cloning a hidden prototype block and swapping ``$title`` and
``$text`` into it. That block was hidden with ``class="hidden"`` -- a Bootstrap
3 utility, dropped in Bootstrap 4, defined neither by Bootstrap 5 nor anywhere
in this project -- so it was not hidden at all, and the raw ``$title``,
``$byline`` and ``$text`` sat at the bottom of every help panel. It is
``d-none`` now.

The palette had no tests, because it only renders once a ``MenuItem`` points at
it and the demo's menu comes from a management command the suite never runs.
Five browser tests now create that menu item and cover the panel opening, the
prototype staying invisible while keeping its placeholders, a stored entry
listed with its text, and the question mark landing on the label of the field
it documents.

**Two fixes for forms that live in a modal.**

*TinyMCE arrived empty at the server.* The editor writes its content back into
the ``<textarea>`` only when the form is really submitted, through a hook it
installs on the form element. A modal is not submitted -- its javascript reads
the fields and posts JSON -- so the textarea still held whatever it had when
the editor booted, usually nothing, and the field came back *"this field cannot
be blank"* over a box with visible text in it. ``obtainFormAsJSON()`` now
flushes every editor in the form before reading it.

*And it arrived empty at the editor.* The other direction named two widgets by
hand, ``EditorTinymce`` and ``TextareaWysiwyg``, so editing an object whose
field used any other editor widget -- ``VoiceEditorTinymce``, or one a project
subclasses -- wrote the stored value into the hidden textarea and left the
editor blank over data that was there; saving then wiped it. It asks TinyMCE
whether it manages the element instead, which covers every variant.

Both faults reached ``async_notification`` as well -- every message field there
is an ``EmailEditorTinymce`` inside a create/update modal -- so four browser
tests now cover that screen too: the editor's content reaching the server, a
stored message reaching the editor, the preview button, and the widget keeping
``data-widget="EditorTinymce"`` so the shared initialiser runs. Unlike the
compose test, which was the module's only browser coverage, they need no
MailHog.

**``ChunkedUploadBaseView.login_required``.** The upload views refused every
anonymous request with a 403 baked into ``check_permissions()``, so a public
form with a file on it could not work and there was nothing to override short
of rewriting the method. It is a class attribute now. **The default is still
True** -- an open upload endpoint is somewhere for anyone to park files -- and a
project that wants otherwise subclasses:

.. code:: python

    class PublicUpload(ChunkedUploadView):
        login_required = False

Note that an anonymous upload cannot be scoped to its owner, so its 32
character ``upload_id`` is the only thing protecting a partial upload;
``get_max_bytes()`` still caps the size.

**The upload widgets got their missing half.** Their file input has always been
transparent -- that is what makes the whole area a click target and a drop
target -- but nothing was ever drawn underneath, so an empty widget rendered as
a blank white box with no label, no button and no hint that it could be clicked
at all. ``gentelella/css/fileupload.css`` draws that surface, and it is a
backdrop behind the input rather than a replacement for it, so no javascript
changed. The same file gives the widgets a real progress bar (the only sign an
upload was running used to be a percentage inside a 3 rem chip), makes the
download control neutral instead of ``bg-danger`` -- a red button, in a palette
where red is how deletion is spelled, for the one control that only reads --
and turns the delete row into a labelled checkbox that goes red only once it is
armed. ``PDFViewerWidget`` gets the same treatment. Colours and the accent are
``--gt-upload-*`` custom properties.

**``FileChunkedUpload`` on a model ``FileField`` now has tests, and the demo
can actually delete.** The widget already resolved the upload token into the
uploaded file (``value_from_datadict``) and rendered a file that came from the
database (``format_value``), so a ``FileField`` needs nothing but
``widget=FileChunkedUpload`` -- but none of that round trip was covered. Four
browser tests now walk it: the upload is saved into the model field byte for
byte, reopening the record shows the stored file with its download link, saving
without touching it keeps the file, and ticking *delete this file* clears it.

That last one exposed a demo bug: ``ChunkedUploadItem.fileexample`` was
declared without ``blank=True``, so the delete checkbox the widget ships could
only ever produce *"This field cannot be blank"* on submit. Any model that
offers that checkbox needs a field that allows blank; the demo's does now
(migration ``0028``).

**The chunked upload is ours now: blueimp jQuery-File-Upload is gone.** The
upload group was four vendored files; it is one. ``jquery.fileupload.min.js``
is replaced by ``gentelella/js/base/chunkedupload.js``, which speaks the
protocol ``chunked_upload/views.py`` already defined -- slice, POST with a
``Content-Range``, thread the ``upload_id``, then hand over the checksum -- in
about 130 lines of ``fetch``. With it go ``jquery.ui.widget.min.js``, which was
only there because blueimp is built on the jQuery UI widget factory, and
``jquery.iframe-transport.min.js``, a fallback for browsers with no XHR file
upload, meaning IE9. ``spark-md5`` stays: it hashes a file incrementally, which
SubtleCrypto cannot do, and the alternative is holding the whole upload in
memory to checksum it.

``FileChunkedUpload`` and ``PDFViewerWidget`` had a copy each of the same
uploader and the same md5 helper; both now call the shared one.

**This fixes a race that could reject a good upload.** The checksum was
computed in the background while the upload ran, so a small file on a fast
connection finished first and the completion request went out with an empty
``md5`` -- the server answers *"Both 'upload_id' and 'md5' are required"*, and
the file is lost after transferring fine. The hash is now awaited before the
first slice is sent.

Uploads had no browser test at all, which for a widget that is entirely
javascript meant none. Four now push a real 240 kB file through a real browser
and compare what landed on the server byte for byte, check that a small file's
completion call is accepted, that progress is reported, and that a refused
upload rejects with a message to show rather than failing silently.

**FullCalendar 5.11.3 -> 6.1.20, and it no longer has a stylesheet.**
FullCalendar 6 injects its own CSS from javascript, so
``vendors/fullcalendar/main.min.css`` does not exist any more: it is gone from
the readonly CSS bundle and from ``stylesheets.html``, and a project that
linked it by hand has to drop the link. The script is one global build with the
standard plugins already in it, ``index.global.min.js``, instead of
``main.min.js``. ``locales-all.js`` is no longer downloaded either -- it moved
to another package in 6, and no template had ever loaded it.

The widget API this library uses did not change: ``new FullCalendar.Calendar``,
``eventDidMount``, ``eventClick``, ``dateClick`` and the ``EventApi`` setters
all behave the same, and so do the three CSS overrides in ``calendar.html``
that target ``fc-daygrid-day-frame`` and friends -- which is exactly what a
major version is free to rename, so the calendar now has six browser tests
that pin the month grid, the injected styles, those overrides, the event
tooltip and the detail modal. It had none.

**TinyMCE 5.6.1 -> 8.8.2, under the GPL licence key.** From TinyMCE 7 the
editor is GPL-2.0-or-later, and from 8 a self-hosted build **loads read-only
unless a licence key is set**. The shared config now sends
``license_key: 'gpl'``, which is the open source option and matches what this
package ships under. A project that has bought a commercial key sets its own
by overriding the config.

Three things moved in the package itself:

* ``jquery.tinymce.min.js`` is not part of TinyMCE any more -- the jQuery
  integration became a separate project -- so ``$(el).tinymce(config)`` is now
  ``tinymce.init({target: el, ...})``, wrapped in a new
  ``gentelella_tinymce_init()``. Remove the second script tag if you load
  TinyMCE by hand.
* ``models/dom/model.min.js`` is new and **mandatory**: without it the editor
  does not start at all.
* The mobile theme and its ``*.mobile.min.css`` skins are gone.

**The plugin list went from 46 to 29.** ``paste``, ``print``, ``hr``,
``colorpicker``, ``contextmenu``, ``textcolor``, ``noneditable`` and
``tabfocus`` were absorbed into the core; ``bbcode``, ``legacyoutput``,
``spellchecker`` and ``textpattern`` were dropped; ``fullpage``,
``imagetools``, ``template`` and ``toc`` became premium. The toolbar was
trimmed to controls that exist: it had been asking for ``checklist``,
``casechange``, ``permanentpen``, ``formatpainter``, ``pageembed``,
``template``, ``a11ycheck``, ``showcomments`` and ``addcomment``, all premium
and all drawing nothing. ``fontselect``, ``fontsizeselect`` and
``formatselect`` are ``fontfamily``, ``fontsize`` and ``blocks``.
``directionality`` is now actually loaded, so the ``ltr``/``rtl`` buttons the
config had always asked for finally appear. ``paste_preprocess`` takes the
editor as its first argument instead of the plugin.

A project that passed its own ``plugins`` or ``toolbar`` has to check them
against the 29 that remain.

**``VoiceEditorTinymce`` needed one change**, and it is the kind that fails
silently: a toggle button's ``setDisabled`` became ``setEnabled`` in TinyMCE 6,
with the sense reversed. Three browser tests now drive that button with a fake
microphone, so the whole path -- the icon and button registration,
``setActive``, ``setEnabled``, ``setProgressState`` and the notification
manager -- is exercised rather than assumed.

**jQuery-Knob is gone; the dial of ``NumberKnobInput`` is an SVG of our own.**
The old plugin (2015, unmaintained) painted a ``<canvas>`` at a fixed pixel
size -- soft on any display past 1x -- and rebuilt its own keyboard handling
over an input it had emptied of meaning. ``gentelella/js/base/knob.js`` plus
``css/knob.css`` draw a stroked circle instead, and leave the
``<input type="number">`` in the middle of it as the value, the readout and the
focusable control: arrow keys, typing, ``min``/``max``/``step`` validation and
what a screen reader announces are the browser's own, and the svg is
``aria-hidden``, adding only what an input cannot do -- dragging round the dial
and the wheel.

It reads the same ``data-*`` options the old plugin did (``data-min``,
``data-max``, ``data-step``, ``data-width``, ``data-fgcolor``,
``data-bgcolor``, ``data-thickness``), so a form that configured a knob needs
no change; ``data-displayprevious``, ``data-cursor`` and the other
canvas-drawing options are ignored, since there is no canvas to draw. Size and
colour are also ``--gt-knob-size`` and ``--gt-knob-color``, settable in CSS.

Two long-standing bugs went with it. ``NumberKnobInput`` declared
``input_type = 'number'`` but its template never wrote the ``type`` attribute,
so the browser rendered a **text** field -- invisible while a canvas covered
it, and the reason the keyboard did nothing. And ``data-min``/``data-max``/
``data-step`` are now mirrored onto the native ``min``/``max``/``step``, so the
browser's own arrows and validation agree with the dial instead of stepping by
1 through a field declared ``data-step="0.1"``.

**iCheck and switchery are gone; checkboxes, radios and switches are CSS.**
Both libraries worked the same way: hide the real ``<input>`` and paint their
own DOM beside it. That is why every caller had to go through an imperative
API. ``gentelella/css/checks.css`` draws the native input instead
(``appearance: none`` plus a background image), so the control the user clicks
and the field the form submits are the same element again.

What that deletes, rather than ports:

* ``.iCheck('check' | 'uncheck' | 'update')`` -- 13 calls across
  ``permissionmanagement.js``, ``form.common.js``, ``obj_api_management.js``
  and ``custom.js``. Setting ``input.checked`` now repaints on its own.
* ``ifChecked`` / ``ifUnchecked`` / ``ifToggled`` -- 8 handlers, replaced by the
  native ``change`` event.
* The ``data-switchery`` bookkeeping in ``clear_action_form()``: a native form
  reset repaints the switches by itself.
* The hand-written ``<div class="icheckbox_flat-green">…<ins class="iCheck-helper">``
  in ``chunkedupload.html``, ``file.html``, ``pdfviewer.html``,
  ``crud_list.html`` and the javascript template in ``custom.widgets.js``.
* 17 vendored files (both libraries, five skin stylesheets and ten sprite PNGs),
  their ``loaddevstatic`` entries, their four ``pylpfile`` entries and the
  ``.switchery`` overrides in the four theme stylesheets. 36 KB of vendor code
  becomes 6 KB of ours.

**What changes for a project:** the widgets stamp ``gt-check`` (checkbox, radio,
multiple checkbox) or ``gt-switch`` (``YesNoInput``) instead of ``flat``, and
markup written by hand against ``icheckbox_flat-green`` has to become a plain
``<input class="gt-check">``. ``data-checkboxclass`` and ``data-radioclass``,
which chose an iCheck skin, no longer do anything; colour and size are
``--gt-check-color`` and ``--gt-check-size``, settable at runtime.

Three things work now that did not: the indeterminate state (the sprite had no
frame for it, so a partially selected "select all" box drew as empty), keyboard
focus (both libraries hid the input, so the focus ring went with it), and
``prefers-reduced-motion``.

**moment no longer ships all 137 languages to every page.** The bundle carried
``moment-with-locales.min.js``, 375 KB, so that one language could be used. It
now carries moment's core build (59 KB) and the page links the locale file for
the active language separately (~4 KB), through the new ``get_moment_locale``
tag in ``gtsettings``. ``loaddevstatic`` downloads the locales named by
``settings.LANGUAGES``, so a project that narrowed that setting downloads only
its own languages, and one that never set it keeps Django's full list and loses
nothing. English needs no file: it is built into the core build, and a language
moment has no translation for degrades to English rather than 404ing.

daterangepicker keeps moment -- it mutates moment objects in about twenty
places, so dayjs, which is immutable, is not a drop-in replacement for it.

**DataTables 1.12.1 -> 2.3.7, and 14 extensions dropped from the build.** The
bundle carried AutoFill, DateTime, FixedColumns, FixedHeader, KeyTable,
RowGroup, RowReorder, Scroller, SearchBuilder, SearchPanes, Select,
StateRestore, jszip and the colvis/html5/print buttons without a single
reference anywhere in the project -- row selection is hand rolled with
``.gtcheckable`` checkboxes, not the Select extension. What is left is
DataTables itself plus Buttons, ColReorder and Responsive: the vendored
directory goes from 668 KB to 194 KB.

What changes for a project that styles or scripts its own tables:

* **Every class DataTables generates was renamed**, ``dataTables_*`` ->
  ``dt-*``: ``dataTables_wrapper`` is ``dt-container``, ``dataTables_filter``
  is ``dt-search``, ``dataTables_paginate`` is ``dt-paging``,
  ``dataTables_length`` is ``dt-length``, ``dataTables_info`` is ``dt-info``,
  ``dataTables_processing`` is ``dt-processing``, ``dataTables_empty`` is
  ``dt-empty``. The four theme stylesheets were updated, and the
  ``paging_full_numbers``, ``DTTT_button`` (TableTools, gone since 2014),
  ``table.display`` and ``example_alt_pagination`` rules -- all DataTables 1.9
  markup that nothing in this project has emitted for years -- were deleted
  rather than renamed.
* **The ``dom`` string is now a ``layout`` object.**
  ``document.table_default_dom`` is ``document.table_default_layout``; a page
  that set its own ``dom`` (the notification list did) has to be ported.
* **``dt.context[0].nTable`` is gone**; use ``dt.table().node()``.
* The i18n files come from ``plug-ins/2.3.7/i18n/`` and their keys changed.
  ``DATATABLES_SUPPORT_LANGUAGES`` still points at them the same way.

The server side is untouched: ``formatDataTableParams`` already translated the
request into DRF's ``offset``/``limit``/``ordering``, and
``draw``/``recordsTotal``/``recordsFiltered`` mean the same thing in
DataTables 2. Seven browser tests now cover the wrapper, which had none.

**Chart.js 2.9.3 -> 4.5.1.** The whole chart configuration is built by
``djgentelella.chartjs`` and handed to ``new Chart()`` untouched, so the option
vocabulary in the serializers is now Chart.js 4's:

===============================  ==========================================
Chart.js 2                       Chart.js 4
===============================  ==========================================
``options.title``                ``options.plugins.title``
``options.legend``               ``options.plugins.legend``
``options.tooltips``             ``options.plugins.tooltip``
``scales.xAxes: [{...}]``        ``scales: {x: {...}}``
``scale.scaleLabel.labelString`` ``scale.title.text``
``scale.gridLines``              ``scale.grid``
``elements.rectangle``           ``elements.bar``
``dataset.steppedLine``          ``dataset.stepped``
``type: 'horizontalBar'``        ``type: 'bar'`` + ``indexAxis: 'y'``
===============================  ==========================================

The ``get_<option>()`` hooks kept their names -- ``get_title``, ``get_legend``
and ``get_tooltips`` name a chart concept, not a configuration path -- and the
last five rows of that table are translated for a release: a ``get_scales``
still returning ``xAxes``/``yAxes``, an ``elements.rectangle`` block, a
``steppedLine`` dataset key and a ``get_type`` returning ``horizontalBar`` all
keep working. What does **not** survive is a **tooltip callback written for
Chart.js 2**: v3 replaced the ``(item, data)`` arguments with a single context
object, so every function registered in ``document.chartcallbacks`` has to be
rewritten. The two shipped with the library already are.

``options.plugins`` accepts anything, so third party plugins configured through
``get_plugins()`` are passed through untouched.

Two smaller consequences: ``vendors/chartjs/Chart.min.css`` is gone (Chart.js 3
dropped the stylesheet, everything is drawn on the canvas) and the script is
``vendors/chartjs/chart.umd.min.js``. A project that linked either path by hand
has to update it. ``gentelella/widgets/chart.html``, an orphan template no
include ever pointed at, was deleted; the live one is
``gentelella/widgets/chartjs.html``.

**Five javascript libraries are gone from the bundles.** None of them was doing
anything, and all five were downloaded and shipped on every page:

* **Parsley** (42 KB) -- no ``data-parsley-*`` attribute and no ``.parsley()``
  call has ever existed in the project.
* **patternfly-bootstrap-treeview** (27 KB) -- nothing calls ``.treeview()``;
  the ``TreeSelect*`` widgets are drawn by select2. It was also the only
  dependency fetched from a raw ``github.com`` URL.
* **bootstrap-progressbar** -- the plugin only reacts to ``data-transitiongoal``
  and no template sets it, so ``$('.progress .progress-bar').progressbar()``
  animated nothing. The call in ``custom.js`` went with it.
* **jQuery UI's stylesheet** -- downloaded, never linked. The one piece of
  jQuery UI still in the build is blueimp's private ``jquery.ui.widget`` shim,
  which comes with the file-upload plugin.
* **A second copy of interact.js** -- it was downloaded into both
  ``vendors/interact/`` and ``vendors/pdfjs/``, and both were loaded.

A project that referenced any of them directly has to vendor it itself.

**Javascript bundles are now joined with ``;\n``.** A minified vendor file that
ends in an expression without a trailing semicolon, followed by one that starts
with ``(``, used to concatenate into a single call expression: the bundle then
died at parse time and every library after that point disappeared silently.
Nothing to change downstream, but a custom ``pylpfile.py`` copied from this one
should pick up the ``sep=JS_SEP`` argument.

**Library upgrades.** jQuery 3.6.1 -> 3.7.1, inputmask 3.3.11 -> 5.0.10 (only
the jQuery build is shipped now; it already contains the whole library),
bootstrap-daterangepicker 3.0.5 -> 3.1.0, bootstrap-maxlength 1.10.0 -> 2.0.0
and ion-rangeslider 2.3.1 -> 2.3.2. The maxlength counter's
``warningClass`` moved from the Bootstrap 3 ``label label-success`` to
``badge text-bg-success``.

**Two dead asset links removed.** ``vendors/tagify/jQuery.tagify.min.js`` and
``vendors/pdfjs/pdf_viewer.min.css`` were requested by
``gentelella/statics/*.html`` but not downloaded by ``loaddevstatic``: a 404 on
every page in development and a hard failure under
``ManifestStaticFilesStorage``. The uncompressed branch also loaded
fileupload, tagify, TinyMCE and SweetAlert2 twice, and htmx not at all -- htmx
was only in the compressed bundle, and its vendor folder was misspelled
``vendors/htmlx/``. It is ``vendors/htmx/`` now.

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

**PDF viewer widget.** ``PDFViewerWidget`` displays a PDF from a ``FileField``
with page navigation and zoom, rendering client-side through pdf.js;
``PDFFileField`` validates the extension, the content type and the magic bytes,
and uploads go through a PDF-specific chunked endpoint
(``upload_pdf_view`` / ``upload_pdf_done``) rather than the generic one. Demo at
``/pdfviewer/``.

``gentelella/css/pdfviewer_widget.css`` is linked from the base template rather
than left for each project to remember, on the same reasoning as ``maps.css``:
without it the canvas has no size and the controls no layout.

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

``pdf.js`` 4.6.82 -> 6.2.108. ``globalThis.pdfjsLib`` is still exposed by the
``.mjs`` build and ``getViewport``/``render`` are unchanged, but **6.x dropped
``getDocument``'s bare-string shorthand**: a relative string, an absolute string
and even a ``URL`` object are all rejected with "expected either ``data``,
``range``, or ``url`` parameter", and the rejection is asynchronous, so the
canvas simply stays blank at its default 300x150. Both call sites now pass
``{url: ...}``.
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
