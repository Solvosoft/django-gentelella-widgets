Form widgets of the catalog
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Nine widgets for the field types a form builder expects: stars, a switch, a
slider, a free combobox, a list of values searched in a modal, a Markdown
editor, an image cropped before upload, a QR code and an address found on the
map. Each one is a plain Django widget -- its own template, an initializer in
``base.js`` registered in ``document.gtwidgets`` -- so it works in any form,
in a design (``djgentelella.designs``) and in djgentelella-editor through
:mod:`djgentelella.forms.widgetmap`.

All of them are on the demo page ``/formwidgets/`` (``demoapp/formwidgets/``).

--------------------------------
In the widget table
--------------------------------

:func:`~djgentelella.forms.widgetmap.widget_choices` offers them at the end of
the list of their kind, so no default changes:

=============  ==========================================================
Kind           New widgets
=============  ==========================================================
``integer``    ``StarRatingInput``, ``RangeInput``
``decimal``    ``RangeInput``
``float``      ``RangeInput``
``boolean``    ``SwitchInput``
``string``     ``ComboboxInput``, ``QRCodeInput``, ``GeocodedAddressInput``
``url``        ``QRCodeInput``
``text``       ``MarkdownInput``
``image``      ``ImageCropInput``
=============  ==========================================================

The table builds a widget without arguments: ``ComboboxInput`` then has no
list (it is free text with select2) and ``GeocodedAddressInput`` no point
field (it only searches). ``LOVPopupSelect`` needs the name of a LOV and the
range pair is a form field of two values, so neither is in the table.

--------------------------------
Options
--------------------------------

:data:`~djgentelella.forms.widgetmap.WIDGET_OPTIONS` declares the options of
each widget -- the keyword arguments of its constructor a design (or
djgentelella-editor) may set -- as a JSON schema per option, with a ``title``
for an inspector:

=========================  ================================================
Widget                     Options
=========================  ================================================
``StarRatingInput``        ``stars`` (1-10), ``readonly``
``RangeInput``             ``min_value``, ``max_value``, ``step`` (> 0),
                           ``show_value``, ``suffix``
``ComboboxInput``          ``choices``: texts or ``[value, label]`` pairs
``QRCodeInput``            ``scan``, ``readonly``, ``size`` (64-1024)
``ImageCropInput``         ``aspect_ratio``, ``max_width``, ``max_height``,
                           ``output_type``, ``quality``
``GeocodedAddressInput``   ``point_field``, ``replace_text``
``MarkdownInput``          ``rows`` (2-60)
``SwitchInput``            ``label``
=========================  ================================================

.. code:: python

    from djgentelella.forms import widgetmap

    widgetmap.widget_options('StarRatingInput')   # the object schema
    widgetmap.validate_widget_options('RangeInput', {'step': 0})
    # [Error(path='$.step', message='not greater than 0')]
    widgetmap.build_widget('StarRatingInput', {'stars': 10})  # the instance

Only the declared options reach the constructor, so a design never passes
``attrs`` or any other keyword argument; ``build_widget`` raises
``ValueError`` on invalid options. In a design they are the
``widget_options`` of a form (see :doc:`../designs`).

--------------------------------
Libraries
--------------------------------

Three libraries, downloaded by ``loaddevstatic`` and **loaded only by the
widget that needs them**, the first time it does (``gt_load_script`` in
``gentelella/js/base/formwidgets.js``): no pylp bundle carries them, so a page
without these widgets pays nothing.

=======================  ========  ============  =========================
Library                  Version   Licence       Used by
=======================  ========  ============  =========================
Cropper.js               1.6.2     MIT           ``ImageCropInput``
qrcode-generator         1.4.4     MIT           ``QRCodeInput``, ``{% qrcode %}``
jsQR                     1.4.0     Apache-2.0    ``QRCodeInput(scan=True)``
=======================  ========  ============  =========================

The Markdown preview and the ``markdown`` filter need the ``[markdown]``
extra (Python-Markdown and nh3)::

    pip install "djgentelella[markdown]"

Stars, switch, range, combobox and the popup LOV need nothing new. The styles
are in ``gentelella/css/formwidgets.css``, always linked.

--------------------------------
Stars
--------------------------------

:class:`~djgentelella.widgets.extras.StarRatingInput` -- an integer from 0 to
``stars``. The value lives in a ``<input type="number">`` (what a browser
without javascript shows); the stars are buttons, with the arrow keys and a
clear button. ``readonly=True`` only draws them. Validate the range on the
server with :class:`~djgentelella.fields.extras.RatingField`:

.. code:: python

    from djgentelella.fields.extras import RatingField

    class ReviewForm(GTForm, forms.ModelForm):
        rating = RatingField(stars=5, required=False, empty_value=0)

With a model field alone, the widget still draws ``stars`` stars (it ignores
the 0..32767 a ``PositiveSmallIntegerField`` passes), but nothing stops a
crafted 9: add ``MaxValueValidator`` to the model or use ``RatingField``.

--------------------------------
Switch
--------------------------------

:class:`~djgentelella.widgets.extras.SwitchInput` -- a ``BooleanField`` drawn as
Bootstrap 5's ``form-switch``, with an optional ``label`` beside it. Unlike
``YesNoInput`` there is no "No"/"Yes" text and no show/hide of related fields.

.. code:: python

    widgets = {'active': SwitchInput(label=_('Enabled'))}

--------------------------------
Range
--------------------------------

:class:`~djgentelella.widgets.extras.RangeInput` -- ``<input type="range">`` with
its value beside it (``suffix`` appended: ``' %'``). It is a ``NumberInput``
for Django, so ``IntegerField(min_value=, max_value=)`` passes its limits to
it; ``min_value``, ``max_value`` and ``step`` given to the widget win (a model
``IntegerField`` passes the whole range of its column). A range always posts a
value: use it on a field with a default.

