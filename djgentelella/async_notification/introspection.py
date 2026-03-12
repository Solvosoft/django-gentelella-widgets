"""
Model field introspection utilities.

Provides functions to describe model fields recursively, supporting
depth-limited traversal of foreign key relationships. Used to build
the variable tree shown in the email template editor.
"""

from django.apps import apps
from django.db.models import fields as model_fields
from django.db.models.fields.files import FileField, ImageField
from django.db.models.fields.related import ForeignKey, OneToOneField

from django.contrib.contenttypes.models import ContentType

from djgentelella.async_notification.registry import get_context_config


def _build_field_type_map():
    """Build field type map dynamically to handle Django version differences."""
    mapping = {
        model_fields.AutoField: 'integer',
        model_fields.BigIntegerField: 'integer',
        model_fields.IntegerField: 'integer',
        model_fields.SmallIntegerField: 'integer',
        model_fields.PositiveIntegerField: 'integer',
        model_fields.PositiveSmallIntegerField: 'integer',
        model_fields.FloatField: 'float',
        model_fields.DecimalField: 'decimal',
        model_fields.CharField: 'string',
        model_fields.TextField: 'text',
        model_fields.SlugField: 'string',
        model_fields.EmailField: 'email',
        model_fields.URLField: 'url',
        model_fields.UUIDField: 'uuid',
        model_fields.BooleanField: 'boolean',
        model_fields.DateField: 'date',
        model_fields.DateTimeField: 'datetime',
        model_fields.TimeField: 'time',
        FileField: 'file',
        ImageField: 'image',
        model_fields.BinaryField: 'binary',
        model_fields.GenericIPAddressField: 'ip',
        model_fields.DurationField: 'duration',
        model_fields.FilePathField: 'filepath',
    }
    # Fields that may not exist in all Django versions
    for attr, type_name in [
        ('BigAutoField', 'integer'),
        ('SmallAutoField', 'integer'),
        ('PositiveBigIntegerField', 'integer'),
        ('NullBooleanField', 'boolean'),
        ('JSONField', 'json'),
        ('IPAddressField', 'ip'),
    ]:
        cls = getattr(model_fields, attr, None)
        if cls is not None:
            mapping[cls] = type_name
    return mapping


FIELD_TYPE_MAP = _build_field_type_map()


def _get_field_type(field):
    """Map a Django model field to a simple type string."""
    for field_class, type_name in FIELD_TYPE_MAP.items():
        if isinstance(field, field_class):
            return type_name
    return 'unknown'


def describe_model_fields(model, depth=2, exclude=None, prefix='',
                          current_depth=0):
    """Describe fields of a Django model recursively.

    Args:
        model: Django model class.
        depth: Maximum depth for following FK/O2O relations.
        exclude: List of field names to exclude.
        prefix: Dot-separated prefix for nested fields.
        current_depth: Current recursion depth (internal).

    Returns:
        List of dicts with keys: name, type, verbose_name, is_relation, expandable.
    """
    exclude = exclude or []
    result = []

    for field in model._meta.get_fields():
        # Skip reverse relations and excluded fields
        if not hasattr(field, 'column') and not hasattr(field, 'attname'):
            if not isinstance(field, (ForeignKey, OneToOneField)):
                continue

        field_name = field.name
        if field_name in exclude:
            continue

        full_name = f'{prefix}{field_name}' if not prefix else f'{prefix}.{field_name}'
        is_relation = isinstance(field, (ForeignKey, OneToOneField))
        expandable = is_relation and current_depth < depth

        field_info = {
            'name': full_name,
            'type': 'relation' if is_relation else _get_field_type(field),
            'verbose_name': str(getattr(field, 'verbose_name', field_name)),
            'is_relation': is_relation,
            'expandable': expandable,
        }
        result.append(field_info)

        if expandable:
            related_model = field.related_model
            children = describe_model_fields(
                related_model,
                depth=depth,
                exclude=exclude,
                prefix=full_name,
                current_depth=current_depth + 1,
            )
            result.extend(children)

    return result


def get_fields_for_content_types(content_type_pks):
    """Get all available template fields from a list of ContentType PKs.

    Args:
        content_type_pks: Iterable of ContentType primary keys.

    Returns:
        Dict mapping model names to their field lists.
        Returns None if no valid content types are found.
    """
    pks = list(content_type_pks) if content_type_pks else []
    if not pks:
        return None

    result = {}
    found_any = False

    for ct in ContentType.objects.filter(pk__in=pks):
        model = ct.model_class()
        if model is None:
            continue
        found_any = True
        prefix = ct.model
        fields = describe_model_fields(model, depth=2, prefix=prefix)
        if prefix in result:
            existing_names = {f['name'] for f in result[prefix]}
            result[prefix].extend(f for f in fields if f['name'] not in existing_names)
        else:
            result[prefix] = fields

    if not found_any:
        return None

    result['extra_variables'] = []
    return result


def get_fields_for_context(code):
    """Get fields for a registry context code or app_label.model_name string.

    Kept for backward compatibility with registry-based contexts.

    Args:
        code: A registered context code or comma-separated app_label.model_name strings.

    Returns:
        Dict mapping prefixes to field lists, or None if nothing resolved.
    """
    codes = [c.strip() for c in code.split(',') if c.strip()] if code else []
    if not codes:
        return None

    result = {}
    extra_variables = []
    found_any = False

    for single_code in codes:
        config = get_context_config(single_code)

        if config is not None:
            models_map = config['models']
            exclude_map = config['exclude']
            depth = config['depth']
            extra_variables.extend(
                {'name': name, 'type': 'custom', 'verbose_name': desc,
                 'is_relation': False, 'expandable': False}
                for name, desc in config['extra_variables'].items()
            )
        else:
            try:
                apps.get_model(single_code)
            except (LookupError, ValueError):
                continue
            models_map = {single_code.split('.')[-1]: single_code}
            exclude_map = {}
            depth = 2

        found_any = True
        for prefix, model_string in models_map.items():
            try:
                model = apps.get_model(model_string)
            except (LookupError, ValueError):
                continue
            fields = describe_model_fields(
                model, depth=depth,
                exclude=exclude_map.get(prefix, []), prefix=prefix)
            if prefix in result:
                existing_names = {f['name'] for f in result[prefix]}
                result[prefix].extend(f for f in fields if f['name'] not in existing_names)
            else:
                result[prefix] = fields

    if not found_any:
        return None

    result['extra_variables'] = extra_variables
    return result
