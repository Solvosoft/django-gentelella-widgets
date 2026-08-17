Email Templates & Preview
===========================

The email template system allows creating reusable email templates with Django template syntax,
live preview, and model field introspection.

Creating Templates
--------------------

Templates use Django's template language for dynamic content:

.. code:: python

    from djgentelella.async_notification.models import EmailTemplate

    EmailTemplate.objects.create(
        code='welcome',
        subject='Welcome, {{ user.first_name }}!',
        message=(
            '<h2>Welcome to our platform!</h2>'
            '<p>Hello {{ user.first_name }},</p>'
            '<p>Your account <strong>{{ user.username }}</strong> '
            'is now active.</p>'
        ),
        context_code='user_welcome',
        base_template='default',
    )

The ``context_code`` links the template to a registered context (see :doc:`registry`), which enables
the Model Inspector in the UI to show available template variables.

The ``base_template`` references a key from ``ASYNC_NOTIFICATION_BASE_TEMPLATES`` in settings (see :doc:`settings`).

Template Preview
-------------------

The preview system renders templates with dummy or real data. It is used both in the management UI
and can be called programmatically.

.. code:: python

    from djgentelella.async_notification.preview import (
        build_dummy_context, render_preview
    )

    # Build dummy context from a registered context code
    context = build_dummy_context('user_welcome')

    # Render the template with the dummy context
    html = render_preview(
        content='<p>Hello {{ user.first_name }}!</p>',
        context=context,
        base_template_key='default',  # Optional: wrap in base template
    )

``build_dummy_context()`` introspects the registered models and generates type-appropriate dummy values:

- ``string`` fields → ``"Sample Text"``
- ``integer`` fields → ``42``
- ``date`` fields → ``2025-01-15``
- ``email`` fields → ``"user@example.com"``
- And so on for all Django field types.

Custom Preview Providers
^^^^^^^^^^^^^^^^^^^^^^^^^^^

For previews with real data, you can register a custom ``PreviewProvider`` on a context:

.. code:: python

    from djgentelella.async_notification.preview import PreviewProvider

    class OrderPreviewProvider(PreviewProvider):
        def get_queryset(self):
            from myapp.models import Order
            return Order.objects.order_by('-created_at')[:10]

        def get_display(self, obj):
            return f'Order #{obj.id} - {obj.customer_name}'

        def build_context(self, obj):
            return {
                'order': obj,
                'user': obj.customer,
            }

Then register it:

.. code:: python

    from djgentelella.async_notification.registry import register_context

    register_context(
        code='order_confirmation',
        subject='Order #{{ order.id }} Confirmed',
        models={'order': 'myapp.Order', 'user': 'auth.User'},
        preview_provider='myapp.previews.OrderPreviewProvider',
    )

Model Inspector
------------------

The Model Inspector is a UI component in the template editor that shows available template variables
for the selected context code. It uses the introspection module to recursively describe model fields.

The introspection endpoint (``/model-fields/?code=<context_code>``) supports two response formats:

- **JSON** (default) - Returns a dict mapping prefixes to field lists.
- **HTML** (when ``Accept: text/html`` header is sent) - Returns a rendered HTML fragment using the ``_model_tree.html`` template.

The management UI uses the HTML format for direct DOM insertion.

.. code:: python

    from djgentelella.async_notification.introspection import get_fields_for_context

    fields = get_fields_for_context('order_confirmation')
    # Returns:
    # {
    #     'order': [
    #         {'name': 'order.id', 'type': 'integer', 'verbose_name': 'ID', ...},
    #         {'name': 'order.total', 'type': 'decimal', 'verbose_name': 'Total', ...},
    #         ...
    #     ],
    #     'user': [
    #         {'name': 'user.username', 'type': 'string', 'verbose_name': 'Username', ...},
    #         ...
    #     ],
    #     'extra_variables': [
    #         {'name': 'site_url', 'type': 'custom', 'verbose_name': 'Site URL', ...},
    #     ],
    # }

Each field entry includes:

- ``name`` - Dotted path for use in templates (e.g., ``{{ order.total }}``).
- ``type`` - Field type string (``string``, ``integer``, ``date``, ``relation``, etc.).
- ``verbose_name`` - Human-readable field description.
- ``is_relation`` - Whether the field is a FK/O2O relation.
- ``expandable`` - Whether the relation can be expanded (depth limit not reached).

Base Templates
-----------------

Base templates wrap email content in a consistent layout. Configure them in settings:

.. code:: python

    ASYNC_NOTIFICATION_BASE_TEMPLATES = {
        'default': 'emails/base_default.html',
        'minimal': 'emails/base_minimal.html',
    }

The base template receives:

- ``{{ content|safe }}`` - The rendered email body.
- All context variables from the template's context code.

See :doc:`settings` for a full example of a base template.
