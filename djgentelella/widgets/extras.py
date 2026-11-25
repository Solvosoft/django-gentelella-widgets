"""Form widgets of the APEX catalog (2.1): stars, switch, range, combobox and QR.

Each one is a plain Django widget with its own template and a small
initializer in ``base.js`` (registered in ``document.gtwidgets`` under its
class name). None of them needs a field of its own to work, but the stars and
the range pair have one that validates on the server what the widget draws
in the browser (:mod:`djgentelella.fields.extras`).
"""

from django.forms import CheckboxInput as DJCheckboxInput, \
    MultiWidget, NumberInput as DJNumberInput
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _

from .core import Select, TextInput, js_widget_name, update_kwargs


class StarRatingInput(DJNumberInput):
    """An integer from 0 to ``stars``, picked by clicking stars.

    The real input is a ``<input type="number">`` with ``min``/``max``, so the
    value posts as a number and the widget degrades to a number box without
    javascript. ``readonly=True`` draws the stars without letting them change
    (the value still posts). 0, or empty, is "not rated".
    """

    template_name = 'gentelella/widgets/star_rating.html'

    def __init__(self, attrs=None, stars=5, readonly=False, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self),
                                  base_class='form-control gt-rating-input ')
        attrs = attrs or {}
        self.stars = int(stars)
        if self.stars < 1:
            raise ValueError('StarRatingInput needs at least one star')
        attrs.setdefault('min', 0)
        attrs.setdefault('max', self.stars)
        attrs.setdefault('step', 1)
        attrs['data-stars'] = self.stars
        self.readonly = readonly
        if readonly:
            attrs['readonly'] = True
            attrs['data-readonly'] = 'true'
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        # A model field passes the range of its column (0..32767 for a
        # PositiveSmallIntegerField): the stars are the range.
        context['widget']['attrs'].update(min=0, max=self.stars, step=1)
        try:
            current = int(float(value)) if value not in (None, '') else 0
        except (TypeError, ValueError):
            current = 0
        context['stars'] = [
            {'value': index, 'on': index <= current,
             'label': _('%(value)s of %(stars)s') % {
                 'value': index, 'stars': self.stars}}
            for index in range(1, self.stars + 1)]
        context['readonly'] = self.readonly
        context['clear_title'] = _('Clear')
        return context


class SwitchInput(DJCheckboxInput):
    """A boolean drawn as the Bootstrap 5 ``form-switch``.

    Unlike :class:`~djgentelella.widgets.core.YesNoInput` (the ``gt-switch``
    with "No"/"Yes" around it and show/hide of related fields), this is the
    plain Bootstrap switch; ``label`` is the text beside it.
    """

    template_name = 'gentelella/widgets/switch.html'

    def __init__(self, attrs=None, label=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self),
                                  base_class='form-check-input ')
        attrs = attrs or {}
        attrs['role'] = 'switch'
        self.label = label
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['switch_label'] = self.label
        return context


class RangeInput(DJNumberInput):
    """A number picked with a slider (``<input type="range">``), its value
    shown beside it.

    It is a ``NumberInput`` for Django, so ``IntegerField(min_value=,
    max_value=)`` and ``DecimalField`` pass their ``min``, ``max`` and ``step``
    to it, but ``min_value``, ``max_value`` and ``step`` given here win. A
    range always has a value -- the browser posts the middle when none was
    set -- so it suits a field with a default better than an optional one.
    """

    input_type = 'range'
    template_name = 'gentelella/widgets/range.html'

    def __init__(self, attrs=None, min_value=None, max_value=None, step=None,
                 show_value=True, suffix='', extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self),
                                  base_class='form-range ')
        attrs = attrs or {}
        # Kept apart and applied again on render: a form field writes its own
        # min/max into the widget (a model IntegerField the whole range of
        # the database column), and the constructor has to win.
        self.fixed = {key: value for key, value in (
            ('min', min_value), ('max', max_value), ('step', step))
            if value is not None}
        attrs.update(self.fixed)
        self.show_value = show_value
        self.suffix = suffix
        if suffix:
            attrs['data-suffix'] = suffix
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['attrs'].update(self.fixed)
        # In the widget dict, not the context: RangePairInput renders each
        # range from its subwidget dict alone.
        context['widget']['show_value'] = self.show_value
        context['widget']['suffix'] = self.suffix
        return context


class RangePairInput(MultiWidget):
    """Two :class:`RangeInput` for a minimum and a maximum (``RangePairField``).

    The value is a ``(low, high)`` pair; a ``"low,high"`` string is read too.
    """

    template_name = 'gentelella/widgets/range_pair.html'

    def __init__(self, attrs=None, min_value=None, max_value=None, step=None,
                 suffix=''):
        widgets = [RangeInput(attrs=attrs, min_value=min_value,
                              max_value=max_value, step=step, suffix=suffix)
                   for _index in range(2)]
        super().__init__(widgets, attrs=None)

    def decompress(self, value):
        if not value:
            return [None, None]
        if isinstance(value, str):
            value = value.split(',')
        value = list(value)[:2]
        return value + [None] * (2 - len(value))

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['labels'] = [_('Minimum'), _('Maximum')]
        return context


class ComboboxInput(Select):
    """Pick a value of a list or type a new one: select2 with ``tags``.

    For a text field (``CharField``): the value is the text itself, so a
    value that is not in ``choices`` is still shown selected when the form is
    edited. ``choices`` is a list of strings or of ``(value, label)`` pairs.
    Only the length of the field limits what can be written.
    """

    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self),
                                  base_class='form-control ')
        attrs = attrs or {}
        attrs['data-tags'] = 'true'
        super().__init__(attrs, choices=self.normalize(choices),
                         extraskwargs=False)

    @staticmethod
    def normalize(choices):
        return [choice if isinstance(choice, (list, tuple)) else (choice, choice)
                for choice in choices]

    def optgroups(self, name, value, attrs=None):
        groups = super().optgroups(name, value, attrs)
        known = {str(option['value']) for _group, options, _index in groups
                 for option in options}
        index = len(groups)
        if '' not in known:
            # The empty option select2 needs for the placeholder and to clear.
            groups.insert(0, (None, [self.create_option(
                name, '', '', False, 0, attrs=attrs)], 0))
            index += 1
        for item in value:
            if item in ('', None) or str(item) in known:
                continue
            groups.append((None, [self.create_option(
                name, item, item, True, index, attrs=attrs)], index))
            index += 1
        return groups


class QRCodeInput(TextInput):
    """A text value drawn as a QR code while it is typed.

    ``scan=True`` adds a button that reads a QR code with the camera
    (the browser's ``BarcodeDetector`` or, where it is missing, jsQR); it is
    hidden outside a secure context, where the browser denies the camera.
    ``readonly=True`` shows the code of the value and a read-only input.
    ``size`` is the side of the code in pixels.
    """

    template_name = 'gentelella/widgets/qrcode.html'

    def __init__(self, attrs=None, scan=False, readonly=False, size=160,
                 extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self))
        attrs = attrs or {}
        attrs['data-size'] = int(size)
        if scan:
            attrs['data-scan'] = 'true'
        if readonly:
            attrs['readonly'] = True
        self.scan = scan and not readonly
        super().__init__(attrs, extraskwargs=False)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget_attrs = context['widget']['attrs']
        widget_attrs['data-qr-lib'] = static('vendors/qrcode/qrcode.js')
        if self.scan:
            widget_attrs['data-jsqr-lib'] = static('vendors/jsqr/jsQR.js')
        context['scan'] = self.scan
        context['scan_title'] = _('Read a QR code with the camera')
        return context
