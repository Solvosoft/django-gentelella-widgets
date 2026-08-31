from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from djgentelella.async_notification.settings import (
    ASYNC_NOTIFICATION_GROUP_LOOKUP_FIELDS,
)


class RecipientResolver:
    """Base class for recipient resolution.

    Subclasses must implement resolve() and search().
    """

    def resolve(self, identifier):
        """Resolve an identifier to a list of email addresses.

        Args:
            identifier: The identifier string (e.g., group name).

        Returns:
            List of email address strings.
        """
        raise NotImplementedError

    def search(self, query):
        """Search for matching recipients.

        Args:
            query: Search query string.

        Returns:
            List of dicts with 'value' and 'label' keys.
        """
        raise NotImplementedError


class DjangoGroupResolver(RecipientResolver):
    """Resolves recipients from Django auth.Group members."""

    def resolve(self, identifier):
        """Resolve a group name to member email addresses."""
        User = get_user_model()
        try:
            group = Group.objects.get(name=identifier)
        except Group.DoesNotExist:
            return []
        return list(
            User.objects.filter(groups=group)
            .exclude(email='')
            .values_list('email', flat=True)
        )

    def search(self, query):
        """Search groups by name."""
        q = Q()
        for field in ASYNC_NOTIFICATION_GROUP_LOOKUP_FIELDS:
            q |= Q(**{f'{field}__icontains': query})
        groups = Group.objects.filter(q)[:20]
        return [
            {'value': f'{g.name}@group.local', 'label': f'Group: {g.name}'}
            for g in groups
        ]


class ContentTypeResolver(RecipientResolver):
    """Resolve ``<pk>@<app_label>.<model_name>.internal`` to an instance email.

    The instance is located via ``ContentType`` and its address is taken
    from a ``gt_get_mail_address()`` method (preferred) or an ``email``
    attribute. Registered under the terminal label ``internal``.
    """

    def resolve_domain(self, identifier, domain):
        """Resolve using the full domain (``app_label.model_name.internal``).

        Args:
            identifier: The instance primary key (before the ``@``).
            domain: The full domain part after the ``@``.

        Returns:
            List with the resolved email, or empty list on any failure.
        """
        base = domain[:-len('.internal')]
        parts = base.split('.')
        if len(parts) != 2:
            return []
        app_label, model_name = parts
        try:
            ct = ContentType.objects.get(
                app_label=app_label, model=model_name)
            model = ct.model_class()
            if model is None:
                return []
            instance = model.objects.get(pk=identifier)
        except (ContentType.DoesNotExist, ValueError, TypeError):
            return []
        except Exception:
            # Includes model.DoesNotExist for the resolved model.
            return []

        getter = getattr(instance, 'gt_get_mail_address', None)
        if callable(getter):
            email = getter()
        else:
            email = getattr(instance, 'email', None)

        if not email:
            return []
        if isinstance(email, str):
            return [email]
        return [e for e in email if e]

    def resolve(self, identifier):  # pragma: no cover - not used directly
        return []

    def search(self, query):
        return []


class RecipientResolverRegistry:
    """Registry for recipient resolvers keyed by domain suffix.

    Resolvers are matched by exact domain (e.g. ``group.local``) or, for
    resolvers that implement ``resolve_domain``, by the terminal domain
    label (e.g. ``internal`` matching ``app.model.internal``).
    """

    _resolvers = {}

    @classmethod
    def register(cls, suffix, resolver_class):
        """Register a resolver class for a given suffix.

        Args:
            suffix: Domain suffix (e.g., 'group.local').
            resolver_class: A RecipientResolver subclass.
        """
        cls._resolvers[suffix] = resolver_class()

    @classmethod
    def has_resolver(cls, suffix):
        """Return True if a resolver is registered for the given suffix."""
        return suffix in cls._resolvers

    @classmethod
    def resolve(cls, address):
        """Resolve an address using the appropriate resolver.

        If the address contains '@' and the domain matches a registered
        suffix, delegate to that resolver. Otherwise return the address
        as-is in a list.

        Args:
            address: Email address or resolver-aware address.

        Returns:
            List of resolved email address strings.
        """
        if '@' in address:
            identifier, domain = address.rsplit('@', 1)
            # Exact-domain resolver (e.g. group.local).
            if domain in cls._resolvers:
                return cls._resolvers[domain].resolve(identifier)
            # Terminal-label resolver (e.g. <app>.<model>.internal).
            last_label = domain.rsplit('.', 1)[-1]
            resolver = cls._resolvers.get(last_label)
            if resolver is not None and hasattr(resolver, 'resolve_domain'):
                return resolver.resolve_domain(identifier, domain)
        return [address]

    @classmethod
    def search_all(cls, query):
        """Search all registered resolvers.

        Args:
            query: Search query string.

        Returns:
            List of result dicts from all resolvers.
        """
        results = []
        for resolver in cls._resolvers.values():
            results.extend(resolver.search(query))
        return results

    @classmethod
    def reset(cls):
        """Clear all registered resolvers. Useful for testing."""
        cls._resolvers.clear()
