"""The proposals of wave 12 that W34 adds as API: a restricted data source,
the hooks of the data source views, the query timeout and the export row
cap, the OpenAPI description of the design viewsets, type hints of the
method fields, and push (scope per Site, queue, pushsubscriptionchange,
unsubscribing on logout)."""

import inspect
import json
import sys
import types
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from demoapp.models import Product, ProductCategory
from djgentelella.datasources import api
from djgentelella.datasources.base import (
    DataSourceUnavailable, ModelDataSource, RestrictedDataSource, query_timeout,
    register_datasource, restricted, unregister_datasource,
)
from djgentelella.designs.openapi import openapi_parameters
from djgentelella.designs.regions import CalendarViewSet, MapViewSet
from djgentelella.designs.source_tables import SourceTableViewSet
from djgentelella.models import Notification, PushSubscription
from djgentelella.pwa import push
from djgentelella.pwa.backends import LocmemPushBackend
from djgentelella.pwa.manifest import build_manifest, worker_config
from djgentelella.serializers.selects import GTS2SerializerBase
from djgentelella.tests.PwaPush_Test import AUTH, FCM, P256DH, subscription_json
from djgentelella.designs import engine
from djgentelella.designs.models import Page
from djgentelella.tests.Designs_Test import design, node
from djgentelella.tests.DesignsData_Test import DataDesignTestCase, load
from djgentelella.utils import set_settings

LOCMEM = 'djgentelella.pwa.backends.LocmemPushBackend'
FAST = ['django.contrib.auth.hashers.MD5PasswordHasher']
NEW_FCM = 'https://fcm.googleapis.com/fcm/send/renewed'
NEW_AUTH = 'AAAAAAAAAAAAAAAAAAAAAA'

PRODUCTS = ModelDataSource(Product, name='w34.products', perms=[],
                           fields=['name', 'price', 'status'])


def slow_sql():
    if connection.vendor == 'postgresql':
        return 'SELECT pg_sleep(3)'
    return ('WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c '
            'WHERE x < 100000000) SELECT count(*) FROM c')


class SlowSource(ModelDataSource):
    """Reading it runs a query that takes seconds."""

    def get_queryset(self, request):
        with connection.cursor() as cursor:
            cursor.execute(slow_sql())
        return super().get_queryset(request)


