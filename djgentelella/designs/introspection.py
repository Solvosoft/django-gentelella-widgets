"""What a design can know about a model, as plain JSON-friendly data.

Moved from djgentelella-editor (``gteditor.introspection.describe_model`` and
the description half of ``gteditor.mapping``), which imports it from here.
Only the schema (``Model._meta``) is read, never a row. The same descriptions
feed the editor's diagram and palette, its code generator and the runtime
components, so they all agree on what a field is.

The *kind* of a field is its type in
:data:`djgentelella.forms.widgetmap.FIELD_KINDS`, except that a field with
``choices`` is ``'choices'`` and a ``GTPointField`` is ``'point'``.
"""

from tree_queries.models import TreeNode

from djgentelella.forms import widgetmap
from djgentelella.models import DeletedWithTrash

RELATION_KINDS = widgetmap.RELATION_KINDS
TEXT_KINDS = ('string', 'slug', 'email', 'url', 'text')
NUMBER_KINDS = ('integer', 'decimal', 'float')
SINGLE_RELATIONS = ('fk', 'o2o')


def model_label(model):
    return model._meta.label


def _plain(value):
    """``value`` if it is JSON-friendly, else its ``str`` (lazy strings included)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def describe_field(field):
    kind = widgetmap.field_type(field)
    description = {
        'name': field.name,
        'verbose_name': str(field.verbose_name),
        'type': kind,
        'class': type(field).__name__,
        'null': field.null,
        'blank': field.blank,
        'editable': field.editable,
        'primary_key': field.primary_key,
        'unique': field.unique,
        'help_text': str(field.help_text),
    }
    if getattr(field, 'max_length', None):
        description['max_length'] = field.max_length
    if field.choices:
        description['choices'] = [
            [_plain(value), str(label)] for value, label in field.flatchoices]
    if field.has_default() and not callable(field.default):
        description['default'] = _plain(field.default)
    if kind in RELATION_KINDS:
        description['relation'] = {
            'kind': kind,
            'to': model_label(field.related_model),
            'related_name': field.remote_field.related_name,
        }
    return description


def describe_reverse(relation):
    """A relation pointing *at* the model, from the other side."""
    return {
        'accessor': relation.get_accessor_name(),
        'from': model_label(relation.related_model),
        'field': relation.field.name,
        'kind': widgetmap.field_type(relation.field),
    }


def describe_model(model, fields=None):
    """The model as a dict. ``fields`` -- model fields -- limits the forward
    fields described, e.g. to an :class:`~djgentelella.designs.exposure.Exposure`'s."""
    opts = model._meta
    if fields is None:
        # Forward fields only: the reverse side of a relation is reported apart.
        fields = list(opts.fields) + list(opts.many_to_many)
    reverse = [field for field in opts.get_fields()
               if field.auto_created and not field.concrete
               and field.related_model is not None]
    default_perms = ['%s_%s' % (action, opts.model_name)
                     for action in opts.default_permissions]
    return {
        'label': model_label(model),
        'app_label': opts.app_label,
        'name': opts.object_name,
        'model_name': opts.model_name,
        'verbose_name': str(opts.verbose_name),
        'verbose_name_plural': str(opts.verbose_name_plural),
        'db_table': opts.db_table,
        'proxy': opts.proxy,
        'managed': opts.managed,
        'ordering': [str(item) for item in opts.ordering],
        'permissions': default_perms + [codename for codename, _ in opts.permissions],
        'is_tree': issubclass(model, TreeNode),
        'soft_delete': issubclass(model, DeletedWithTrash),
        'fields': [describe_field(field) for field in fields],
        'reverse_relations': [describe_reverse(relation) for relation in reverse],
    }


# -- rules on descriptions ---------------------------------------------------------

def field_kind(description):
    """The kind of a :func:`describe_field` dict."""
    if description.get('class') == 'GTPointField':
        return 'point'
    if description.get('choices') and description['type'] not in RELATION_KINDS:
        return 'choices'
    return description['type']


def is_form_field(description):
    """Whether a ModelForm would show the field by default."""
    return description['editable'] and description['type'] != 'auto'


def widget_choices(description):
    return widgetmap.widget_choices(field_kind(description))


def search_field(model_description):
    """Field a select2 lookup searches on: the first text-like one, if any."""
    for field in model_description['fields']:
        if field['type'] in TEXT_KINDS and not field['primary_key']:
            return field['name']
    return None


def column_type(description, has_lookup):
    """The ``ObjectManagement`` DataTable column type of a field."""
    kind = field_kind(description)
    if kind in TEXT_KINDS:
        return 'string'
    if kind in NUMBER_KINDS:
        return 'number'
    if kind in ('boolean', 'date', 'choices'):
        return {'choices': 'select'}.get(kind, kind)
    if kind == 'datetime':
        return 'date'
    if kind in SINGLE_RELATIONS + ('m2m',):
        return 'select2' if has_lookup else 'readonly'
    return 'readonly'


def filter_lookup(description):
    """Lookup of a filter ``Meta.fields`` can declare, or ``None``.

    Dates, datetimes and many-to-many need a declared filter; files and the
    rest are not filterable.
    """
    kind = field_kind(description)
    if kind in TEXT_KINDS:
        return 'icontains'
    if kind in NUMBER_KINDS + SINGLE_RELATIONS + ('boolean', 'choices'):
        return 'exact'
    return None
