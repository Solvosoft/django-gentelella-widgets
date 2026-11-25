"""``{% get_settings %}`` escapes the values that are not HTML (W20).

On 4faeda00 the tag returned every value through ``mark_safe``: a
``site_title`` or ``sidebar_title`` with markup -- the title of a djodo App
typed by its owner, a value imported from a file -- was printed as HTML in
every page.
"""
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.template import Context, Template
from django.test import TestCase, override_settings
from django.urls import reverse

from djgentelella.utils import (
    escape_setting, get_settings_display, html_settings, set_settings,
    setting_allows_html,
)

SCRIPT = '<script>alert(1)</script>'


def render(text, **context):
    return Template('{% load gtsettings %}' + text).render(Context(context))


class SettingsEscapeTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_a_text_setting_is_escaped(self):
        # The reproduction: on 4faeda00 this printed the script tag.
        set_settings('site_title', SCRIPT)
        html = render("{% get_settings 'site_title' %}")
        self.assertNotIn('<script>', html)
        self.assertEqual(html, '&lt;script&gt;alert(1)&lt;/script&gt;')

    def test_also_through_a_variable(self):
        set_settings('sidebar_title', SCRIPT)
        html = render("{% get_settings 'sidebar_title' as title %}{{ title }}"
                      "|{{ title|safe }}")
        self.assertEqual(html, '&lt;script&gt;alert(1)&lt;/script&gt;|'
                               '&lt;script&gt;alert(1)&lt;/script&gt;')

    def test_the_pages_escape_the_titles(self):
        set_settings('site_title', SCRIPT)
        set_settings('sidebar_title', '<b onmouseover=x>Sales</b>')
        user = get_user_model().objects.create_user('settings-w20')
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, SCRIPT)
        self.assertNotContains(response, '<b onmouseover')
        self.assertContains(response, '&lt;b onmouseover=x&gt;Sales&lt;/b&gt;')

    def test_a_value_stored_escaped_shows_the_same(self):
        # What djodo and older code stored, escaped by hand.
        set_settings('sidebar_title', 'Ventas &lt;Norte&gt; &amp; Sur')
        self.assertEqual(render("{% get_settings 'sidebar_title' %}"),
                         'Ventas &lt;Norte&gt; &amp; Sur')

    def test_a_bare_ampersand(self):
        set_settings('site_title', 'R&D & co &copy; &#169; &#xa9; &bogus')
        self.assertEqual(render("{% get_settings 'site_title' %}"),
                         'R&amp;D &amp; co &copy; &#169; &#xa9; &amp;bogus')

    def test_quotes_in_an_attribute(self):
        set_settings('sidebar_icon', 'fa" onclick="x')
        html = render('<i class="{% get_settings \'sidebar_icon\' %}"></i>')
        self.assertEqual(html, '<i class="fa&quot; onclick=&quot;x"></i>')

    def test_the_logo_is_html(self):
        logo = '<img src="/static/logo.png" alt="logo">'
        set_settings('site_logo', logo)
        self.assertEqual(render("{% get_settings 'site_logo' %}"), logo)
        self.assertTrue(setting_allows_html('site_logo'))
        self.assertFalse(setting_allows_html('site_title'))

    @override_settings(GT_HTML_SETTINGS=['site_title'])
    def test_the_html_settings_are_configurable(self):
        set_settings('site_title', '<b>Bold</b>')
        set_settings('site_logo', '<img src="x">')
        self.assertEqual(html_settings(), frozenset(['site_title']))
        self.assertEqual(render("{% get_settings 'site_title' %}"), '<b>Bold</b>')
        self.assertEqual(render("{% get_settings 'site_logo' %}"),
                         '&lt;img src=&quot;x&quot;&gt;')

    def test_the_default(self):
        self.assertEqual(render("{% get_settings 'nothing' 'My Site' %}"),
                         'My Site')
        self.assertEqual(get_settings_display('nothing', default='x'), 'x')

    def test_the_site_value(self):
        site = Site.objects.create(domain='ventas.example.com', name='Ventas')
        set_settings('site_title', 'Global')
        set_settings('site_title', '<i>Ventas</i>', site=site)
        self.assertEqual(get_settings_display('site_title', site=site),
                         '&lt;i&gt;Ventas&lt;/i&gt;')
        self.assertEqual(get_settings_display('site_title'), 'Global')

    def test_escape_setting(self):
        self.assertEqual(escape_setting("a'b"), 'a&#x27;b')
        self.assertEqual(escape_setting(5), '5')