@override_settings(PASSWORD_HASHERS=FAST, LANGUAGE_CODE='en')
class DataSourceProposalTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        register_datasource(PRODUCTS)

    @classmethod
    def tearDownClass(cls):
        unregister_datasource('w34.products')
        super().tearDownClass()

    def setUp(self):
        food = ProductCategory.objects.create(name='Food')
        for index, name in enumerate(['Apple', 'Bread', 'Cheese']):
            Product.objects.create(name=name, price=Decimal(index + 1),
                                   status='active', category=food,
                                   available_since=timezone.localdate())
        self.user = get_user_model().objects.create_user('ds', password='x')
        self.factory = APIRequestFactory()

    def call(self, view_class, params=None, name='w34.products', **query):
        if params is not None:
            query['params'] = json.dumps(params)
        request = self.factory.get('/', query)
        force_authenticate(request, self.user)
        return view_class.as_view()(request, name=name)

    def test_a_restricted_source(self):
        only = restricted(PRODUCTS, ['name'], label='Names')
        self.assertIsInstance(only, RestrictedDataSource)
        self.assertEqual([column.name for column in only.columns(None)], ['name'])
        self.assertEqual(only.get_label(), 'Names')
        self.assertIs(only.project_model, Product)
        self.assertEqual(PRODUCTS.with_columns(['price']).allowed, ['price'])

        class NamesView(api.DataSourceRowsView):
            def get_source(self, name):
                return restricted(super().get_source(name), ['name'])

        response = self.call(NamesView, length=10)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted(row['name'] for row in response.data['data']),
                         ['Apple', 'Bread', 'Cheese'])
        self.assertNotIn('price', response.data['data'][0])
        # A column it does not allow cannot be filtered on.
        response = self.call(NamesView, {'filters': [
            {'column': 'price', 'op': 'gt', 'value': 1}]})
        self.assertEqual(response.status_code, 400)

    def test_restricted_perms_add_to_the_source(self):
        only = restricted(PRODUCTS, ['name'], perms=['demoapp.view_product'])
        request = self.factory.get('/')
        request.user = self.user
        self.assertFalse(only.has_permission(request))

    def test_the_export_view_may_skip_the_handler(self):
        handler = mock.Mock(return_value=None)

        class OwnExport(api.DataSourceExportView):
            use_export_handler = False

        with override_settings(GT_DATASOURCE_EXPORT_HANDLER=handler):
            response = self.call(OwnExport, fmt='csv')
            self.assertEqual(response.status_code, 200)
            handler.assert_not_called()
            self.call(api.DataSourceExportView, fmt='csv')
            handler.assert_called_once()

    @override_settings(GT_DATASOURCE_EXPORT_REFUSE_OVER_LIMIT=True,
                       GT_DATASOURCE_EXPORT_MAX_ROWS=2)
    def test_an_export_over_the_limit_is_refused(self):
        response = self.call(api.DataSourceExportView, fmt='csv')
        self.assertEqual(response.status_code, 400)
        self.assertIn('more than 2 rows', json.dumps(response.data))
        response = self.call(api.DataSourceExportView, {'filters': [
            {'column': 'name', 'op': 'eq', 'value': 'Apple'}]}, fmt='csv')
        self.assertEqual(response.status_code, 200)

    @override_settings(GT_DATASOURCE_EXPORT_MAX_ROWS=2)
    def test_without_the_setting_the_export_is_cut(self):
        response = self.call(api.DataSourceExportView, fmt='json')
        self.assertEqual(response.status_code, 200)

    def test_the_query_timeout(self):
        with self.assertRaises(DataSourceUnavailable) as raised:
            with query_timeout(0.05):
                with connection.cursor() as cursor:
                    cursor.execute(slow_sql())
        self.assertEqual(raised.exception.status_code, 504)
        # Back to normal after the block.
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_the_api_answers_504_past_the_timeout(self):
        register_datasource(SlowSource(Product, name='w34.slow', perms=[],
                                       fields=['name']))
        try:
            with override_settings(GT_DATASOURCE_QUERY_TIMEOUT=0.05):
                response = self.call(api.DataSourceRowsView, name='w34.slow')
            self.assertEqual(response.status_code, 504)

            class NoLimit(api.DataSourceInfoView):
                query_timeout = 0

            with override_settings(GT_DATASOURCE_QUERY_TIMEOUT=0.05):
                self.assertEqual(self.call(NoLimit, name='w34.slow').status_code,
                                 200)
        finally:
            unregister_datasource('w34.slow')


class OpenApiTests(TestCase):
    def names(self, viewset, action='list'):
        return [item['name'] for item in openapi_parameters(viewset, action)]

    def test_what_each_viewset_reads(self):
        self.assertEqual(self.names(CalendarViewSet), ['params', 'search', 'start',
                                                       'end'])
        self.assertEqual(self.names(MapViewSet), ['params', 'search', 'bbox'])
        self.assertEqual(self.names(SourceTableViewSet),
                         ['gtfilters', 'search', 'ordering', 'offset', 'limit',
                          'draw'])
        self.assertEqual(self.names(CalendarViewSet, 'create'), [])
        item = openapi_parameters(CalendarViewSet, 'list')[0]
        self.assertEqual((item['in'], item['schema']), ('query', {'type': 'string'}))

    def test_the_method_fields_have_type_hints(self):
        hints = {name: inspect.signature(getattr(GTS2SerializerBase, name))
                 .return_annotation
                 for name in ('get_id', 'get_text', 'get_selected', 'get_disabled')}
        self.assertEqual(hints['get_text'], str)
        self.assertEqual(hints['get_selected'], bool)
        self.assertEqual(hints['get_id'], int | str)


