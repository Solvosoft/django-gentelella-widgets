"""From a model field to the djgentelella widget that edits it.

The table every ModelForm otherwise repeats in ``Meta.widgets``: a
``DateField`` gets ``genwidgets.DateInput``, a ``TextField`` a
``Textarea``, a foreign key to a tree a ``TreeSelect``. Use it as the
``formfield_callback`` of a ModelForm::

    from djgentelella.forms.forms import GTForm
    from djgentelella.forms.widgetmap import gt_formfield_callback

    class PersonForm(GTForm, forms.ModelForm):
        class Meta:
            model = Person
            fields = '__all__'
            formfield_callback = gt_formfield_callback

``Meta.widgets`` still wins for the fields it names. The same table drives
djgentelella-editor, which offers :func:`widget_choices` per field.

Some widgets take options (the stars of ``StarRatingInput``, the list of a
``ComboboxInput``...): :data:`WIDGET_OPTIONS` declares them, as a JSON
schema per option, and :func:`build_widget` builds a widget with options that
:func:`validate_widget_options` accepted. Only the options declared there
reach the constructor: a design never passes free keyword arguments.

The *kind* of a field is its type name (:data:`FIELD_KINDS`), except that a
field with ``choices`` is ``'choices'``, a nullable ``BooleanField`` is
``'nullboolean'`` and a ``GTPointField`` is ``'point'``.
"""

import math

from django.db import models
from django.db.models.fields.files import FileField, ImageField
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _
from tree_queries.models import TreeNode

from djgentelella.designs.jsonschema import Error, validate
from djgentelella.fields.maps import GTPointField
from djgentelella.fields.tree import GentelellaTreeNodeChoiceField, \
    GentelellaTreeNodeMultipleChoiceField
from djgentelella.forms.querysets import permission_queryset

#: ``(model field class, kind)``, matched in order with ``isinstance``, so a
#: subclass (EmailField) is listed before its base (CharField).
FIELD_KINDS = [
    (models.BigAutoField, 'auto'),
    (models.SmallAutoField, 'auto'),
    (models.AutoField, 'auto'),
    (models.BooleanField, 'boolean'),
    (models.EmailField, 'email'),
    (models.URLField, 'url'),
    (models.SlugField, 'slug'),
    (models.CharField, 'string'),
    (models.TextField, 'text'),
    (models.DateTimeField, 'datetime'),
    (models.DateField, 'date'),
    (models.TimeField, 'time'),
    (models.DurationField, 'duration'),
    (models.DecimalField, 'decimal'),
    (models.FloatField, 'float'),
    (models.IntegerField, 'integer'),
    (models.UUIDField, 'uuid'),
    (models.GenericIPAddressField, 'ip'),
    (models.JSONField, 'json'),
    (models.BinaryField, 'binary'),
    (ImageField, 'image'),
    (FileField, 'file'),
    (models.FilePathField, 'filepath'),
    (models.OneToOneField, 'o2o'),
    (models.ForeignKey, 'fk'),
    (models.ManyToManyField, 'm2m'),
]
RELATION_KINDS = ('fk', 'o2o', 'm2m')

