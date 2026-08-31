=====
Icons
=====

Django Gentelella Widgets includes several icon libraries that can be used throughout your application for navigation, buttons, status indicators, and more.

Four sets ship with the package, each with a searchable reference page in the
demo, reachable from the sidebar's **Icons** menu:

.. list-table::
   :header-rows: 1
   :widths: 22 12 16 50

   * - Set
     - Icons
     - Demo page
     - Loaded
   * - Font Awesome 4.7
     - 786
     - ``/icons/fontawesome``
     - always
   * - Friconix
     - 1559
     - ``/icons/friconix``
     - always
   * - Material Design Icons
     - 7448
     - ``/icons/mdi``
     - opt-in, ``use_mdi``
   * - Country flags
     - 266
     - ``/icons/flags``
     - always (sprite fetched on demand)

Each page reads its set from what the browser already loaded, so the lists
cannot drift from the versions ``loaddevstatic`` downloaded.


Font Awesome 4.7.0
==================

Font Awesome is the primary icon library used in djgentelella. It is automatically loaded when using the base template.

Installation
------------

Font Awesome is included via ``loaddevstatic`` and bundled into the vendor files:

.. code:: bash

    python manage.py loaddevstatic

Usage
-----

Use the ``<i>`` tag with Font Awesome classes:

.. code:: html

    <i class="fa fa-home"></i>
    <i class="fa fa-user"></i>
    <i class="fa fa-cog"></i>

Common Icons in djgentelella
----------------------------

**Navigation:**

- ``fa fa-home`` - Home
- ``fa fa-bars`` - Menu/hamburger
- ``fa fa-chevron-down`` - Expand
- ``fa fa-chevron-right`` - Navigate

**Actions:**

- ``fa fa-plus`` - Add
- ``fa fa-plus-circle`` - Add (circled)
- ``fa fa-pencil`` - Edit
- ``fa fa-trash`` - Delete
- ``fa fa-save`` - Save
- ``fa fa-download`` - Download
- ``fa fa-upload`` - Upload

**Status:**

- ``fa fa-check`` - Success/complete
- ``fa fa-times`` - Error/close
- ``fa fa-exclamation-triangle`` - Warning
- ``fa fa-info-circle`` - Information
- ``fa fa-spinner fa-spin`` - Loading

**Objects:**

- ``fa fa-user`` - User
- ``fa fa-users`` - Users/group
- ``fa fa-file`` - File
- ``fa fa-folder`` - Folder
- ``fa fa-calendar`` - Calendar
- ``fa fa-table`` - Table/data
- ``fa fa-cog`` - Settings
- ``fa fa-envelope`` - Email/notification

Reference
---------

For a complete list of available icons, see the `Font Awesome 4.7 Cheatsheet <https://fontawesome.com/v4/cheatsheet/>`_.


Country Flags
=============

All 266 flag-icons flags ship with djgentelella as a single gzipped SVG sprite,
``gentelella/flags/flags.4x3.svg.gz`` (~650 KB). Nothing is downloaded at build
or install time, and a page pays only for the flags it actually shows.

Template tag
------------

.. code:: html

    {% load gtflags %}

    {% flag 'us' %}                   <!-- United States -->
    {% flag 'gb' %}                   <!-- United Kingdom -->
    {% flag 'cr' %}                   <!-- Costa Rica -->
    {% flag 'gb-sct' %}               <!-- Scotland -->
    {% flag 'cr' square=True %}       <!-- cropped to a square -->
    {% flag 'cr' css_class="me-2" title="Costa Rica" %}

Codes are ISO 3166-1 alpha-2, lowercase, plus the subdivision and organisation
codes flag-icons draws (``es-ct``, ``gb-eng``, ``gb-nir``, ``gb-sct``,
``gb-wls``, ``es-ga``, ``eu``, ``un``, ``cefta``). An unknown code renders
nothing.

The tag emits an ``<svg>`` pointing into the sprite, so however many flags a
page shows, the browser fetches the sprite once and caches it across pages:

.. code:: html

    <svg class="gt-flag" role="img" aria-label="CR">
        <use href="/flags/sprite.svg#fi-cr"></use>
    </svg>

Sizing comes from ``gentelella/css/flags.css``, always loaded by the base
template. ``.gt-flag`` is ``1.333em × 1em``; set ``font-size`` on the element,
or override the two rules, to change it.

Serving one flag
----------------

``/flags/<code>.svg`` returns a single flag, for an ``<img>``, a CSS
``background-image`` or anywhere a URL is needed:

