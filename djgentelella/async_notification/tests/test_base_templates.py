"""Render checks for the shipped base email templates and utility partials."""

from django.template.loader import render_to_string
from django.test import TestCase

from djgentelella.async_notification.preview import wrap_in_base_template

BASE_KEYS = ['executive', 'product', 'transactional', 'newsletter']


class BaseTemplateRenderTest(TestCase):

    def test_each_base_renders_with_content_and_brand(self):
        for key in BASE_KEYS:
            html = wrap_in_base_template('<p>Hello world</p>', key)
            self.assertIn('Hello world', html, key)
            self.assertIn('<!DOCTYPE', html, key)
            # brand.name from the demo ASYNC_NOTIFICATION_BRAND
            self.assertIn('Demo Org', html, key)
            # inheritance from the shared shell resolved
            self.assertIn('an-body', html, key)

    def test_unknown_key_returns_content_unchanged(self):
        self.assertEqual(
            wrap_in_base_template('<p>x</p>', 'does-not-exist'), '<p>x</p>')

    def test_product_renders_cta_from_extra_context(self):
        html = wrap_in_base_template(
            '<p>News</p>', 'product',
            {'cta_url': 'https://example.com/go', 'cta_label': 'Get started'})
        self.assertIn('https://example.com/go', html)
        self.assertIn('Get started', html)


class UtilityPartialTest(TestCase):

    def test_button_is_bulletproof(self):
        html = render_to_string(
            'async_notification/base/utils/button.html',
            {'url': 'https://example.com', 'label': 'Click me'})
        self.assertIn('https://example.com', html)
        self.assertIn('Click me', html)
        self.assertIn('v:roundrect', html)   # Outlook VML fallback

    def test_info_box_title_and_text(self):
        html = render_to_string(
            'async_notification/base/utils/info_box.html',
            {'title': 'Heads up', 'text': 'Trial ends soon.'})
        self.assertIn('Heads up', html)
        self.assertIn('Trial ends soon.', html)

    def test_spacer_uses_height(self):
        html = render_to_string(
            'async_notification/base/utils/spacer.html', {'height': 24})
        self.assertIn('24px', html)

    def test_include_renders_through_preview(self):
        """The preview path renders {% include %} of a utility partial, so an
        author sees the same output the template-code send path produces."""
        from djgentelella.async_notification.preview import render_preview
        html = render_preview(
            '<p>x</p>{% include '
            '"async_notification/base/utils/button.html" '
            'with url="https://x/go" label="GoNow" %}', {})
        self.assertIn('GoNow', html)
        self.assertIn('v:roundrect', html)
