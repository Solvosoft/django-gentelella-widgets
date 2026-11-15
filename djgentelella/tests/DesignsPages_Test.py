"""djgentelella.designs served: pages, security, endpoints, commands, admin."""

import json
import threading
import time
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.contrib.sites.models import Site
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from djgentelella.designs import engine, publishing
from djgentelella.designs.models import Page
from djgentelella.designs.registry import register
from djgentelella.designs.sanitize import clean_html
from djgentelella.tests.Designs_Test import FIXTURES, DesignState, design, node
from djgentelella.tests.designs_fixtures.components import EchoComponent


def grant(user, *codenames):
    for codename in codenames:
        app_label, name = codename.split('.')
        user.user_permissions.add(Permission.objects.get(
            content_type__app_label=app_label, codename=name))
    # has_perm caches what it read: start again from the database.
    return User.objects.get(pk=user.pk)


class DesignClient(DesignState, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('ana', password='pw')
        self.client.force_login(self.user)

    def publish(self, document, path='sample', published=True, **kwargs):
        page, errors = publishing.publish(document, path=path, published=published,
                                          **kwargs)
        self.assertEqual(errors, [])
        return page

    def get(self, path):
        return self.client.get(reverse('gt-design-page', args=[path]))


class PublishAndViewTests(DesignClient):
    def test_editor_fixture_published_by_command_and_seen(self):
        out = StringIO()
        call_command('gtdesigns_publish', str(FIXTURES / 'product_admin.json'),
                     stdout=out)
        self.assertIn('Published', out.getvalue())
        page = Page.objects.get()
        self.assertEqual((page.path, page.title, page.is_published),
                         ('products', 'Products', True))
        self.assertEqual(page.required_permissions(), ['demoapp.view_person'])
        self.assertEqual(self.get('products').status_code, 403)
        self.user = grant(self.user, 'demoapp.view_person')
        response = self.get('products/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertTemplateUsed(response, 'gentelella/base.html')
        self.assertIn('<title>Products</title>', content)
        self.assertIn('<p class="lead">The catalogue, with its categories and '
                      'tags.</p>', content)
        self.assertIn('data-gtdesign="product_admin"', content)

    def test_every_fixture_publishes(self):
        for name in ('product_admin', 'sales_dashboard', 'category_products'):
            call_command('gtdesigns_publish', str(FIXTURES / ('%s.json' % name)),
                         stdout=StringIO())
        self.assertEqual(sorted(Page.objects.values_list('path', flat=True)),
                         ['category-products', 'dashboard', 'products'])

    def test_publish_options(self):
        site = Site.objects.create(domain='apps.example', name='apps')
        call_command('gtdesigns_publish', str(FIXTURES / 'sales_dashboard.json'),
                     '--site', 'apps.example', '--path', '/ventas/tablero/',
                     '--user', 'ana', '--draft', stdout=StringIO())
        page = Page.objects.get()
        self.assertEqual((page.site, page.path, page.is_published, page.updated_by),
                         (site, 'ventas/tablero', False, self.user))
        # Publishing again replaces the page at (site, path).
        call_command('gtdesigns_publish', str(FIXTURES / 'sales_dashboard.json'),
                     '--site', 'apps.example', '--path', 'ventas/tablero',
                     stdout=StringIO())
        self.assertTrue(Page.objects.get().is_published)

    def test_publish_refuses_an_invalid_design(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json'
            path.write_text(json.dumps(design(node('nope', 'x'),
                                              permissions=['demoapp.fly_person'])))
            with self.assertRaises(CommandError) as raised:
                call_command('gtdesigns_publish', str(path), stdout=StringIO())
            self.assertIn("unknown component type 'nope'", str(raised.exception))
            path.write_text('{not json')
            with self.assertRaisesMessage(CommandError, 'not valid JSON'):
                call_command('gtdesigns_publish', str(path))
        with self.assertRaisesMessage(CommandError, 'No site'):
            call_command('gtdesigns_publish', str(FIXTURES / 'product_admin.json'),
                         '--site', 'nowhere.example')
        with self.assertRaisesMessage(CommandError, 'No user'):
            call_command('gtdesigns_publish', str(FIXTURES / 'product_admin.json'),
                         '--user', 'nobody')
        self.assertFalse(Page.objects.exists())

    def test_export(self):
        page = self.publish(design(), path='a/b')
        out = StringIO()
        call_command('gtdesigns_export', 'a/b', stdout=out)
        self.assertEqual(json.loads(out.getvalue()), page.document)
        with TemporaryDirectory() as directory:
            call_command('gtdesigns_export', '--output', directory, stdout=StringIO())
            exported = Path(directory) / 'a__b.json'
            self.assertEqual(json.loads(exported.read_text()), page.document)
            # What is exported publishes again, unchanged.
            call_command('gtdesigns_publish', str(exported), '--path', 'c',
                         stdout=StringIO())
            self.assertEqual(Page.objects.get(path='c').hash, page.hash)
            single = Path(directory) / 'one.json'
            call_command('gtdesigns_export', 'a/b', '-o', str(single))
            self.assertEqual(json.loads(single.read_text()), page.document)
        with self.assertRaisesMessage(CommandError, 'No page'):
            call_command('gtdesigns_export', 'nope')
        with self.assertRaisesMessage(CommandError, '--output'):
            call_command('gtdesigns_export')

    def test_page_without_permissions_needs_login_by_default(self):
        self.publish(design())
        self.assertEqual(self.get('sample').status_code, 200)
        self.client.logout()
        response = self.get('sample')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        with override_settings(GT_DESIGNS_LOGIN_REQUIRED=False):
            self.assertEqual(self.get('sample').status_code, 200)

    def test_missing_page(self):
        self.assertEqual(self.get('nope').status_code, 404)

    # The Site is found by host; SITE_ID = 1 (the demo's) does not get in the way.
    def test_site_rule_in_the_view(self):
        site = Site.objects.create(domain='testserver', name='test')
        self.publish(design(node('html', 'x', {'html': 'global'})))
        self.assertContains(self.get('sample'), 'global')
        self.publish(design(node('html', 'x', {'html': 'mine'})), site=site)
        self.assertContains(self.get('sample'), 'mine')
        with self.settings(ALLOWED_HOSTS=['other.example']):
            response = self.client.get(reverse('gt-design-page', args=['sample']),
                                       HTTP_HOST='other.example')
        self.assertContains(response, 'global')

    def test_a_page_that_no_longer_resolves(self):
        page = self.publish(design())
        Page.objects.filter(pk=page.pk).update(
            document=design(node('nope', 'x')), hash='changed')
        with self.assertLogs('djgentelella.designs.engine', 'WARNING'):
            self.assertEqual(self.get('sample').status_code, 404)
        self.user = grant(self.user, 'gtdesigns.change_page')
        response = self.get('sample')
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, 'unknown component type', status_code=503)


# English labels are asserted: the demo runs in Spanish once its .mo, which is
# not versioned, is compiled, and a local run would disagree with CI.
@override_settings(LANGUAGE_CODE='en')
class SecurityTests(DesignClient):
    def render_html(self, html):
        self.publish(design(node('html', 'x', {'html': html})))
        response = self.get('sample')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        start = content.index('data-gtdesign="x"')
        return content[start:content.index('</div>', start)]

    def test_script_and_handlers_are_removed(self):
        markup = self.render_html(
            '<p onclick="alert(1)" class="lead">hi<script>alert(2)</script></p>'
            '<img src="x.png" onerror="alert(3)">'
            '<a href="javascript:alert(4)">a</a><a href="/ok" target="_blank">b</a>'
            '<iframe src="https://evil.example"></iframe><style>p{}</style>')
        for needle in ('onclick', 'alert', '<script', 'onerror', 'javascript:',
                       '<iframe', '<style'):
            self.assertNotIn(needle, markup)
        self.assertIn('<p class="lead">hi</p>', markup)
        self.assertIn('<img src="x.png">', markup)
        self.assertIn('<a href="/ok" target="_blank" rel="noopener noreferrer">b</a>',
                      markup)

    def test_template_tags_are_not_evaluated(self):
        markup = self.render_html('<p>{% now "Y" %} {{ user.password }} '
                                  '{% url "login" %}</p>')
        self.assertIn('{% now "Y" %} {{ user.password }} {% url "login" %}', markup)

    def test_style_is_filtered(self):
        cleaned = clean_html('<p style="color: red; background: url(javascript:x); '
                             'position: fixed">x</p>')
        self.assertIn('color:red', cleaned.replace(' ', ''))
        self.assertNotIn('url(', cleaned)
        self.assertNotIn('position', cleaned)

    def test_bootstrap_markup_survives(self):
        cleaned = clean_html('<div class="x_panel" data-toggle="x" aria-label="y" '
                             'role="note"><table class="table"><tr><td colspan="2">'
                             '<i class="fa fa-check"></i></td></tr></table></div>')
        self.assertIn('class="x_panel"', cleaned)
        self.assertIn('data-toggle="x"', cleaned)
        self.assertIn('aria-label="y"', cleaned)
        self.assertIn('colspan="2"', cleaned)
        self.assertIn('<i class="fa fa-check"></i>', cleaned)

    def test_only_bootstrap_data_attributes_survive(self):
        cleaned = clean_html(
            '<div data-bs-toggle="collapse" data-bs-target="#x" data-toggle="tab" '
            'data-widget="AutocompleteSelect" data-url="/evil/" '
            'data-gt-dynamic=\'[{"actions": []}]\' data-widget-id="w" '
            'data-bs-html="true" data-bs-sanitize="false" '
            'data-bs-template="&lt;b&gt;" data-anything="y">x</div>')
        for kept in ('data-bs-toggle="collapse"', 'data-bs-target="#x"',
                     'data-toggle="tab"'):
            self.assertIn(kept, cleaned)
        for dropped in ('data-widget', 'data-url', 'data-gt-dynamic',
                        'data-bs-html', 'data-bs-sanitize', 'data-bs-template',
                        'data-anything'):
            self.assertNotIn(dropped, cleaned)

    def test_unpublished_page_is_404_without_permission(self):
        self.publish(design(), published=False)
        self.assertEqual(self.get('sample').status_code, 404)
        self.client.logout()
        self.assertEqual(self.get('sample').status_code, 404)
        self.user = grant(self.user, 'gtdesigns.change_page')
        self.client.force_login(self.user)
        response = self.get('sample')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Preview: this page is not published')

    def test_meta_permissions_are_required(self):
        self.publish(design(permissions={'view': ['demoapp.view_person',
                                                  'demoapp.change_person']}))
        Page.objects.get().permissions.clear()  # only the document asks for them
        self.assertEqual(self.get('sample').status_code, 403)
        self.user = grant(self.user, 'demoapp.view_person')
        self.assertEqual(self.get('sample').status_code, 403)
        self.user = grant(self.user, 'demoapp.change_person')
        self.assertEqual(self.get('sample').status_code, 200)
        self.client.logout()
        self.assertEqual(self.get('sample').status_code, 302)

    def test_page_m2m_permissions_are_required(self):
        page = self.publish(design())
        page.permissions.add(Permission.objects.get(codename='view_country'))
        self.assertEqual(self.get('sample').status_code, 403)
        self.user = grant(self.user, 'demoapp.view_country')
        self.assertEqual(self.get('sample').status_code, 200)

    def template_design(self):
        document = design(node('html', 'x', {
            'html': '<p>{{ user.username }}<script>alert(1)</script></p>'}))
        document['assets'] = {'js': 'window.trusted = 1;'}
        return document

    def test_templates_and_js_need_setting_and_publisher_permission(self):
        self.publish(self.template_design(), user=self.user)
        content = self.get('sample').content.decode()
        self.assertIn('{{ user.username }}', content)
        self.assertNotIn('window.trusted', content)

        with self.settings(GT_DESIGNS_ALLOW_TEMPLATES=True, GT_DESIGNS_ALLOW_JS=True):
            # The setting alone is not enough: the publisher lacks the perms.
            content = self.get('sample').content.decode()
            self.assertIn('{{ user.username }}', content)
            self.assertNotIn('window.trusted', content)
            self.user = grant(self.user, 'gtdesigns.publish_template',
                              'gtdesigns.publish_js')
            engine.clear_cache()
            content = self.get('sample').content.decode()
            self.assertIn('<p>ana</p>', content, 'rendered, then cleaned')
            self.assertNotIn('alert(1)', content)
            self.assertIn('<script>window.trusted = 1;</script>', content)

        # Without the setting, the permission is not enough either.
        engine.clear_cache()
        content = self.get('sample').content.decode()
        self.assertIn('{{ user.username }}', content)
        self.assertNotIn('window.trusted', content)

    @override_settings(GT_DESIGNS_ALLOW_TEMPLATES=True)
    def test_a_page_published_without_a_user_is_not_trusted(self):
        self.publish(self.template_design())
        self.assertIn('{{ user.username }}', self.get('sample').content.decode())

    @override_settings(GT_DESIGNS_ALLOW_TEMPLATES=True)
    def test_template_syntax_is_checked_when_trusted(self):
        self.user = grant(self.user, 'gtdesigns.publish_template')
        page, errors = publishing.publish(design(node('html', 'x', {
            'html': '{% if %}'})), path='bad', user=self.user)
        self.assertIsNone(page)
        self.assertIn('not a valid Django template', errors[0].message)


class EndpointRouterTests(DesignClient):
    def setUp(self):
        super().setUp()
        register(EchoComponent)
        self.page = self.publish(design(node('echo', 'hello', {'message': 'hi'}),
                                        node('html', 'plain', {'html': ''})))

    def api(self, node_id, rest='', page=None):
        return self.client.get('/gtapis/designs/%d/%s/%s' % (
            (page or self.page).pk, node_id, rest))

    def test_dispatch_to_the_node_viewsets(self):
        response = self.api('hello')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'node': 'hello', 'message': 'hi',
                                           'page': self.page.pk})
        self.assertEqual(self.api('hello', '7/').json(), {'node': 'hello', 'pk': '7'})
        self.assertEqual(self.api('hello', 'shout/').json(), {'shout': 'HI'})
        self.assertEqual(reverse('gt-design-endpoint', kwargs={
            'page_id': 1, 'node_id': 'n', 'rest': 'x/'}), '/gtapis/designs/1/n/x/')

    def test_the_build_comes_from_the_cached_resolve(self):
        self.api('hello')
        resolved, _errors = engine.resolve_page(self.page)
        resolver = resolved.endpoint_resolver('hello')
        self.api('hello', 'shout/')
        self.assertIs(engine.resolve_page(self.page)[0].endpoint_resolver('hello'),
                      resolver)

    def test_threads_share_one_resolver(self):
        """A cached page is shared between threads: its resolvers and the
        viewsets behind them are built once."""
        resolved, _errors = engine.resolve(self.page.document)
        component = resolved.nodes['hello'].component
        original = type(component).endpoints
        calls = []

        def slow_endpoints(this, build):
            calls.append(build)
            time.sleep(0.1)
            return original(this, build)

        found = []
        with mock.patch.object(type(component), 'endpoints', slow_endpoints):
            threads = [threading.Thread(target=lambda: found.append(
                resolved.endpoint_resolver('hello'))) for _ in range(3)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        self.assertEqual(len(calls), 1)
        self.assertEqual(len({id(resolver) for resolver in found}), 1)

    def test_not_found(self):
        self.assertEqual(self.api('plain').status_code, 404, 'no endpoints')
        self.assertEqual(self.api('missing').status_code, 404)
        self.assertEqual(self.api('hello', 'a/b/c/').status_code, 404)
        self.assertEqual(self.client.get('/gtapis/designs/999/hello/').status_code, 404)

    def test_the_page_rules_apply(self):
        self.page.is_published = False
        self.page.save()
        self.assertEqual(self.api('hello').status_code, 404)
        self.page.is_published = True
        self.page.save()
        self.page.permissions.add(Permission.objects.get(codename='view_person'))
        self.assertEqual(self.api('hello').status_code, 403)
        self.user = grant(self.user, 'demoapp.view_person')
        self.assertEqual(self.api('hello').status_code, 200)
        self.client.logout()
        self.assertEqual(self.api('hello').status_code, 403)

    def test_a_page_of_another_site(self):
        site = Site.objects.create(domain='elsewhere.example', name='x')
        page = self.publish(design(node('echo', 'hello', {'message': 'x'})),
                            path='other', site=site)
        self.assertEqual(self.api('hello', page=page).status_code, 404)


# English labels are asserted: the demo runs in Spanish once its .mo, which is
# not versioned, is compiled, and a local run would disagree with CI.
@override_settings(LANGUAGE_CODE='en')
class AdminTests(DesignClient):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('root', 'root@example.com', 'pw')
        self.client.force_login(self.admin)

    def test_list_change_and_validate(self):
        page = self.publish(design(node('html', 'x', {'html': '<b>x</b>'})))
        self.assertContains(self.client.get(
            reverse('admin:gtdesigns_page_changelist')), 'sample')
        change = self.client.get(reverse('admin:gtdesigns_page_change', args=[page.pk]))
        self.assertContains(change, reverse('admin:gtdesigns_page_validate',
                                            args=[page.pk]))
        self.assertContains(change, '&lt;b&gt;x&lt;/b&gt;')  # the JSON, read only
        self.assertNotContains(change, 'name="document"')
        response = self.client.get(reverse('admin:gtdesigns_page_validate',
                                           args=[page.pk]), follow=True)
        self.assertContains(response, 'The design is valid.')
        Page.objects.filter(pk=page.pk).update(document=design(node('nope', 'x')))
        response = self.client.get(reverse('admin:gtdesigns_page_validate',
                                           args=[page.pk]), follow=True)
        self.assertContains(response, 'unknown component type')

    def test_add_validates_the_document(self):
        url = reverse('admin:gtdesigns_page_add')
        response = self.client.post(url, {'path': 'new', 'document': json.dumps(
            design(node('nope', 'x')))})
        self.assertContains(response, 'unknown component type')
        self.client.post(url, {'path': 'new', 'document': json.dumps(design()),
                               'is_published': 'on'})
        page = Page.objects.get()
        self.assertEqual((page.path, page.updated_by), ('new', self.admin))
