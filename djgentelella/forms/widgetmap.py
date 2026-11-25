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

The *kind* of a field is its type name (:data:`FIELD_KINDS`), except that a
field with ``choices`` is ``'choices'``, a nullable ``BooleanField`` is
``'nullboolean'`` and a ``GTPointField`` is ``'point'``.
"""

from django.db import models
from django.db.models.fields.files import FileField, ImageField
from django.utils.module_loading import import_string
from tree_queries.models import TreeNode

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
