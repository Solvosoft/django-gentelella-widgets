from django.contrib.auth.models import Group

from djgentelella.async_notification.tests import AsyncNotificationTestBase
from djgentelella.async_notification.resolvers import (
    RecipientResolver, DjangoGroupResolver, RecipientResolverRegistry
)


class DjangoGroupResolverTest(AsyncNotificationTestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.group = Group.objects.create(name='developers')
        cls.user.groups.add(cls.group)
        cls.superuser.groups.add(cls.group)

    def test_resolve_existing_group(self):
        resolver = DjangoGroupResolver()
        emails = resolver.resolve('developers')
        self.assertIn(self.user.email, emails)
        self.assertIn(self.superuser.email, emails)

    def test_resolve_nonexistent_group(self):
        resolver = DjangoGroupResolver()
        emails = resolver.resolve('nonexistent')
        self.assertEqual(emails, [])

    def test_resolve_excludes_empty_emails(self):
        self.noperms_user.email = ''
        self.noperms_user.save()
        group = Group.objects.create(name='noemail')
        self.noperms_user.groups.add(group)
        resolver = DjangoGroupResolver()
        emails = resolver.resolve('noemail')
        self.assertEqual(emails, [])

    def test_search(self):
        resolver = DjangoGroupResolver()
        results = resolver.search('dev')
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]['value'], 'developers@group.local')
        self.assertIn('label', results[0])


class RecipientResolverRegistryTest(AsyncNotificationTestBase):

    def setUp(self):
        RecipientResolverRegistry.reset()
        RecipientResolverRegistry.register('group.local', DjangoGroupResolver)

    def tearDown(self):
        RecipientResolverRegistry.reset()
        RecipientResolverRegistry.register('group.local', DjangoGroupResolver)

    def test_resolve_regular_email(self):
        result = RecipientResolverRegistry.resolve('user@example.com')
        self.assertEqual(result, ['user@example.com'])

    def test_resolve_group_address(self):
        group = Group.objects.create(name='testers')
        self.user.groups.add(group)
        result = RecipientResolverRegistry.resolve('testers@group.local')
        self.assertIn(self.user.email, result)

    def test_resolve_unknown_domain(self):
        result = RecipientResolverRegistry.resolve('someone@unknown.domain')
        self.assertEqual(result, ['someone@unknown.domain'])

    def test_search_all(self):
        Group.objects.create(name='search-test')
        results = RecipientResolverRegistry.search_all('search')
        self.assertTrue(len(results) > 0)

    def test_custom_resolver(self):
        class TestResolver(RecipientResolver):
            def resolve(self, identifier):
                return [f'{identifier}@test.com']

            def search(self, query):
                return [{'value': f'{query}@test.local', 'label': query}]

        RecipientResolverRegistry.register('test.local', TestResolver)
        result = RecipientResolverRegistry.resolve('john@test.local')
        self.assertEqual(result, ['john@test.com'])

    def test_reset(self):
        RecipientResolverRegistry.reset()
        # After reset, group addresses should pass through as-is
        result = RecipientResolverRegistry.resolve('test@group.local')
        self.assertEqual(result, ['test@group.local'])
