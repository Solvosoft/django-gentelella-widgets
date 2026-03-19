from django.test import SimpleTestCase

from djgentelella.async_notification.registry import (
    register_context, get_context_config, get_all_contexts, clear_registry
)


class RegistryTest(SimpleTestCase):

    def setUp(self):
        clear_registry()

    def tearDown(self):
        clear_registry()

    def test_register_and_retrieve(self):
        register_context(
            code='order_confirmation',
            subject='Order #{{ order.id }} confirmed',
            models={'order': 'demoapp.Customer', 'user': 'auth.User'},
        )
        config = get_context_config('order_confirmation')
        self.assertIsNotNone(config)
        self.assertEqual(config['code'], 'order_confirmation')
        self.assertEqual(config['subject'], 'Order #{{ order.id }} confirmed')
        self.assertEqual(config['models'], {
            'order': 'demoapp.Customer', 'user': 'auth.User'})

    def test_retrieve_nonexistent(self):
        self.assertIsNone(get_context_config('nonexistent'))

    def test_get_all_contexts(self):
        register_context(code='a', subject='A', models={})
        register_context(code='b', subject='B', models={})
        all_ctx = get_all_contexts()
        self.assertEqual(len(all_ctx), 2)
        self.assertIn('a', all_ctx)
        self.assertIn('b', all_ctx)

    def test_clear_registry(self):
        register_context(code='x', subject='X', models={})
        self.assertIsNotNone(get_context_config('x'))
        clear_registry()
        self.assertIsNone(get_context_config('x'))

    def test_defaults(self):
        register_context(code='minimal', subject='S', models={'m': 'auth.User'})
        config = get_context_config('minimal')
        self.assertEqual(config['exclude'], {})
        self.assertEqual(config['extra_variables'], {})
        self.assertEqual(config['depth'], 2)
        self.assertIsNone(config['preview_provider'])

    def test_extra_variables(self):
        register_context(
            code='with_extras',
            subject='S',
            models={},
            extra_variables={'site_url': 'The site URL', 'year': 'Current year'},
        )
        config = get_context_config('with_extras')
        self.assertEqual(len(config['extra_variables']), 2)
        self.assertIn('site_url', config['extra_variables'])

    def test_overwrite_registration(self):
        register_context(code='dup', subject='First', models={})
        register_context(code='dup', subject='Second', models={})
        config = get_context_config('dup')
        self.assertEqual(config['subject'], 'Second')
