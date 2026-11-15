"""The Site rule across modules, with real ``django.contrib.sites`` Sites
resolved by host: data sources with ``site_field``, design pages by Site, the
task inbox as a data source, and Django's ``LoginView`` on a host without a
Site (``SITE_ID = 1`` in the demo)."""

import json
from datetime import timedelta

from django.contrib.auth.models import Permission, User
from django.contrib.sites.models import Site
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from djgentelella.datasources import query
from djgentelella.datasources.base import (
    ModelDataSource, get_datasource, register_datasource, unregister_datasource,
)
from djgentelella.designs import publishing
from djgentelella.flows.actions import ActionContext
from djgentelella.flows.models import Task
from djgentelella.flows.tasks import create_task
from djgentelella.models import GentelellaSettings
from djgentelella.tests.Designs_Test import DesignState, design, node

HOSTS = override_settings(ALLOWED_HOSTS=['*'])


class TwoSites:
    def setUp(self):
        super().setUp()
        # A rolled back test leaves Sites in this cache, by host and by pk.
        Site.objects.clear_cache()
        self.site_a = Site.objects.create(domain='a.example', name='A')
        self.site_b = Site.objects.create(domain='b.example', name='B')

    def request(self, host, user=None):
        request = RequestFactory().get('/', HTTP_HOST=host)
        request.user = user or User.objects.get_or_create(username='viewer')[0]
        return request


@HOSTS
class SiteFieldDataSourceTests(TwoSites, TestCase):
    """``ModelDataSource(site_field=...)`` over a real Site foreign key."""

    def setUp(self):
        super().setUp()
        for key, site in (('sites.global', None), ('sites.a', self.site_a),
                          ('sites.b', self.site_b)):
            GentelellaSettings.objects.create(key=key, value=key, site=site)
        self.source = ModelDataSource(
            GentelellaSettings, name='test.sites.settings', perms=[],
            fields=['key', 'site'], site_field='site',
            queryset=GentelellaSettings.objects.filter(key__startswith='sites.'))
        register_datasource(self.source)
        self.addCleanup(unregister_datasource, 'test.sites.settings')

    def keys(self, request):
        return sorted(row.key for row in query.apply_params(self.source, request, {}))

    def test_the_site_of_the_host_and_the_globals(self):
        self.assertEqual(self.keys(self.request('a.example')),
                         ['sites.a', 'sites.global'])
        self.assertEqual(self.keys(self.request('B.EXAMPLE:8000')),
                         ['sites.b', 'sites.global'])

    def test_a_host_without_a_site_sees_only_the_globals(self):
        # SITE_ID = 1 (example.com) is not a fallback.
        self.assertEqual(self.keys(self.request('localhost')), ['sites.global'])

    def test_a_site_set_by_a_middleware_wins_over_the_host(self):
        request = self.request('a.example')
        request.site = self.site_b
        self.assertEqual(self.keys(request), ['sites.b', 'sites.global'])

    def test_through_the_api(self):
        url = reverse('gtdatasource-rows', args=['test.sites.settings'])
        response = self.client.get(url, HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(sorted(row['key'] for row in body['data']),
                         ['sites.a', 'sites.global'])
        self.assertEqual(body['recordsTotal'], 2)


@HOSTS
class DesignPageBySiteTests(TwoSites, DesignState, TestCase):
    """A design page of the current Site wins over the global one."""

    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_user('ana', password='pw'))
        for markup, site in (('global page', None), ('page of A', self.site_a)):
            page, errors = publishing.publish(
                design(node('html', 'x', {'html': markup})), site=site,
                path='sites/home')
            self.assertEqual(errors, [])

    def get(self, host):
        return self.client.get(reverse('gt-design-page', args=['sites/home']),
                               HTTP_HOST=host)

    def test_the_site_wins(self):
        response = self.get('a.example')
        self.assertContains(response, 'page of A')
        self.assertNotContains(response, 'global page')

    def test_other_hosts_get_the_global_page(self):
        self.assertContains(self.get('b.example'), 'global page')
        # localhost has no Site: SITE_ID does not pin it to example.com.
        self.assertContains(self.get('localhost'), 'global page')

    def test_a_page_of_the_site_id_site_is_not_served_elsewhere(self):
        example = Site.objects.get(pk=1)
        publishing.publish(design(node('html', 'x', {'html': 'example only'})),
                           site=example, path='sites/only')
        url = reverse('gt-design-page', args=['sites/only'])
        self.assertEqual(self.client.get(url, HTTP_HOST='localhost').status_code, 404)
        self.assertContains(self.client.get(url, HTTP_HOST=example.domain),
                            'example only')


@HOSTS
class LoginViewWithoutASiteTests(TestCase):
    """``SITE_ID = 1`` keeps Django's views working on hosts with no Site."""

    def test_login_on_a_host_without_a_site(self):
        Site.objects.clear_cache()
        response = self.client.get(reverse('login'), HTTP_HOST='nosite.example')
        self.assertEqual(response.status_code, 200)


class TaskDataSourceTests(TestCase):
    """``flows.tasks``: the inbox as a data source, with facets."""

    def setUp(self):
        self.ana = User.objects.create_user('ana', password='pw')
        self.bob = User.objects.create_user('bob', password='pw')
        owner = User.objects.create_user('owner')
        create_task(obj=owner, title='Approve A', potential_owners=[self.ana],
                    priority=1, due=timezone.now() + timedelta(days=1))
        create_task(obj=owner, title='Approve B', potential_owners=[self.ana],
                    priority=3)
        create_task(obj=owner, title='For Bob', potential_owners=[self.bob])
        self.url = 'gtdatasource-rows'

    def rows(self, user):
        if user is not None:
            self.client.force_login(user)
        return self.client.get(reverse(self.url, args=['flows.tasks']))

    def test_registered(self):
        source = get_datasource('flows.tasks')
        self.assertEqual(source.model, Task)
        self.assertIn('state', source.column_map(None))

    def test_rows_are_the_inbox_of_the_user(self):
        body = self.rows(self.ana).json()
        self.assertEqual(sorted(row['title'] for row in body['data']),
                         ['Approve A', 'Approve B'])
        self.assertEqual(body['recordsTotal'], 2)

    def test_anonymous_is_403(self):
        self.assertEqual(self.rows(None).status_code, 403)

    def test_facets(self):
        self.client.force_login(self.ana)
        response = self.client.get(
            reverse('gtdatasource-facets', args=['flows.tasks']),
            {'columns': 'priority,state'})
        self.assertEqual(response.status_code, 200)
        body = json.dumps(response.json())
        self.assertIn('"count": 2', body)

    def test_with_view_task_every_task(self):
        self.ana.user_permissions.add(Permission.objects.get(
            codename='view_task', content_type__app_label='gtflows'))
        body = self.rows(User.objects.get(pk=self.ana.pk)).json()
        self.assertEqual(body['recordsTotal'], 3)


@HOSTS
class ActionContextSiteTests(TwoSites, TestCase):
    def test_the_site_of_the_request(self):
        self.assertEqual(ActionContext(request=self.request('a.example')).site,
                         self.site_a)
        self.assertIsNone(ActionContext(request=self.request('localhost')).site)