.. code:: html

    {% load gtflags %}
    <img src="{% flag_url 'cr' %}" alt="Costa Rica">
    <img src="{% flag_url 'cr' size=48 shape='circle' %}" alt="Costa Rica">

Query parameters, all optional:

``size``
    Width in pixels. The height follows the flag's ratio, or matches ``size``
    when a shape is given.

``shape``
    ``circle`` or ``rounded``. Crops the flag to its centred square and clips
    it. Anything else is ignored.

``title``
    Accessible name, emitted as a ``<title>`` child of the SVG.

From Python, use :func:`djgentelella.flags.flag_url`, which takes the same
parameters and appends the package version so an upgraded sprite is not masked
by the endpoint's long-lived cache headers.

Flags in a select2 autocomplete
-------------------------------

``AutocompleteSelectImage`` renders each option through ``decore_img_select2``,
which draws whatever the lookup's ``get_url()`` returns. Point that at
``flag_url`` and the dropdown shows a flag per option, fetching only the flags
of the options on screen:

.. code:: python

    # myapp/gtselects.py
    from djgentelella.flags import flag_url
    from djgentelella.groute import register_lookups
    from djgentelella.views.select2autocomplete import BaseSelectImg2View


    @register_lookups(prefix='countryflag', basename='countryflagbasename')
    class CountryFlagLookup(BaseSelectImg2View):
        model = Country
        fields = ['name']

        def get_url(self, obj):
            return flag_url(obj.code)

.. code:: python

    # myapp/forms.py
    from djgentelella.widgets.selects import AutocompleteSelectImage


    class PersonForm(GTForm, forms.ModelForm):
        class Meta:
            model = Person
            fields = '__all__'
            widgets = {'country': AutocompleteSelectImage('countryflagbasename')}

The demo shows it in two places: ``/imageselect/create/``, where the same
widget sits beside one fed by uploaded ``FileField`` images -- the only
difference is what ``get_url()`` returns -- and the person form, where it
also has to survive being cloned into a formset row and a modal.

Updating the sprite
-------------------

Only needed when flag-icons releases new artwork. Bump ``FLAG_ICONS_VERSION`` in
``djgentelella/management/commands/buildflagsprite.py`` and run:

.. code:: bash

    cd demo && python manage.py buildflagsprite

It downloads every flag, namespaces each file's internal ids so the symbols
cannot borrow each other's gradients and clip paths, writes the sprite and
refuses to write a partial one. Commit the result.

.. note::

    Before 0.6.0 flags were CSS classes (``<i class="fi fi-cr"></i>``) backed by
    ``djgentelella.flags.vendors.min.css``, a 6.35 MB stylesheet that
    base64-inlined all 532 SVGs and had to be downloaded in full to show a
    single flag. It and the ``use_flags`` define are gone; replace
    ``<i class="fi fi-xx"></i>`` with ``{% flag 'xx' %}`` and
    ``<i class="fi fi-xx fis"></i>`` with ``{% flag 'xx' square=True %}``.

Material Design Icons 7.4.47
============================

7448 icons as a webfont. **Opt-in**: the stylesheet is 347 KB and the font
another 403 KB, so it is not loaded unless a template asks for it.

Enabling it
-----------

.. code:: html

    {% extends 'gentelella/base.html' %}
    {% load gtsettings %}

    {% block pre_head %}
        {% define_true "use_mdi" %}
    {% endblock %}

Or globally, for a project that uses these icons everywhere:

.. code:: python

    DEFAULT_JS_IMPORTS = {
        'use_mdi': True,
    }

Usage
-----

Two classes, the family and the icon:

.. code:: html

    <i class="mdi mdi-home"></i>
    <i class="mdi mdi-account-circle mdi-24px"></i>
    <i class="mdi mdi-loading mdi-spin"></i>
    <i class="mdi mdi-chevron-right mdi-rotate-90"></i>

Icons take the surrounding text colour and scale with ``font-size``. Sizes:
``mdi-18px``, ``mdi-24px``, ``mdi-36px``, ``mdi-48px``. Effects: ``mdi-spin``,
``mdi-flip-h``, ``mdi-flip-v``, ``mdi-rotate-45`` through ``mdi-rotate-315``.

Browse them at ``/icons/mdi`` in the demo, or at
`pictogrammers.com/library/mdi <https://pictogrammers.com/library/mdi/>`_.

.. note::

    The icons ship inside the Python package -- nothing is fetched from a CDN at
    runtime -- but only the **woff2** is downloaded. Upstream's ``@font-face``
    also lists eot, woff and ttf, the same glyphs in three encodings no
    supported browser would pick, so ``loaddevstatic`` rewrites the rule to the
    woff2 alone rather than shipping 2.3 MB of fonts. It is deliberately kept
    out of the pylp bundles: ``urlreplace`` would base64 the font into
    ``djgentelella.vendors.min.css``, and the point of a webfont is that the
    browser fetches one file and caches it.

