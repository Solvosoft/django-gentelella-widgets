from django.test import TestCase

from djgentelella.async_notification.registry import register_context, clear_registry
from djgentelella.async_notification.introspection import (
    describe_model_fields, get_fields_for_context
)
from django.contrib.auth.models import User


class DescribeModelFieldsTest(TestCase):

    def test_basic_fields(self):
        fields = describe_model_fields(User, depth=0)
        field_names = [f['name'] for f in fields]
        self.assertIn('username', field_names)
        self.assertIn('email', field_names)
        self.assertIn('first_name', field_names)

    def test_field_types(self):
        fields = describe_model_fields(User, depth=0)
        username_field = next(f for f in fields if f['name'] == 'username')
        self.assertEqual(username_field['type'], 'string')
        self.assertFalse(username_field['is_relation'])

    def test_depth_zero_no_expansion(self):
        fields = describe_model_fields(User, depth=0)
        for f in fields:
            self.assertFalse(f['expandable'])

    def test_depth_expansion(self):
        fields = describe_model_fields(User, depth=1)
        # User has no FK fields to expand by default in auth.User
        # but logentry_set reverse relations exist
        expandable = [f for f in fields if f['expandable']]
        # Any expandable fields should have children in the result
        for exp_field in expandable:
            children = [f for f in fields
                        if f['name'].startswith(exp_field['name'] + '.')]
            self.assertGreater(len(children), 0)

    def test_exclude_fields(self):
        fields = describe_model_fields(User, depth=0, exclude=['password', 'id'])
        field_names = [f['name'] for f in fields]
        self.assertNotIn('password', field_names)
        self.assertNotIn('id', field_names)

    def test_prefix(self):
        fields = describe_model_fields(User, depth=0, prefix='user')
        for f in fields:
            self.assertTrue(f['name'].startswith('user.'))

    def test_verbose_name(self):
        fields = describe_model_fields(User, depth=0)
        email_field = next(f for f in fields if f['name'] == 'email')
        self.assertIn('verbose_name', email_field)
        self.assertTrue(len(email_field['verbose_name']) > 0)


class GetFieldsForContextTest(TestCase):

    def setUp(self):
        clear_registry()

    def tearDown(self):
        clear_registry()

    def test_nonexistent_code(self):
        self.assertIsNone(get_fields_for_context('nonexistent'))

    def test_with_registered_model(self):
        register_context(
            code='test_ctx',
            subject='Test',
            models={'user': 'auth.User'},
        )
        result = get_fields_for_context('test_ctx')
        self.assertIn('user', result)
        self.assertIn('extra_variables', result)
        field_names = [f['name'] for f in result['user']]
        self.assertTrue(any('user.username' in n for n in field_names))

    def test_with_exclusions(self):
        register_context(
            code='excl_ctx',
            subject='Test',
            models={'user': 'auth.User'},
            exclude={'user': ['password', 'is_superuser']},
        )
        result = get_fields_for_context('excl_ctx')
        field_names = [f['name'] for f in result['user']]
        self.assertNotIn('user.password', field_names)
        self.assertNotIn('user.is_superuser', field_names)

    def test_extra_variables_in_result(self):
        register_context(
            code='extras_ctx',
            subject='Test',
            models={},
            extra_variables={'site_url': 'The URL of the site'},
        )
        result = get_fields_for_context('extras_ctx')
        extras = result['extra_variables']
        self.assertEqual(len(extras), 1)
        self.assertEqual(extras[0]['name'], 'site_url')
        self.assertEqual(extras[0]['type'], 'custom')

    def test_invalid_model_string(self):
        register_context(
            code='bad_model',
            subject='Test',
            models={'bad': 'nonexistent.Model'},
        )
        result = get_fields_for_context('bad_model')
        self.assertEqual(result['bad'], [])

    def test_depth_limit(self):
        register_context(
            code='depth_test',
            subject='Test',
            models={'user': 'auth.User'},
            depth=0,
        )
        result = get_fields_for_context('depth_test')
        for f in result['user']:
            self.assertFalse(f['expandable'])
