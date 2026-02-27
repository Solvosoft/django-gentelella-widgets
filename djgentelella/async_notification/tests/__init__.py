from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class AsyncNotificationTestBase(TestCase):
    """Base test class with shared fixtures for async_notification tests."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        cls.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass123'
        )
        cls.noperms_user = User.objects.create_user(
            username='noperms',
            email='noperms@example.com',
            password='nopermspass123'
        )


class AsyncNotificationAPITestBase(AsyncNotificationTestBase):
    """Base test class for API tests with DataTable helpers."""

    def get_datatable_response(self, url, user=None, query_params=None):
        """Helper to make DataTable-compatible GET requests."""
        if user:
            self.client.force_login(user)
        params = {'draw': 1, 'limit': 10, 'offset': 0}
        if query_params:
            params.update(query_params)
        return self.client.get(url, params)

    def assert_datatable_response(self, response, expected_count=None):
        """Assert that a response has valid DataTable structure."""
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('data', data)
        self.assertIn('recordsTotal', data)
        self.assertIn('recordsFiltered', data)
        self.assertIn('draw', data)
        if expected_count is not None:
            self.assertEqual(len(data['data']), expected_count)