@override_settings(GT_PUSH_BACKEND=LOCMEM, PASSWORD_HASHERS=FAST,
                   ALLOWED_HOSTS=['*'], LANGUAGE_CODE='en')
class PushProposalTests(TestCase):
    def setUp(self):
        LocmemPushBackend.outbox = []
        self.user = get_user_model().objects.create_user('push34', password='x')
        self.client.force_login(self.user)

    def test_scope_per_site(self):
        site = Site.objects.create(domain='app1.example', name='App 1')
        set_settings('pwa_scope', '/app1/', site=site)
        request = self.client.get('/', HTTP_HOST='app1.example').wsgi_request
        manifest = build_manifest(request)
        self.assertEqual((manifest['scope'], manifest['start_url']),
                         ('/app1/', '/app1/'))
        self.assertEqual(worker_config(request)['scope'], '/app1/')
        response = self.client.get(reverse('gt_pwa_service_worker'),
                                   HTTP_HOST='app1.example')
        self.assertEqual(response['Service-Worker-Allowed'], '/app1/')
        # Anything else is not a scope: the setting.
        set_settings('pwa_scope', 'app1', site=site)
        request = self.client.get('/', HTTP_HOST='app1.example').wsgi_request
        self.assertEqual(build_manifest(request)['scope'], '/')

    def test_pushsubscriptionchange(self):
        PushSubscription.objects.create(user=self.user, endpoint=FCM, p256dh=P256DH,
                                        auth=AUTH)
        client = Client(enforce_csrf_checks=True)  # no session, no token
        url = reverse('gt_push_resubscribe')
        body = {'old': subscription_json(), 'new': subscription_json(
            NEW_FCM, auth=NEW_AUTH)}
        response = client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        subscription = PushSubscription.objects.get()
        self.assertEqual((subscription.endpoint, subscription.auth, subscription.user),
                         (NEW_FCM, NEW_AUTH, self.user))
        # The old one is gone: it proves nothing any more.
        response = client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        # The right endpoint with a wrong secret proves nothing either.
        body = {'old': subscription_json(NEW_FCM, auth='x' * 22),
                'new': subscription_json(FCM)}
        response = client.post(url, json.dumps(body), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        response = client.post(url, json.dumps({'old': 'x'}),
                               content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('resubscribe_url', worker_config(
            self.client.get('/').wsgi_request))

    def subscribe(self):
        response = self.client.post(reverse('gt_push_subscribe'),
                                    json.dumps(subscription_json()),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)

    def test_logout_keeps_the_subscription_by_default(self):
        self.subscribe()
        self.client.post(reverse('logout'))
        self.assertTrue(PushSubscription.objects.exists())

    @override_settings(GT_PUSH_UNSUBSCRIBE_ON_LOGOUT=True)
    def test_logout_forgets_this_browsers_subscription(self):
        PushSubscription.objects.create(user=self.user, endpoint=NEW_FCM,
                                        p256dh=P256DH, auth=NEW_AUTH)
        self.subscribe()
        self.client.post(reverse('logout'))
        # Only the one this session subscribed.
        self.assertEqual(list(PushSubscription.objects.values_list(
            'endpoint', flat=True)), [NEW_FCM])

    def notify(self):
        PushSubscription.objects.create(user=self.user, endpoint=FCM, p256dh=P256DH,
                                        auth=AUTH)
        with self.captureOnCommitCallbacks(execute=True):
            Notification.objects.create(user=self.user, description='Hello',
                                        message_type='info')

    def test_sync_by_default(self):
        self.notify()
        self.assertEqual(len(LocmemPushBackend.outbox), 1)

    @override_settings(GT_PUSH_QUEUE='celery')
    def test_queued_with_celery(self):
        task = mock.Mock()
        tasks = types.ModuleType('djgentelella.pwa.tasks')
        tasks.push_notification_task = task
        with mock.patch.dict(sys.modules, {'djgentelella.pwa.tasks': tasks}):
            self.notify()
        task.delay.assert_called_once_with(Notification.objects.get().pk)
        self.assertEqual(LocmemPushBackend.outbox, [])

    @override_settings(GT_PUSH_QUEUE='auto', CELERY_BROKER_URL='redis://x')
    def test_auto_without_celery_sends_it(self):
        with mock.patch.dict(sys.modules, {'celery': None}):
            self.assertFalse(push.queued())
            self.notify()
        self.assertEqual(len(LocmemPushBackend.outbox), 1)


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST)
class E15ProposalTests(DataDesignTestCase):
    """What E15 (master-detail and the Advisor of the editor) asked of W."""

    def category_page(self, **parent):
        document = load('category_products')
        document['meta']['parent'].update(parent)
        return document

    def test_a_page_may_link_its_rows_to_itself(self):
        # A master-detail page whose rows open the page about each row: it
        # does not exist yet the first time it is published.
        document = design(
            node('object_management', 'categories', {
                'model': 'demoapp.ProductCategory', 'form': 'category_form',
                'list_fields': ['name'],
                'row_links': [{'url_name': 'page:master/', 'title': 'Open'}]}),
            forms={'category_form': {'model': 'demoapp.ProductCategory',
                                     'fields': ['name']}},
            url='master/', url_name='master',
            parent={'model': 'demoapp.ProductCategory'})
        self.assertFalse(Page.objects.filter(path='master').exists())
        page = self.publish(document, path='master')
        build = engine.resolve_page(page)[0].nodes['categories'].build
        self.assertEqual(build.row_links[0].page, 'master')
        # By url_name too; another page that does not exist is still refused.
        links = document['root']['children'][0]['children'][0]['children'][0][
            'props']['row_links']
        links[0]['url_name'] = 'master'
        Page.objects.all().delete()
        self.publish(document, path='master')
        links[0]['url_name'] = 'page:elsewhere/'
        self.assertTrue(self.errors(document))

    def test_choose_the_parent(self):
        self.grant('demoapp.view_product', 'demoapp.view_productcategory')
        url = reverse('gt-design-page', args=['category-products'])
        self.publish(load('category_products'))
        self.assertEqual(self.client.get(url).status_code, 404)
        self.publish(self.category_page(choose=True))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/designs/category-products/%d/"'
                            % self.food.pk)
        self.assertContains(response, 'Tools')
        # The page of one object is served as before.
        self.assertEqual(self.client.get(reverse('gt-design-page', args=[
            'category-products/%d' % self.food.pk])).status_code, 200)

    def test_choosing_needs_the_view_permission_of_the_model(self):
        self.grant('demoapp.view_product')
        self.publish(self.category_page(choose=True))
        url = reverse('gt-design-page', args=['category-products'])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_site_rows_is_public(self):
        from djgentelella.designs import factories  # noqa: PLC0415 test
        self.assertIn('site_rows', factories.__all__)


