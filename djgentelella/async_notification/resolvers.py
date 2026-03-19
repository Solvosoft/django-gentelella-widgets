import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q

from djgentelella.async_notification.settings import (
    ASYNC_NOTIFICATION_GROUP_LOOKUP_FIELDS,
)

logger = logging.getLogger(__name__)


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


class GenericModelGroupResolver(RecipientResolver):
    """Generic resolver that extracts user emails from any model instance.

    Address format: {pk}@{app_label}.{model_name}.groups
    Example: 1@laboratory.laboratory.groups

    Introspects the instance's relations to find associated User objects via:
    - Direct FK/OneToOne fields pointing to User
    - Forward M2M fields to User or auth.Group
    - Reverse FK from User to this model
    - Reverse M2M from User to this model

    If no user relations are found, logs a warning — the model must have
    some relation to User or Group for this resolver to be useful.
    """

    SUFFIX = 'groups'

    def resolve(self, identifier):
        raise NotImplementedError("Call resolve_for_model(pk, model_path) instead.")

    def resolve_for_model(self, pk, model_path):
        """Resolve user emails from a model instance identified by pk and model path.

        Args:
            pk: Primary key of the model instance.
            model_path: Dot-separated app_label.model_name string.

        Returns:
            List of resolved email address strings.
        """
        from django.apps import apps

        User = get_user_model()

        try:
            parts = model_path.rsplit('.', 1)
            if len(parts) != 2:
                logger.warning(
                    'GenericModelGroupResolver: invalid model path "%s". '
                    'Expected "app_label.model_name".', model_path)
                return []
            app_label, model_name = parts
            model = apps.get_model(app_label, model_name)
            instance = model.objects.get(pk=pk)
        except Exception as e:
            logger.warning(
                'GenericModelGroupResolver: could not load %s pk=%s: %s',
                model_path, pk, e)
            return []

        emails = set()
        self._extract_user_emails(instance, User, emails, depth=0)

        if not emails:
            logger.warning(
                'GenericModelGroupResolver: no user relations found for %s pk=%s. '
                'The model has no accessible relation to User or Group.',
                model_path, pk)

        return list(emails)

    def _extract_user_emails(self, instance, User, emails, depth=0):
        """Recursively walk instance relations to collect user email addresses.

        Args:
            instance: A Django model instance.
            User: The active User model class.
            emails: Set to accumulate found email addresses.
            depth: Current recursion depth (max 2).
        """
        if depth > 2:
            return

        # Base cases
        if isinstance(instance, User):
            if instance.email:
                emails.add(instance.email)
            return

        if isinstance(instance, Group):
            found = (User.objects.filter(groups=instance)
                     .exclude(email='')
                     .values_list('email', flat=True))
            emails.update(found)
            return

        for field in instance._meta.get_fields():
            if not field.is_relation or field.related_model is None:
                continue
            try:
                # Forward FK / OneToOne → recurse into related object
                if (field.many_to_one or field.one_to_one) and not field.auto_created:
                    related_obj = getattr(instance, field.name, None)
                    if related_obj is not None:
                        self._extract_user_emails(related_obj, User, emails, depth + 1)

                # Forward M2M → recurse into each related object
                elif field.many_to_many and not field.auto_created:
                    related_manager = getattr(instance, field.name, None)
                    if related_manager is not None:
                        for obj in related_manager.all():
                            self._extract_user_emails(obj, User, emails, depth + 1)

                # Reverse FK: User → this model (User has FK pointing here)
                elif field.one_to_many and field.related_model == User:
                    accessor = field.get_accessor_name()
                    related_manager = getattr(instance, accessor, None)
                    if related_manager is not None:
                        found = (related_manager.exclude(email='')
                                 .values_list('email', flat=True))
                        emails.update(found)

                # Reverse M2M: User has M2M to this model
                elif (field.many_to_many and field.auto_created
                      and field.related_model == User):
                    accessor = field.get_accessor_name()
                    related_manager = getattr(instance, accessor, None)
                    if related_manager is not None:
                        found = (related_manager.exclude(email='')
                                 .values_list('email', flat=True))
                        emails.update(found)

            except Exception as e:
                logger.debug(
                    'GenericModelGroupResolver: skipping field %s on %s: %s',
                    field, instance, e)
                continue

    def search(self, query):
        return []


class RecipientResolverRegistry:
    """Registry for recipient resolvers keyed by domain suffix."""

    _resolvers = {}
    _generic_model_resolver = GenericModelGroupResolver()

    @classmethod
    def register(cls, suffix, resolver_class):
        """Register a resolver class for a given domain suffix.

        Args:
            suffix: Domain suffix (e.g., 'group.local').
            resolver_class: A RecipientResolver subclass.
        """
        cls._resolvers[suffix] = resolver_class()

    @classmethod
    def resolve(cls, address):
        """Resolve an address to a list of email addresses.

        Resolution order:
        1. Exact domain match in registered resolvers.
        2. Generic model group pattern: {pk}@{app_label}.{model_name}.groups
        3. Plain email address passthrough.

        Args:
            address: Email address or resolver-aware address.

        Returns:
            List of resolved email address strings.
        """
        if '@' not in address:
            return [address]

        identifier, domain = address.rsplit('@', 1)

        # 1. Registered resolver
        if domain in cls._resolvers:
            return cls._resolvers[domain].resolve(identifier)

        # 2. Generic model group: {pk}@{app_label}.{model_name}.groups
        _suffix = GenericModelGroupResolver.SUFFIX
        if domain.endswith(f'.{_suffix}'):
            model_path = domain[:-(len(_suffix) + 1)]
            return cls._generic_model_resolver.resolve_for_model(identifier, model_path)

        # 3. Plain email passthrough
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
