"""
Preview system for email templates.

Generates dummy context data for template preview and provides
real data preview via PreviewProvider.
"""

import datetime
import decimal
import uuid

from django.apps import apps
from django.template import Template, Context
from django.utils.safestring import mark_safe

from djgentelella.async_notification.registry import get_context_config


class DummyContextObject:
    """Generates type-aware dummy values for model fields.

    Used to build a fake context for template preview rendering.
    """

    DUMMY_VALUES = {
        'string': 'Sample Text',
        'text': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
        'integer': 42,
        'float': 3.14,
        'decimal': decimal.Decimal('99.99'),
        'boolean': True,
        'date': datetime.date(2025, 1, 15),
        'datetime': datetime.datetime(2025, 1, 15, 10, 30, 0),
        'time': datetime.time(10, 30, 0),
        'email': 'user@example.com',
        'url': 'https://example.com',
        'uuid': uuid.UUID('12345678-1234-5678-1234-567812345678'),
        'ip': '192.168.1.1',
        'duration': datetime.timedelta(hours=2, minutes=30),
        'file': '/media/sample/file.pdf',
        'image': '/media/sample/image.png',
        'json': {'key': 'value'},
        'binary': b'binary data',
        'filepath': '/path/to/file',
        'relation': None,
        'custom': 'Custom Value',
        'unknown': 'Unknown',
    }

    @classmethod
    def get_dummy_value(cls, field_type):
        """Return a dummy value for a given field type string.

        Args:
            field_type: Field type string (e.g., 'string', 'integer').

        Returns:
            An appropriate dummy value for the type.
        """
        return cls.DUMMY_VALUES.get(field_type, 'N/A')


class PreviewProvider:
    """Base class for preview data providers.

    Override get_queryset() and get_display() to customize
    how real data is fetched for previews.
    """

    def get_queryset(self):
        """Return a queryset for preview objects."""
        raise NotImplementedError

    def get_display(self, obj):
        """Return a string representation for display in the preview selector."""
        return str(obj)

    def build_context(self, obj):
        """Build a template context dict from an object.

        Default implementation returns the object's __dict__ without
        internal attributes.

        Args:
            obj: The model instance.

        Returns:
            Dict of template context variables.
        """
        return {k: v for k, v in obj.__dict__.items()
                if not k.startswith('_')}


class AutoPreviewProvider(PreviewProvider):
    """Default preview provider using model introspection.

    Fetches the 10 most recent objects from the model.
    """

    def __init__(self, model_string):
        self.model_string = model_string
        try:
            self.model = apps.get_model(model_string)
        except (LookupError, ValueError):
            self.model = None

    def get_queryset(self):
        if self.model is None:
            return []
        return self.model.objects.order_by('-pk')[:10]


def build_dummy_context(code):
    """Build a dummy context dict for one or more registered template contexts.

    Accepts a single code or a comma-separated string of codes. Results are
    merged so all variables from all contexts are available.

    Args:
        code: A registered context code, or comma-separated codes.

    Returns:
        Dict suitable for use as a Django template Context.
        Returns empty dict if no code is registered.
    """
    from djgentelella.async_notification.introspection import get_fields_for_context

    fields_data = get_fields_for_context(code)
    if fields_data is None:
        return {}

    context = {}
    for prefix, fields in fields_data.items():
        if prefix == 'extra_variables':
            for field in fields:
                context[field['name']] = DummyContextObject.get_dummy_value(
                    field['type'])
        else:
            # Build nested dict structure for dotted field names
            for field in fields:
                parts = field['name'].split('.')
                current = context
                for part in parts[:-1]:
                    if not isinstance(current.get(part), dict):
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = DummyContextObject.get_dummy_value(
                    field['type'])

    return context


def build_dummy_context_from_fields(fields_data):
    """Build a dummy context from an already-resolved fields_data dict.

    Args:
        fields_data: Dict as returned by get_fields_for_content_types().

    Returns:
        Dict suitable for use as a Django template Context.
    """
    context = {}
    for prefix, fields in fields_data.items():
        if prefix == 'extra_variables':
            for field in fields:
                context[field['name']] = DummyContextObject.get_dummy_value(field['type'])
        else:
            for field in fields:
                parts = field['name'].split('.')
                current = context
                for part in parts[:-1]:
                    if not isinstance(current.get(part), dict):
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = DummyContextObject.get_dummy_value(field['type'])
    return context


def render_preview(content, context, base_template=None):
    """Render an email template with a context for preview.

    Args:
        content: The template content string (HTML with Django template syntax).
        context: Dict of template context variables.
        base_template: Optional EmailTemplate instance (or PK) whose message
            wraps the rendered content via {{ body }}.

    Returns:
        Rendered HTML string, or error message on template syntax errors.
    """
    try:
        inner_tpl = Template(content)
        inner_html = inner_tpl.render(Context(context))

        if base_template is not None:
            from djgentelella.async_notification.models import EmailTemplate
            if not isinstance(base_template, EmailTemplate):
                try:
                    base_template = EmailTemplate.objects.get(pk=base_template)
                except (EmailTemplate.DoesNotExist, ValueError):
                    base_template = None

        if base_template is not None:
            outer_tpl = Template(base_template.message)
            return outer_tpl.render(Context({**context, 'body': mark_safe(inner_html)}))

        return inner_html
    except Exception as e:
        return f'<div style="color:red;padding:10px;">Template Error: {e}</div>'