Friconix
========

Friconix draws 1559 icons as inline SVG from a single script, with no font and
no stylesheet. It is always loaded, in ``djgentelella.vendors.header.min.js``.

Class syntax
------------

``fi-`` + a **six letter mask** + ``-`` + the icon name:

.. code:: html

    <i class="fi-cnluxl-check"></i>
    <i class="fi-xnsuxl-user-circle"></i>
    <i class="fi-cnlusx-cog"></i>

Each position of the mask sets one property, and each value also has a class of
its own that overrides that position:

.. list-table::
   :header-rows: 1
   :widths: 5 15 45 35

   * - Pos
     - Property
     - Mask letters
     - Equivalent class
   * - 1
     - Shape
     - ``t`` triangle, ``e`` equilateral, ``c`` circle, ``s`` square,
       ``h`` hexagon, ``o`` octagon, ``x`` none
     - ``fi-circle``, ``fi-square``, ``fi-no-shape``, ...
   * - 2
     - Thickness
     - ``t`` thin, ``n`` normal, ``x`` wide
     - ``fi-thin``, ``fi-normal``, ``fi-wide``
   * - 3
     - Style
     - ``l`` line, ``s`` solid, ``p`` prohibited, ``x`` none
     - ``fi-line``, ``fi-solid``, ``fi-prohibited``
   * - 4
     - Rotation
     - ``u`` 0°, ``r`` 90°, ``d`` 180°, ``l`` 270°
     - ``fi-up``, ``fi-right``, ``fi-down``, ``fi-left``
   * - 5
     - Effect
     - ``x`` none, ``h``/``v`` flip, ``s`` spin, ``p`` pulse
     - ``fi-spin``, ``fi-pulse``
   * - 6
     - Size
     - ``t`` 0.3em, ``s`` 0.5em, ``n`` 1em, ``l`` 1.33em, ``x`` 1.66em,
       ``2``-``9`` Nem
     - ``fi-size-s``, ``fi-2x``, ...

Icons inherit the surrounding text colour (``fill="currentColor"``) and scale
with the mask's size letter.

.. warning::

    ``fi-flip-h`` is broken upstream -- friconix maps it to the same value as
    ``fi-flip-v``. Put an ``h`` in position 5 of the mask for a horizontal flip.

Browsing the icons
------------------

The demo carries a searchable grid of every icon at ``/friconix``. It enumerates
friconix's own ``paths`` global in the browser, so it always matches the version
``loaddevstatic`` downloaded, and the mask field lets you preview a whole style
at once.

Dynamic content
---------------

Friconix scans the document **once**, when the page finishes loading, and has no
``MutationObserver``. Any icon added later -- a formset row, a reopened modal, a
DataTables redraw -- would stay an empty ``<i>``. djgentelella rescans for you
from ``gt_find_initialize()``, the same hook every widget re-initialises through,
so this is handled for anything built the usual way. If you inject markup by
hand, call it yourself:

.. code:: javascript

    $('#target').html(markup);
    gt_friconix_refresh();

.. note::

    ``friconix.js`` is fetched from ``https://friconix.com/cdn/friconix.js``,
    which serves no version and is the only source -- the npm package was
    unpublished in 2020 and there is no cdnjs entry or public repository. The
    script is pinned by nothing but that URL.

Timeline/StoryMap Icons
=======================

Specialized icons for timeline and storymap widgets are included when using readonly widgets.

Enable these icons by setting ``use_readonlywidgets``:

.. code:: html

    {% extends 'gentelella/base.html' %}
    {% load gtsettings %}

    {% block pre_head %}
        {% define_true "use_readonlywidgets" %}
    {% endblock %}


Using Icons in MenuItem
=======================

When creating menu items, you can set the ``icon`` field to display an icon next to the menu title.

.. code:: python

    from djgentelella.models import MenuItem

    MenuItem.objects.create(
        title='Dashboard',
        url_name='dashboard',
        category='sidebar',
        is_reversed=True,
        icon='fa fa-tachometer',  # Font Awesome icon
        only_icon=False
    )

For footer sidebar items where you want only the icon displayed:

.. code:: python

    MenuItem.objects.create(
        title='Logout',
        url_name='/accounts/logout/',
        category='sidebarfooter',
        is_reversed=False,
        icon='fa fa-power-off',
        only_icon=True  # Only show the icon, not the title
    )