class FlowCheckTests(TestCase):
    def flow(self, **attrs):
        from djgentelella.flows import Flow, Transition  # noqa: PLC0415 app
        defaults = {
            'model': Product, 'name': 'tests.w34.check',
            'states': [('new', 'New'), ('review', 'Review'), ('stuck', 'Stuck'),
                       ('orphan', 'Orphan'), ('done', 'Done')],
            'initial': 'new', 'final_states': ['done'],
            'transitions': [Transition('send', 'new', 'review'),
                            Transition('approve', 'review', 'done'),
                            Transition('park', 'review', 'stuck'),
                            Transition('loop', 'stuck', 'stuck'),
                            Transition('revive', 'orphan', 'done')]}
        defaults.update(attrs)
        return Flow(**defaults)

    def test_dead_ends_and_unreachable_states(self):
        flow = self.flow()
        self.assertEqual(flow.unreachable_states(), ['orphan'])
        self.assertEqual(flow.dead_ends(), ['stuck'])

    def test_a_sound_flow(self):
        from djgentelella.flows import Transition  # noqa: PLC0415 app
        flow = self.flow(states=[('new', 'New'), ('done', 'Done')],
                         transitions=[Transition('go', 'new', 'done')])
        self.assertEqual((flow.unreachable_states(), flow.dead_ends()), ([], []))
