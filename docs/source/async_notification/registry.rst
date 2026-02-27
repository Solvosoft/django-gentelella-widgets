Context Registry
===========================

The context registry maps template codes to the models and variables available when rendering
that template. This powers both the Model Inspector in the UI and the dummy context generation
for template previews.

Registering a Context
------------------------

Register contexts in your app's ``AppConfig.ready()`` or a module imported at startup:

.. code:: python

    from djgentelella.async_notification.registry import register_context

    register_context(
        code='order_confirmation',
        subject='Order #{{ order.id }} Confirmed',
        models={
            'order': 'myapp.Order',
            'user': 'auth.User',
        },
        exclude={
            'user': ['password', 'last_login', 'is_superuser'],
        },
        extra_variables={
            'site_url': 'Full URL of the site',
            'support_email': 'Support team email address',
        },
        depth=2,
        preview_provider='myapp.previews.OrderPreviewProvider',
    )

**Parameters:**

- ``code`` (str) - Unique identifier for this context. Used in the ``EmailTemplate.context_code`` field.
- ``subject`` (str) - Default subject template string.
- ``models`` (dict) - Maps variable prefixes to model strings in ``app_label.ModelName`` format.
- ``exclude`` (dict, optional) - Maps prefixes to lists of field names to exclude from introspection.
- ``extra_variables`` (dict, optional) - Maps variable names to human-readable descriptions. These are
  shown in the Model Inspector but are not tied to model fields.
- ``depth`` (int, default 2) - Maximum depth for following FK/O2O relations during introspection.
- ``preview_provider`` (str or class, optional) - Dotted path or class for generating real preview data.

Retrieving Contexts
----------------------

.. code:: python

    from djgentelella.async_notification.registry import (
        get_context_config, get_all_contexts
    )

    # Get a single context
    config = get_context_config('order_confirmation')
    # Returns dict with: code, subject, models, exclude,
    #                     extra_variables, depth, preview_provider

    # Get all registered contexts
    all_contexts = get_all_contexts()
    # Returns dict mapping codes to their configurations

How the Registry is Used
---------------------------

**In the management UI:**

When a user selects a ``context_code`` in the email template editor, the UI fetches the model fields
from the ``/model-fields/`` endpoint, which calls ``get_fields_for_context()`` internally. This shows
the user which template variables are available (e.g., ``{{ order.id }}``, ``{{ user.email }}``).

**For template preview:**

When previewing a template, ``build_dummy_context()`` uses the registry to generate type-appropriate
dummy values for all model fields and extra variables.

**In serializers:**

When saving an ``EmailTemplate``, the ``context_code`` is persisted so that later previews
(including from the table listing) know which context to use.

Example: Full Registration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

    # myapp/apps.py
    from django.apps import AppConfig

    class MyAppConfig(AppConfig):
        name = 'myapp'

        def ready(self):
            from djgentelella.async_notification.registry import register_context

            register_context(
                code='user_welcome',
                subject='Welcome, {{ user.first_name }}!',
                models={'user': 'auth.User'},
                exclude={'user': ['password', 'last_login', 'groups',
                                  'user_permissions']},
                extra_variables={
                    'login_url': 'URL to the login page',
                    'site_name': 'Name of the site',
                },
            )

            register_context(
                code='password_reset',
                subject='Password Reset for {{ user.username }}',
                models={'user': 'auth.User'},
                exclude={'user': ['password']},
                extra_variables={
                    'reset_url': 'Password reset link',
                    'expiry_hours': 'Hours until the link expires',
                },
            )

Clearing the Registry
^^^^^^^^^^^^^^^^^^^^^^^^

For testing purposes, the registry can be cleared:

.. code:: python

    from djgentelella.async_notification.registry import clear_registry

    clear_registry()
