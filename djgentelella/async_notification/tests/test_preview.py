from django.test import TestCase

from djgentelella.async_notification.registry import register_context, clear_registry
from djgentelella.async_notification.preview import (
    DummyContextObject, AutoPreviewProvider,
    build_dummy_context, render_preview
)


class DummyContextObjectTest(TestCase):

    def test_string_type(self):
        val = DummyContextObject.get_dummy_value('string')
        self.assertIsInstance(val, str)
        self.assertTrue(len(val) > 0)

    def test_integer_type(self):
        val = DummyContextObject.get_dummy_value('integer')
        self.assertIsInstance(val, int)

    def test_boolean_type(self):
        val = DummyContextObject.get_dummy_value('boolean')
        self.assertIsInstance(val, bool)

    def test_date_type(self):
        import datetime
        val = DummyContextObject.get_dummy_value('date')
        self.assertIsInstance(val, datetime.date)

    def test_unknown_type(self):
        val = DummyContextObject.get_dummy_value('unknown')
        self.assertEqual(val, 'Unknown')

    def test_missing_type(self):
        val = DummyContextObject.get_dummy_value('nonexistent_type')
        self.assertEqual(val, 'N/A')


class AutoPreviewProviderTest(TestCase):

    def test_valid_model(self):
        provider = AutoPreviewProvider('auth.User')
        qs = provider.get_queryset()
        self.assertIsNotNone(qs)

    def test_invalid_model(self):
        provider = AutoPreviewProvider('nonexistent.Model')
        self.assertIsNone(provider.model)
        qs = provider.get_queryset()
        self.assertEqual(list(qs), [])


class BuildDummyContextTest(TestCase):

    def setUp(self):
        clear_registry()

    def tearDown(self):
        clear_registry()

    def test_unregistered_code(self):
        ctx = build_dummy_context('nonexistent')
        self.assertEqual(ctx, {})

    def test_with_model(self):
        register_context(
            code='test_preview',
            subject='Test',
            models={'user': 'auth.User'},
            depth=0,
        )
        ctx = build_dummy_context('test_preview')
        self.assertIn('user', ctx)
        # user should be a dict with field values
        self.assertIsInstance(ctx['user'], dict)

    def test_with_extra_variables(self):
        register_context(
            code='extras',
            subject='Test',
            models={},
            extra_variables={'site_url': 'The site URL'},
        )
        ctx = build_dummy_context('extras')
        self.assertIn('site_url', ctx)


class RenderPreviewTest(TestCase):

    def test_simple_render(self):
        result = render_preview('<p>Hello {{ name }}</p>', {'name': 'World'})
        self.assertIn('Hello World', result)

    def test_empty_context(self):
        result = render_preview('<p>Static content</p>', {})
        self.assertIn('Static content', result)

    def test_syntax_error(self):
        result = render_preview('{% invalid %}', {})
        self.assertIn('Template Error', result)

    def test_no_base_template(self):
        result = render_preview('<b>Bold</b>', {}, base_template=None)
        self.assertEqual(result, '<b>Bold</b>')

    def test_unknown_base_template_key(self):
        result = render_preview('<p>Test</p>', {},
                                base_template='nonexistent_key')
        self.assertIn('Test', result)

    def test_nested_variables(self):
        result = render_preview(
            '<p>{{ user.name }}</p>',
            {'user': {'name': 'Alice'}})
        self.assertIn('Alice', result)