#: Widget key -> dotted path of the class.
WIDGETS = {
    **{key: 'djgentelella.widgets.core.' + key for key in (
        'TextInput', 'Textarea', 'EmailInput', 'URLInput', 'NumberInput',
        'FloatInput', 'YesNoInput', 'CheckboxInput', 'DateInput', 'DateTimeInput',
        'TimeInput', 'Select', 'SelectMultiple', 'RadioHorizontalSelect',
        'RadioVerticalSelect', 'CheckboxSelectMultiple', 'FileInput',
        'ClearableFileInput', 'DateMaskInput', 'DateTimeMaskInput',
        'EmailMaskInput', 'PhoneNumberMaskInput', 'ColorInput', 'NullBooleanSelect',
    )},
    'EditorTinymce': 'djgentelella.widgets.tinymce.EditorTinymce',
    'TextareaWysiwyg': 'djgentelella.widgets.wysiwyg.TextareaWysiwyg',
    'TaggingInput': 'djgentelella.widgets.tagging.TaggingInput',
    'FilteredSelectMultiple':
        'djgentelella.widgets.selectmultiple.FilteredSelectMultiple',
    'MapPointInput': 'djgentelella.widgets.maps.MapPointInput',
    'AutocompleteSelect': 'djgentelella.widgets.selects.AutocompleteSelect',
    'AutocompleteSelectMultiple':
        'djgentelella.widgets.selects.AutocompleteSelectMultiple',
    'TreeSelect': 'djgentelella.widgets.trees.TreeSelect',
    'TreeSelectMultiple': 'djgentelella.widgets.trees.TreeSelectMultiple',
    'FileChunkedUpload': 'djgentelella.widgets.files.FileChunkedUpload',
    'PDFViewerWidget': 'djgentelella.widgets.pdf.PDFViewerWidget',
    # The form widgets of the catalog (2.1). Each one is built without
    # arguments here; ComboboxInput has no list then (free text with select2)
    # and GeocodedAddressInput no point field (it only searches).
    'StarRatingInput': 'djgentelella.widgets.extras.StarRatingInput',
    'SwitchInput': 'djgentelella.widgets.extras.SwitchInput',
    'RangeInput': 'djgentelella.widgets.extras.RangeInput',
    'ComboboxInput': 'djgentelella.widgets.extras.ComboboxInput',
    'QRCodeInput': 'djgentelella.widgets.extras.QRCodeInput',
    'MarkdownInput': 'djgentelella.widgets.markdown.MarkdownInput',
    'ImageCropInput': 'djgentelella.widgets.imagecrop.ImageCropInput',
    'GeocodedAddressInput': 'djgentelella.widgets.geocoding.GeocodedAddressInput',
}
#: Built with the basename of a select2 lookup (``gtselects.py``):
#: ``AutocompleteSelect('<basename>')``. Never a default, there is no lookup
#: to guess.
LOOKUP_WIDGETS = frozenset({'AutocompleteSelect', 'AutocompleteSelectMultiple'})
#: Only for relations to a ``tree_queries`` TreeNode, with the form field of
#: :data:`TREE_FORM_FIELDS`: the option template reads the label as a dict.
TREE_WIDGETS = frozenset({'TreeSelect', 'TreeSelectMultiple'})
TREE_FORM_FIELDS = {
    'TreeSelect': GentelellaTreeNodeChoiceField,
    'TreeSelectMultiple': GentelellaTreeNodeMultipleChoiceField,
}
#: Chunked uploads: an API takes the upload token (``ChunkedFileField``), not
#: the base64 content.
UPLOAD_WIDGETS = frozenset({'FileChunkedUpload', 'PDFViewerWidget'})

#: Widgets offered for each kind of field. The first usable one is the default;
#: new widgets go at the end of their lists, so no default changes.
WIDGETS_BY_KIND = {
    'string': ['TextInput', 'Textarea', 'TaggingInput', 'PhoneNumberMaskInput',
               'ColorInput', 'ComboboxInput', 'QRCodeInput', 'GeocodedAddressInput'],
    'slug': ['TextInput'],
    'email': ['EmailInput', 'EmailMaskInput', 'TextInput'],
    'url': ['URLInput', 'TextInput', 'QRCodeInput'],
    'text': ['Textarea', 'EditorTinymce', 'TextareaWysiwyg', 'TextInput',
             'MarkdownInput'],
    'integer': ['NumberInput', 'StarRatingInput', 'RangeInput'],
    'decimal': ['FloatInput', 'NumberInput', 'RangeInput'],
    'float': ['FloatInput', 'NumberInput', 'RangeInput'],
    'boolean': ['YesNoInput', 'CheckboxInput', 'SwitchInput'],
    # A checkbox cannot say "unknown": null=True needs the three choices.
    'nullboolean': ['NullBooleanSelect'],
    'date': ['DateInput', 'DateMaskInput'],
    'datetime': ['DateTimeInput', 'DateTimeMaskInput'],
    'time': ['TimeInput'],
    'choices': ['Select', 'RadioHorizontalSelect', 'RadioVerticalSelect'],
    'fk': ['AutocompleteSelect', 'Select', 'TreeSelect'],
    'o2o': ['AutocompleteSelect', 'Select', 'TreeSelect'],
    'm2m': ['AutocompleteSelectMultiple', 'SelectMultiple', 'CheckboxSelectMultiple',
            'FilteredSelectMultiple', 'TreeSelectMultiple'],
    # Clearable first, as in Django: an edit form shows the current file and
    # can empty an optional one.
    'file': ['ClearableFileInput', 'FileInput', 'FileChunkedUpload', 'PDFViewerWidget'],
    'image': ['ClearableFileInput', 'FileInput', 'FileChunkedUpload', 'ImageCropInput'],
    # The form field is a ChoiceField of the files found under ``path``.
    'filepath': ['Select'],
    'point': ['MapPointInput', 'TextInput'],
    'json': ['Textarea'],
}
FALLBACK_WIDGETS = ['TextInput']

