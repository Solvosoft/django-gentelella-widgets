"""djgentelella.sites.site_request: a request of another Site."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.test import TestCase, override_settings

from djgentelella import authorization as authorization_module
from djgentelella.authorization import (
    ConditionRequest,
    authorization,
    check_authorization,
    evaluate_condition,
    set_flag,
)
from djgentelella.datasources.export import (
    available_formats,
    register_exporter_resolver,
    unregister_exporter_resolver,
)
from djgentelella.sites import get_current_site, resolve_site, site_request


def site_layouts(request):
    """A resolver like djodo's layouts: a format per layout of the Site of
    the request, only for a signed-in user."""
    site = get_current_site(request)
    if site is None or not request.user.is_authenticated:
        return {}
    return {'pdf:%s' % site.name: lambda source, request, params: None}


class SiteRequestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ventas = Site.objects.create(domain='ventas.example.com', name='ventas')
        cls.rrhh = Site.objects.create(domain='rrhh.example.com', name='rrhh')
        cls.ana = get_user_model().objects.create_user('ana', password='x')

    def test_a_get_request_of_the_site(self):
        request = site_request(self.ventas, user=self.ana)
        self.assertIsInstance(request, HttpRequest)
        self.assertIs(request.site, self.ventas)
        self.assertEqual(get_current_site(request), self.ventas)
        self.assertEqual(request.user, self.ana)
        self.assertEqual(request.method, 'GET')
        self.assertEqual(request.path, '/')
        self.assertEqual(dict(request.GET), {})
        self.assertEqual(dict(request.POST), {})
        self.assertEqual(request.COOKIES, {})
        self.assertTrue(request.is_site_request)

    @override_settings(ALLOWED_HOSTS=['ventas.example.com'])
    def test_the_host_is_the_domain_of_the_site(self):
        request = site_request(self.ventas)
        self.assertEqual(request.get_host(), 'ventas.example.com')
        self.assertEqual(request.build_absolute_uri('/x/'),
                         'http://ventas.example.com/x/')

    def test_an_id_and_the_global_scope(self):
        self.assertEqual(site_request(self.rrhh.pk).site, self.rrhh)
        self.assertEqual(site_request(str(self.rrhh.pk)).site, self.rrhh)
        request = site_request(None)
        self.assertIsNone(request.site)
        self.assertIsNone(get_current_site(request))
        self.assertEqual(request.get_host(), 'localhost')

    def test_an_id_of_no_site_is_not_the_global_scope(self):
        missing = Site.objects.order_by('-pk').first().pk + 100
        with self.assertRaisesMessage(ValueError, 'There is no Site with id'):
            site_request(missing)
        with self.assertRaises(ValueError):
            ConditionRequest(site=missing)
        with self.assertRaises(TypeError):
            site_request(object())

    def test_without_a_user_it_is_anonymous(self):
        request = site_request(self.ventas)
        self.assertIsInstance(request.user, AnonymousUser)
        self.assertFalse(request.user.is_authenticated)

    def test_resolve_site(self):
        self.assertIs(resolve_site(self.ventas), self.ventas)
        self.assertEqual(resolve_site(self.ventas.pk), self.ventas)
        self.assertIsNone(resolve_site(None))

    def test_the_formats_of_another_site(self):
        register_exporter_resolver(site_layouts)
        self.addCleanup(unregister_exporter_resolver, site_layouts)
        ventas = available_formats(site_request(self.ventas, self.ana))
        rrhh = available_formats(site_request(self.rrhh, self.ana))
        self.assertIn('pdf:ventas', ventas)
        self.assertNotIn('pdf:rrhh', ventas)
        self.assertIn('pdf:rrhh', rrhh)
        self.assertEqual(ventas[:4], ['csv', 'xlsx', 'json', 'pdf'])
        # The user counts: the resolver offers nothing to an anonymous one.
        self.assertNotIn('pdf:ventas', available_formats(site_request(self.ventas)))
        # Global: the built-in formats only.
        self.assertEqual(available_formats(site_request(None, self.ana)),
                         available_formats(site_request(None)))

    def test_conditions_and_flags_of_another_site(self):
        set_flag('w13_beta', True, site=self.ventas)
        condition = {'flag': 'w13_beta'}
        self.assertTrue(evaluate_condition(condition, site_request(self.ventas)))
        self.assertFalse(evaluate_condition(condition, site_request(self.rrhh)))
        self.assertFalse(evaluate_condition(condition, site_request(None)))
        # The same answer as the lighter ConditionRequest.
        self.assertTrue(evaluate_condition(condition,
                                           ConditionRequest(site=self.ventas)))

    def test_authorizations_get_the_user(self):
        @authorization('tests.w13.is_ana')
        def is_ana(request, obj=None):
            return getattr(request.user, 'username', None) == 'ana'
        self.addCleanup(authorization_module._registry.pop, 'tests.w13.is_ana', None)

        self.assertTrue(check_authorization('tests.w13.is_ana',
                                            site_request(self.ventas, self.ana)))
        self.assertFalse(check_authorization('tests.w13.is_ana',
                                             site_request(self.ventas)))
