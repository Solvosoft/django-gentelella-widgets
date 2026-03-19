Recipient Resolvers
===========================

The resolver system allows extending recipient addresses beyond plain email addresses.
When a recipient contains ``@`` and the domain matches a registered resolver, the resolver
translates the identifier into actual email addresses.

Built-in Resolver
--------------------

The module ships with ``DjangoGroupResolver``, which resolves Django auth groups:

- Address format: ``<group_name>@group.local``
- Resolves to: email addresses of all users in the group (excluding users with empty email).

This resolver is registered automatically when the app starts (in ``apps.py``).

.. code:: python

    # These recipients will be resolved at send time:
    notification = EmailNotification.objects.create(
        subject='Team Update',
        message='<p>New sprint started.</p>',
        recipients='dev-team@group.local, managers@group.local, extra@example.com',
        enqueued=True,
    )
    # 'dev-team@group.local' → emails of users in the "dev-team" group
    # 'managers@group.local' → emails of users in the "managers" group
    # 'extra@example.com' → used as-is

Creating Custom Resolvers
----------------------------

To create a custom resolver, subclass ``RecipientResolver`` and implement ``resolve()`` and ``search()``:

.. code:: python

    from djgentelella.async_notification.resolvers import RecipientResolver

    class DepartmentResolver(RecipientResolver):
        """Resolves recipients from a Department model."""

        def resolve(self, identifier):
            """Resolve a department name to member emails."""
            from myapp.models import Department
            try:
                dept = Department.objects.get(name=identifier)
            except Department.DoesNotExist:
                return []
            return list(
                dept.members.exclude(email='')
                .values_list('email', flat=True)
            )

        def search(self, query):
            """Search departments by name for autocomplete."""
            from myapp.models import Department
            departments = Department.objects.filter(
                name__icontains=query)[:20]
            return [
                {
                    'value': f'{d.name}@department.local',
                    'label': f'Department: {d.name}',
                }
                for d in departments
            ]

Registering Resolvers
^^^^^^^^^^^^^^^^^^^^^^^^

Register your resolver in your app's ``AppConfig.ready()`` method:

.. code:: python

    from django.apps import AppConfig

    class MyAppConfig(AppConfig):
        name = 'myapp'

        def ready(self):
            from djgentelella.async_notification.resolvers import (
                RecipientResolverRegistry
            )
            from myapp.resolvers import DepartmentResolver
            RecipientResolverRegistry.register(
                'department.local', DepartmentResolver
            )

Now recipients like ``engineering@department.local`` will be resolved through your custom resolver.

Resolver Registry API
^^^^^^^^^^^^^^^^^^^^^^^^

The ``RecipientResolverRegistry`` provides these class methods:

- ``register(suffix, resolver_class)`` - Register a resolver for a domain suffix.
- ``resolve(address)`` - Resolve an address. If the domain matches a registered suffix, delegates to
  the resolver. Otherwise returns the address as-is.
- ``search_all(query)`` - Search all registered resolvers for autocomplete suggestions.
- ``reset()`` - Clear all registered resolvers (useful for testing).

Autocomplete Integration
---------------------------

The ``email_autocomplete_view`` endpoint (``/autocomplete/?q=<query>``) searches:

1. All registered resolvers via ``RecipientResolverRegistry.search_all()``.
2. The User model using fields configured in ``ASYNC_NOTIFICATION_USER_LOOKUP_FIELDS``.

Results are rendered as HTML fragments using the ``_autocomplete_results.html`` template and displayed
as a dropdown in the management UI for recipient, CC, and BCC fields.