_BOOLEAN = {'type': 'boolean'}
_NUMBER = {'type': 'number'}
#: A field name of the same form (the point a geocoded address fills).
FIELD_NAME = {'type': 'string', 'pattern': r'^[A-Za-z_][A-Za-z0-9_]*$'}
#: How many values a ``ComboboxInput`` lists at most, and how long each is.
MAX_COMBOBOX_CHOICES = 500
_CHOICE_TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 255}

#: Widget key -> ``{option: JSON schema}``: the keyword arguments of its
#: constructor a design (or djgentelella-editor) may set, the only ones
#: :func:`build_widget` passes. A widget that is not here takes none. The
#: ``title`` is what an inspector shows.
WIDGET_OPTIONS = {
    'StarRatingInput': {
        'stars': {'type': 'integer', 'minimum': 1, 'maximum': 10, 'default': 5,
                  'title': 'Stars'},
        'readonly': {**_BOOLEAN, 'default': False,
                     'title': 'Read only (shows the stars, cannot change them)'},
    },
    'SwitchInput': {
        'label': {'type': 'string', 'maxLength': 200, 'title': 'Text beside it'},
    },
    'RangeInput': {
        'min_value': {**_NUMBER, 'title': 'Minimum'},
        'max_value': {**_NUMBER, 'title': 'Maximum'},
        'step': {**_NUMBER, 'exclusiveMinimum': 0, 'title': 'Step'},
        'show_value': {**_BOOLEAN, 'default': True, 'title': 'Show the value'},
        'suffix': {'type': 'string', 'maxLength': 16,
                   'title': 'After the value (%, km...)'},
    },
    'ComboboxInput': {
        'choices': {
            'type': 'array', 'maxItems': MAX_COMBOBOX_CHOICES,
            'title': 'Values offered (a text, or a [value, label] pair)',
            'items': {'type': ['string', 'array'], 'minLength': 1, 'maxLength': 255,
                      'minItems': 2, 'maxItems': 2, 'items': _CHOICE_TEXT},
        },
    },
    'QRCodeInput': {
        'scan': {**_BOOLEAN, 'default': False,
                 'title': 'Read a QR code with the camera'},
        'readonly': {**_BOOLEAN, 'default': False, 'title': 'Read only'},
        'size': {'type': 'integer', 'minimum': 64, 'maximum': 1024, 'default': 160,
                 'title': 'Side of the code (pixels)'},
    },
    'MarkdownInput': {
        'rows': {'type': 'integer', 'minimum': 2, 'maximum': 60, 'default': 8,
                 'title': 'Rows'},
    },
    'ImageCropInput': {
        'aspect_ratio': {**_NUMBER, 'exclusiveMinimum': 0, 'maximum': 100,
                         'title': 'Proportion, width / height (empty = free)'},
        'max_width': {'type': 'integer', 'minimum': 1, 'maximum': 10000,
                      'title': 'Largest width (pixels)'},
        'max_height': {'type': 'integer', 'minimum': 1, 'maximum': 10000,
                       'title': 'Largest height (pixels)'},
        'output_type': {'enum': ['image/jpeg', 'image/png', 'image/webp'],
                        'default': 'image/jpeg', 'title': 'Format of the crop'},
        'quality': {**_NUMBER, 'minimum': 0.1, 'maximum': 1, 'default': 0.9,
                    'title': 'Quality (JPEG and WEBP)'},
    },
    'GeocodedAddressInput': {
        'point_field': {**FIELD_NAME,
                        'title': 'Point field of the form the place fills'},
        'replace_text': {**_BOOLEAN, 'default': False,
                         'title': 'Write the address found'},
    },
}


def field_type(field):
    """The type name of a model field in :data:`FIELD_KINDS`, or ``'other'``."""
    for field_class, name in FIELD_KINDS:
        if isinstance(field, field_class):
            return name
    return 'other'


def field_kind(field):
    """:func:`field_type`, refined to ``'point'`` and ``'choices'``."""
    if isinstance(field, GTPointField):
        return 'point'
    kind = field_type(field)
    if field.choices and kind not in RELATION_KINDS:
        return 'choices'
    if kind == 'boolean' and field.null:
        return 'nullboolean'
    return kind


def widget_choices(kind):
    """The widget keys offered for a field of ``kind``, default first."""
    return WIDGETS_BY_KIND.get(kind, FALLBACK_WIDGETS)