:class:`~djgentelella.fields.extras.RangePairField` is a minimum and a maximum
in one field, two ranges (``RangePairInput``) that clean to ``(low, high)``;
``low > high`` is an error. ``decimal_places=`` makes them decimals.

.. code:: python

    budget = RangePairField(min_value=0, max_value=1000, step=50, suffix=' $')

--------------------------------
Combobox
--------------------------------

:class:`~djgentelella.widgets.extras.ComboboxInput` -- select2 with ``tags``:
choose from ``choices`` or write a new value. It is for a text field: the
value is the text itself and one that is not in the list is shown selected
when the form is edited. Only the field's ``max_length`` limits it.

.. code:: python

    widgets = {'category': ComboboxInput(choices=['Hardware', 'Software'])}

--------------------------------
List of values in a modal
--------------------------------

:class:`~djgentelella.widgets.lov.LOVPopupSelect` -- a LOV (``lov.rst``) searched
in a modal, page by page (the LOV's ``page_size``), for lists too long for a
dropdown. Same endpoint, parents and validation as ``LOVSelect``:

.. code:: python

    product = LOVChoiceField('products', widget=LOVPopupSelect)

The value is the only option of a hidden ``<select>``; a read-only box shows
its label, a button opens the search and another clears it. A parent that
changes empties it. The modal is moved to ``<body>`` when the widget starts,
so it is not clipped by a panel.

--------------------------------
Markdown
--------------------------------

:class:`~djgentelella.widgets.markdown.MarkdownInput` -- a textarea with a
toolbar (bold, italic, heading, link, lists, quote, code) and a "Preview" tab.

The preview is rendered by the server: ``POST gtapis/markdown/preview/``
(``gt-markdown-preview``, login and CSRF token required, at most
``GT_MARKDOWN_MAX_LENGTH`` characters, 100000 by default) runs
:func:`djgentelella.markdown.render_markdown`, which converts with
Python-Markdown (``extra``, ``sane_lists``) and **cleans the HTML with the
allow list of the design pages** (``designs.sanitize.clean_html``, nh3): no
``<script>``, ``on*`` handlers, ``javascript:`` links, iframes or ``data-*``
attributes that could start a widget. Only that cleaned output is marked safe;
the text of the user never is. Show the saved text the same way:

.. code:: html+django

    {% load gtmarkdown %}
    {{ article.body|markdown }}

--------------------------------
Image with crop
--------------------------------

:class:`~djgentelella.widgets.imagecrop.ImageCropInput` -- an ``ImageField``
whose file is cropped in the browser before it is sent. Choosing a file opens
Cropper.js with a box of ``aspect_ratio`` (``1``, ``16 / 9``; ``None`` is
free), with rotate and reset; "Apply" replaces the file of the input with the
crop, at most ``max_width`` x ``max_height``, encoded as ``output_type``
(``image/jpeg`` by default). It stays a normal ``<input type="file">``: the
form posts multipart, an edit form shows the current image and can clear an
optional one, and without javascript the file goes as chosen.

The browser can be skipped, so the server checks again with
:class:`~djgentelella.fields.imagecrop.ImageCropField`: Pillow must open it
(what is not an image is ``invalid_image``), its format must be in
``formats`` (JPEG, PNG, WEBP and GIF by default) and its size at most
``max_size`` bytes (``GT_IMAGE_MAX_SIZE``, 5 MB by default).

.. code:: python

    photo = ImageCropField(required=False, aspect_ratio=1, max_width=800,
                           max_height=800)

--------------------------------
QR code
--------------------------------

:class:`~djgentelella.widgets.extras.QRCodeInput` -- a text input whose value
is drawn as a QR code while it is typed (``size`` pixels). ``scan=True`` adds
a camera button that reads a code: the browser's ``BarcodeDetector`` where
there is one, jsQR elsewhere. The camera needs a secure context (https or
localhost); outside one the button stays hidden. ``readonly=True`` shows the
code of a value that cannot be edited.

To show a value as a code in a list or a detail page:

.. code:: html+django

    {% load gtqrcode %}
    {% qrcode ticket.code 120 %}

--------------------------------
Geocoded address
--------------------------------

:class:`~djgentelella.widgets.geocoding.GeocodedAddressInput` -- an address
(text) and a button that finds it; choosing a place writes its ``"lat,lng"``
into ``point_field``, a field of the same form (usually a ``GTPointField``
with ``MapPointInput``, whose marker moves). ``replace_text=True`` also writes
the address the geocoder found.

.. code:: python

    class Office(models.Model):
        address = models.CharField(max_length=250)
        location = GTPointField(blank=True)

    widgets = {'address': GeocodedAddressInput(point_field='location')}

**The geocoder is off by default**: the widget is then a plain text input and
nothing leaves the server. It is turned on with a class::

    GT_GEOCODER = 'djgentelella.geocoding.NominatimGeocoder'
    GT_GEOCODER_OPTIONS = {
        'url': 'https://nominatim.example.org/search',
        'user_agent': 'my-project/1.0 (admin@example.org)',
        'countrycodes': 'cr',
    }

The browser never calls the service: it asks ``gtapis/geocode/?q=``
(``gt-geocode``, login required), which answers 404 while there is no
geocoder, 400 without a query and 502 when the service fails. Any class with
``search(query, limit)`` returning :class:`djgentelella.geocoding.Place`
objects works -- a commercial service, a local gazetteer, or a fake in tests
(the demo's, ``demoapp/geocoding.py``, is a short offline list). The public
Nominatim allows one request per second: for real traffic, run your own.
