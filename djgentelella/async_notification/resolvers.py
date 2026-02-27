from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
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


class RecipientResolverRegistry:
    """Registry for recipient resolvers keyed by domain suffix."""

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
            _, domain = address.rsplit('@', 1)
            if domain in cls._resolvers:
                identifier = address.rsplit('@', 1)[0]
                return cls._resolvers[domain].resolve(identifier)
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