def usable_widgets(kind, can_autocomplete=True, is_tree=False):
    """The widgets that work for ``kind`` here: autocompletes only when there
    is a lookup to build them with, tree selects only for a TreeNode target."""
    return [key for key in widget_choices(kind)
            if (can_autocomplete or key not in LOOKUP_WIDGETS)
            and (is_tree or key not in TREE_WIDGETS)]


def is_tree_relation(field):
    return bool(field.is_relation and field.related_model
                and isinstance(field.related_model, type)
                and issubclass(field.related_model, TreeNode))


def default_widget(field):
    """The widget key :func:`gt_formfield_callback` gives a model field.

    Relations to a tree get the tree select; autocompletes are never chosen,
    since they need a lookup.
    """
    kind = field_kind(field)
    if kind in RELATION_KINDS and is_tree_relation(field):
        return 'TreeSelectMultiple' if kind == 'm2m' else 'TreeSelect'
    for key in usable_widgets(kind, can_autocomplete=False):
        return key
    return FALLBACK_WIDGETS[0]


def widget_class(key):
    return import_string(WIDGETS[key])


def widget_options(key):
    """The JSON schema of the options of the widget ``key``: an object of
    the options :data:`WIDGET_OPTIONS` declares and no other (an empty
    ``properties`` for a widget without options)."""
    return {'type': 'object', 'additionalProperties': False,
            'properties': dict(WIDGET_OPTIONS.get(key, {}))}


def _range_errors(options, path):
    low, high = options.get('min_value'), options.get('max_value')
    if low is not None and high is not None and low >= high:
        return [Error(path + '.max_value',
                      _('the maximum must be greater than the minimum'))]
    return []


def _combobox_errors(options, path):
    values = [str(choice[0] if isinstance(choice, list) else choice)
              for choice in options.get('choices') or []]
    if len(set(values)) != len(values):
        return [Error(path + '.choices', _('a value is listed twice'))]
    return []


def _number_errors(options, path):
    return [Error('%s.%s' % (path, name), _('not a finite number'))
            for name, value in options.items()
            if isinstance(value, float) and not math.isfinite(value)]


#: Checks of a widget's options that a schema cannot say:
#: ``key -> function(options, path) -> [Error]``.
WIDGET_OPTION_CHECKS = {
    'RangeInput': _range_errors,
    'ComboboxInput': _combobox_errors,
}


def validate_widget_options(key, options, path='$'):
    """The problems of ``options`` for the widget ``key`` (a list of
    :class:`~djgentelella.designs.jsonschema.Error`, empty when valid): its
    schema (:func:`widget_options`) and :data:`WIDGET_OPTION_CHECKS`. An
    option a widget does not declare is an error, and so is any option for a
    widget that takes none."""
    if key not in WIDGETS:
        return [Error(path, _('%r is not a widget') % (key,))]
    if options and key not in WIDGET_OPTIONS:
        return [Error(path, _('%s takes no options') % key)]
    errors = validate(options, widget_options(key), path)
    if errors:
        return errors
    errors = _number_errors(options, path)
    check = WIDGET_OPTION_CHECKS.get(key)
    if check is not None and not errors:
        errors = check(options, path)
    return errors


def build_widget(key, options=None, *, lookup=None):
    """An instance of the widget ``key`` with ``options`` (validated:
    ``ValueError`` with the problems when they are not), and with the
    ``lookup`` basename of an autocomplete."""
    options = dict(options or {})
    errors = validate_widget_options(key, options)
    if errors:
        raise ValueError('; '.join(str(error) for error in errors))
    if key == 'ComboboxInput' and 'choices' in options:
        options['choices'] = [tuple(choice) if isinstance(choice, list) else choice
                              for choice in options['choices']]
    if key in LOOKUP_WIDGETS:
        return widget_class(key)(lookup, **options)
    return widget_class(key)(**options)


def gt_formfield_callback(field, **kwargs):
    """``formfield_callback`` that gives each field its djgentelella widget.

    A widget passed in (``Meta.widgets``) is kept, and so is a form field
    class (``Meta.field_classes``).
    """
    if 'widget' not in kwargs:
        key = default_widget(field)
        kwargs['widget'] = widget_class(key)
        if key in TREE_FORM_FIELDS and 'form_class' not in kwargs:
            kwargs['form_class'] = TREE_FORM_FIELDS[key]
    # str(permission) reads its content type: one query per option otherwise.
    if (field.is_relation and 'queryset' not in kwargs
            and field.related_model is not None
            and field.related_model._meta.label == 'auth.Permission'):
        kwargs['queryset'] = permission_queryset()
    return field.formfield(**kwargs)
