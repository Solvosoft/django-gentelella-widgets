"""What serving a published design page costs once it is cached, and the
cache of its publisher's trust."""

from unittest import mock

from django.contrib.auth.models import Permission, User
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from djgentelella.designs import engine, views
from djgentelella.designs.models import Page
from djgentelella.tests.DesignsPages_Test import DesignClient, grant
from djgentelella.tests.Designs_Test import design, node

TRUSTED = {'GT_DESIGNS_ALLOW_TEMPLATES': True, 'GT_DESIGNS_ALLOW_JS': True}


def trusted_design():
    document = design(node('html', 'x', {'html': '<p>{{ user.username }}</p>'}))
    document['assets'] = {'js': 'window.trusted = 1;'}
    return document


@override_settings(**TRUSTED)
class HotPathTests(DesignClient):
    def setUp(self):
        super().setUp()
        self.publisher = grant(User.objects.create_user('pub'),
                               'gtdesigns.publish_template', 'gtdesigns.publish_js')
        self.page = self.publish(trusted_design(), user=self.publisher)
        self.assertEqual(self.get('sample').status_code, 200)  # fills the caches

    def request(self, path):
        request = RequestFactory().get(path)
        request.user = self.user
        # What a middleware that resolves the Site leaves (no Site for the
        # host); without it the Site lookup by host adds one query.
        request.site = None
        return request

    def test_a_cached_page_takes_two_queries(self):
        request = self.request('/designs/sample')
        with mock.patch.object(engine, 'render',
                               return_value=HttpResponse('ok')) as render:
            # The page with its publisher (document deferred) and its
            # permissions; the trust and the resolution come from the caches.
            with self.assertNumQueries(2):
                response = views.design_page(request, 'sample')
        self.assertEqual(response.status_code, 200)
        resolved = render.call_args.args[0]
        self.assertTrue(resolved.allow_js)
        self.assertTrue(resolved.allow_templates)

    def test_an_endpoint_takes_two_queries_before_its_viewset(self):
        request = self.request('/gtapis/designs/%s/x/' % self.page.pk)
        with mock.patch.object(engine, 'node_endpoints',
                               return_value=None) as endpoints:
            with self.assertNumQueries(2):
                response = views.design_endpoint(request, self.page.pk, 'x')
        endpoints.assert_called_once()  # past the access check
        self.assertEqual(response.status_code, 404)

    def test_finding_the_site_by_host_takes_one_more_query(self):
        # Without a middleware that sets request.site, get_current_site looks
        # the Site up by the request's host: once per request.
        request = RequestFactory().get('/designs/sample')
        request.user = self.user
        with mock.patch.object(engine, 'render', return_value=HttpResponse('ok')):
            with self.assertNumQueries(3):
                response = views.design_page(request, 'sample')
        self.assertEqual(response.status_code, 200)

    def test_the_document_is_read_when_the_cache_misses(self):
        engine.clear_cache()
        content = self.get('sample').content.decode()
        self.assertIn('<p>ana</p>', content)
        self.assertIn('<script>window.trusted = 1;</script>', content)


@override_settings(**TRUSTED)
class TrustCacheTests(DesignClient):
    def setUp(self):
        super().setUp()
        self.publisher = grant(User.objects.create_user('pub'),
                               'gtdesigns.publish_template', 'gtdesigns.publish_js')
        self.page = self.publish(trusted_design(), user=self.publisher)

    def revoke_js(self):
        self.publisher.user_permissions.remove(Permission.objects.get(
            content_type__app_label='gtdesigns', codename='publish_js'))

    def trust(self):
        return engine.cached_page_trust(
            views.served_pages().get(pk=self.page.pk))

    def test_a_revoked_permission_counts_after_the_ttl(self):
        self.assertEqual(self.trust(), (True, True))
        self.revoke_js()
        self.assertEqual(self.trust(), (True, True), 'still within the TTL')
        later = engine.time.monotonic() + 61
        with mock.patch.object(engine.time, 'monotonic', return_value=later):
            self.assertEqual(self.trust(), (True, False))
        self.assertNotIn('window.trusted', self.get('sample').content.decode())

    def test_the_cached_trust_takes_no_query(self):
        self.trust()
        page = views.served_pages().get(pk=self.page.pk)
        with self.assertNumQueries(0):
            self.assertEqual(engine.cached_page_trust(page), (True, True))

    @override_settings(GT_DESIGNS_TRUST_TTL=0)
    def test_a_ttl_of_zero_checks_every_time(self):
        self.assertEqual(self.trust(), (True, True))
        self.revoke_js()
        self.assertEqual(self.trust(), (True, False))

    def test_saving_the_page_checks_again(self):
        self.assertEqual(self.trust(), (True, True))
        self.revoke_js()
        Page.objects.get(pk=self.page.pk).save()
        self.assertEqual(self.trust(), (True, False))

    def test_another_publisher_checks_again(self):
        self.assertEqual(self.trust(), (True, True))
        Page.objects.filter(pk=self.page.pk).update(updated_by=self.user)
        self.assertEqual(self.trust(), (False, False))

    def test_the_settings_are_part_of_the_key(self):
        self.assertEqual(self.trust(), (True, True))
        with self.settings(GT_DESIGNS_ALLOW_JS=False):
            self.assertEqual(self.trust(), (True, False))

    def test_an_unsaved_page_is_not_cached(self):
        page = Page(document=trusted_design(), updated_by=self.publisher)
        self.assertEqual(engine.cached_page_trust(page), (True, True))
        self.assertEqual(engine._trust_cache, {})

    @override_settings(GT_DESIGNS_CACHE_SIZE=1)
    def test_the_cache_is_bounded(self):
        other = self.publish(trusted_design(), path='other', user=self.publisher)
        self.trust()
        engine.cached_page_trust(views.served_pages().get(pk=other.pk))
        self.assertEqual(len(engine._trust_cache), 1)
