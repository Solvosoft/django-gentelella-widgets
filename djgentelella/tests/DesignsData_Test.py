"""The components with data of djgentelella.designs: tables, inline
tables, charts, stats, the classic CRUD, facets and notifications."""

import copy
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from demoapp.models import Product, ProductCategory, ProductTag
from djgentelella.async_notification.models import EmailNotification, EmailTemplate
from djgentelella.designs import engine, exposure, factories, publishing, registry
from djgentelella.designs.builds import ObjectManagementBuild
from djgentelella.designs.models import Page
from djgentelella.models import Notification
from djgentelella.tests.Designs_Test import DesignState, design, node

DEMO_DESIGNS = (Path(__file__).resolve().parents[2] / 'demo' / 'demoapp'
                / 'gtdesign')


def load(name):
    with open(DEMO_DESIGNS / ('%s.json' % name)) as stream:
        return json.load(stream)


def grant(user, *codenames):
    for codename in codenames:
        app_label, name = codename.split('.')
        user.user_permissions.add(Permission.objects.get(
            content_type__app_label=app_label, codename=name))
    return User.objects.get(pk=user.pk)


def product_form(*fields):
    return {'product_form': {'model': 'demoapp.Product',
                             'fields': list(fields or ('name', 'price', 'status',
                                                       'category'))}}


def table(id_='products', **props):
    return node('object_management', id_, {'model': 'demoapp.Product',
                                           'form': 'product_form', **props})


ALL_PRODUCT_PERMS = ['demoapp.%s_product' % action
                     for action in ('view', 'add', 'change', 'delete')]


class DataDesignTestCase(DesignState, TestCase):
    """Some catalogue rows, a signed-in user and helpers to publish."""

    def setUp(self):
        super().setUp()
        factories.clear_cache()
        # Loaded now: loading imports the gtdesigns modules, which expose
        # their models again over what a test withdrew.
        registry.get_components()
        self.user = User.objects.create_user('ana', password='pw',
                                             email='ana@example.com')
        self.client.force_login(self.user)
        self.food = ProductCategory.objects.create(name='Food')
        self.tools = ProductCategory.objects.create(name='Tools')
        self.red = ProductTag.objects.create(name='red')
        self.blue = ProductTag.objects.create(name='blue')
        today = timezone.localdate()
        self.apple = Product.objects.create(
            name='Apple', price=Decimal('2.00'), status='active', category=self.food,
            available_since=today)
        self.bread = Product.objects.create(
            name='Bread', price=Decimal('4.00'), status='draft', category=self.food,
            available_since=today)
        self.hammer = Product.objects.create(
            name='Hammer', price=Decimal('30.00'), status='active',
            category=self.tools,
            available_since=(today.replace(day=1) - timedelta(days=1)))
        self.apple.tags.add(self.red)
        self.hammer.tags.add(self.red, self.blue)

    def tearDown(self):
        factories.clear_cache()
        super().tearDown()

    def publish(self, document, path=None, **kwargs):
        page, errors = publishing.publish(document, path=path, **kwargs)
        self.assertEqual([str(error) for error in errors], [])
        return page

    def errors(self, document, **kwargs):
        _resolved, errors = engine.resolve(document, **kwargs)
        return [str(error) for error in errors]

    def api(self, page, node_id, rest=''):
        return reverse('gt-design-endpoint', kwargs={
            'page_id': page.pk, 'node_id': node_id, 'rest': rest})

    def grant(self, *perms):
        self.user = grant(self.user, *perms)
        self.client.force_login(self.user)

    def post_json(self, url, data, method='post'):
        return getattr(self.client, method)(url, json.dumps(data),
                                            content_type='application/json')


class ResolveTests(DataDesignTestCase):
    """What a design with data may say: only exposed models and fields."""

    def test_the_demo_designs_resolve(self):
        self.publish(load('category_products'))
        for name in ('product_admin', 'sales_dashboard'):
            self.assertEqual(self.errors(load(name)), [], name)

    def test_an_unexposed_model_is_refused_by_every_component(self):
        exposure.unexpose(Product)
        documents = [
            design(table(), forms=product_form()),
            design(node('chart', 'c', {'model': 'demoapp.Product',
                                       'group_by': 'status'})),
            design(node('stat', 's', {'model': 'demoapp.Product'})),
            design(node('crud_classic', 'k', {'model': 'demoapp.Product'})),
        ]
        for document in documents:
            errors = self.errors(document)
            self.assertTrue(any('not exposed' in error for error in errors), errors)

    def test_only_the_fields_the_exposure_allows(self):
        exposure.expose(Product, exclude=('price',))
        errors = self.errors(design(table(list_fields=['name', 'price']),
                                    forms=product_form('name')))
        self.assertIn("$.root.children[0].children[0].children[0].props.list_fields:"
                      " demoapp.Product has no field 'price' a design may use", errors)
        errors = self.errors(design(node('chart', 'c', {
            'model': 'demoapp.Product', 'group_by': 'status', 'aggregate': 'sum',
            'value_field': 'price'})))
        self.assertTrue(any('numeric value_field' in error for error in errors))

    def test_a_relation_column_needs_its_target_exposed(self):
        exposure.unexpose(ProductCategory)
        errors = self.errors(design(table(list_fields=['name', 'category']),
                                    forms=product_form('name')))
        self.assertTrue(any("'demoapp.ProductCategory' is not exposed" in error
                            for error in errors), errors)

    def test_the_editor_rules(self):
        cases = [
            (table(search_fields=['price']), 'is not a text field'),
            (table(perms={'create': []}), 'cannot be empty'),
            (table(perms={'create': ['demoapp.nope_product']}),
             "unknown permission 'demoapp.nope_product'"),
            (table(ordering=['-nothing']), "unknown field '-nothing'"),
            (table(row_links=[{'url_name': 'no-such-url', 'title': 'X'}]),
             'is neither a URL name'),
            (node('chart', 'c', {'model': 'demoapp.Product', 'group_by': 'tags'}),
             "'tags' cannot be grouped by"),
            (node('chart', 'c', {'model': 'demoapp.Product', 'group_by': 'status',
                                 'datasource': 'demoapp.person'}),
             'not both'),
            (node('facets', 'f', {'target': 'nothing', 'columns': ['status']}),
             'is not the id of a table'),
        ]
        for item, message in cases:
            errors = self.errors(design(item, table('other'), forms=product_form()))
            self.assertTrue(any(message in error for error in errors),
                            (message, errors))

    def test_a_form_of_another_model(self):
        errors = self.errors(design(table(form='category_form'), forms={
            'category_form': {'model': 'demoapp.ProductCategory'}}))
        self.assertTrue(any("form 'category_form' is for demoapp.ProductCategory"
                            in error for error in errors), errors)

    def test_inline_tables_need_a_parent(self):
        inline = node('inline_object_management', 'products', {
            'model': 'demoapp.Product', 'form': 'product_form',
            'parent_field': 'category'})
        errors = self.errors(design(inline, forms=product_form('name')))
        self.assertTrue(any('needs a page with a parent' in error for error in errors))
        errors = self.errors(design(
            dict(inline, props=dict(inline['props'], parent_field='name')),
            forms=product_form('name'), parent={'model': 'demoapp.ProductCategory'}))
        self.assertTrue(any("'name' is not a foreign key" in error for error in errors))
        errors = self.errors(design(inline, forms=product_form('name', 'category'),
                                    parent={'model': 'demoapp.ProductCategory'}))
        self.assertTrue(any('the parent comes from the URL' in error
                            for error in errors))

    def test_notifications_are_checked(self):
        errors = self.errors(design(table(notify=[
            {'on': 'create', 'kind': 'notice', 'message': 'x', 'to': ['field:name']},
            {'on': 'create', 'kind': 'email', 'to': ['actor']},
            {'on': 'update', 'kind': 'notice', 'to': ['actor'],
             'message': '{% load static %}{{ object.name }}'},
            {'on': 'update', 'kind': 'notice', 'to': ['field:nothing'],
             'message': 'x'},
        ]), forms=product_form()))
        self.assertTrue(any("'field:name' is not a user" in e for e in errors))
        self.assertTrue(any('an email needs code, subject, message' in e
                            for e in errors))
        self.assertTrue(any('template tags' in e for e in errors))
        self.assertTrue(any("has no field 'nothing'" in e for e in errors))

    def test_template_tags_with_a_trusted_publisher(self):
        document = design(table(notify=[
            {'on': 'update', 'kind': 'notice', 'to': ['actor'],
             'message': '{% if object.name %}{{ object.name }}{% endif %}'}]),
            forms=product_form())
        self.assertEqual(self.errors(document, allow_templates=True), [])


class ObjectManagementTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.page = self.publish(design(table(
            list_fields=['name', 'price', 'status', 'category', 'tags'],
            search_fields=['name']), forms=product_form()), path='products')
        self.url = self.api(self.page, 'products')

    def test_the_page_renders_the_table_and_its_modals(self):
        self.grant(*ALL_PRODUCT_PERMS)
        response = self.client.get(reverse('gt-design-page', args=['products']))
        content = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="products_table"', content)
        for modal in ('create', 'update', 'detail', 'delete'):
            self.assertIn('id="products_%s_modal"' % modal, content)
        self.assertIn('id="products_gtconfig"', content)
        self.assertIn('gentelella/js/designs/data_components.js', content)
        config = json.loads(content.split('id="products_gtconfig" type="application/'
                                          'json">')[1].split('</script>')[0])
        self.assertEqual(config['urls']['list_url'], self.url)
        self.assertEqual(config['urls']['detail_url'], self.url + '0/')
        self.assertEqual([column['name'] for column in config['columns']],
                         ['name', 'price', 'status', 'category', 'tags'])

    def test_the_modals_follow_the_permissions(self):
        self.grant('demoapp.view_product')
        content = self.client.get(reverse('gt-design-page', args=['products'])
                                  ).content.decode()
        self.assertIn('id="products_detail_modal"', content)
        self.assertNotIn('id="products_create_modal"', content)
        self.assertNotIn('id="products_delete_modal"', content)

    def test_list_create_update_detail_delete(self):
        self.grant(*ALL_PRODUCT_PERMS)
        response = self.client.get(self.url, {'draw': 3, 'limit': 10, 'offset': 0})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual((data['draw'], data['recordsTotal'], data['recordsFiltered']),
                         (3, 3, 3))
        row = [item for item in data['data'] if item['name'] == 'Hammer'][0]
        self.assertEqual(row['category']['text'], 'Tools')
        self.assertEqual(sorted(tag['text'] for tag in row['tags']), ['blue', 'red'])
        self.assertEqual(row['actions'], {'destroy': True, 'update': True,
                                          'detail': True})

        response = self.post_json(self.url, {'name': 'Saw', 'price': '12.50',
                                             'status': 'active',
                                             'category': self.tools.pk})
        self.assertEqual(response.status_code, 201, response.content)
        saw = Product.objects.get(name='Saw')
        self.assertEqual(saw.category, self.tools)

        detail = self.url + '%d/' % saw.pk
        response = self.post_json(detail, {'name': 'Big saw', 'price': '13.00',
                                           'status': 'retired',
                                           'category': self.food.pk}, method='put')
        self.assertEqual(response.status_code, 200, response.content)
        saw.refresh_from_db()
        self.assertEqual((saw.name, saw.status), ('Big saw', 'retired'))

        data = self.client.get(detail).json()
        self.assertEqual(data['status_display'], 'Retired')
        self.assertEqual(data['category_display'], 'Food')
        values = self.client.get(detail + 'get_values_for_update/').json()
        self.assertEqual(values['category']['id'], self.food.pk)
        template = self.client.get(self.url + 'detail_template/').json()
        self.assertIn('<% it.status_display %>', template['template'])
        self.assertEqual(template['title'], '<% it.name %>')

        self.assertEqual(self.client.delete(detail).status_code, 204)
        self.assertFalse(Product.objects.filter(pk=saw.pk).exists())

    def test_search_and_filters(self):
        self.grant('demoapp.view_product')

        def names(params):
            return sorted(row['name'] for row in
                          self.client.get(self.url, params).json()['data'])
        self.assertEqual(names({'search': 'ham'}), ['Hammer'])
        self.assertEqual(names({'status': 'active'}), ['Apple', 'Hammer'])
        self.assertEqual(names({'name__icontains': 'br'}), ['Bread'])
        self.assertEqual(names({'category': self.tools.pk}), ['Hammer'])
        self.assertEqual(names({'tags': '%d' % self.blue.pk}), ['Hammer'])
        self.assertEqual(names({'ordering': '-price'}), ['Apple', 'Bread', 'Hammer'])
        self.assertEqual(names({'gtfilters': json.dumps([
            {'column': 'category', 'op': 'in', 'value': [self.food.pk]},
            {'column': 'price', 'op': 'gt', 'value': 3}])}), ['Bread'])

    def test_bad_filters_are_400(self):
        self.grant('demoapp.view_product')
        for value in ('not json', '{"a": 1}', '[1]',
                      json.dumps([{'column': 'secret', 'op': 'eq', 'value': 1}]),
                      json.dumps([{'column': 'price', 'op': 'eq', 'value': 'x'}])):
            response = self.client.get(self.url, {'gtfilters': value})
            self.assertEqual(response.status_code, 400, value)

    def test_a_body_that_is_not_an_object_is_400(self):
        self.grant(*ALL_PRODUCT_PERMS)
        for body in ('[1, 2]', '"text"', 'not json'):
            response = self.client.post(self.url, body, content_type='application/json')
            self.assertEqual(response.status_code, 400, body)

    def test_permissions_per_action(self):
        self.grant('demoapp.view_product')
        detail = self.url + '%d/' % self.apple.pk
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.post_json(self.url, {'name': 'X', 'price': '1'}
                                        ).status_code, 403)
        self.assertEqual(self.post_json(detail, {'name': 'X', 'price': '1'},
                                        method='put').status_code, 403)
        self.assertEqual(self.client.get(detail + 'get_values_for_update/'
                                         ).status_code, 403)
        self.assertEqual(self.client.delete(detail).status_code, 403)
        row = self.client.get(self.url).json()['data'][0]
        self.assertEqual(row['actions'], {'destroy': False, 'update': False,
                                          'detail': True})

    def test_without_view_permission_the_list_is_403(self):
        # The page itself asks for nothing; the table asks for view_product.
        self.assertEqual(self.client.get(self.url).status_code, 403)
        content = self.client.get(reverse('gt-design-page', args=['products'])
                                  ).content.decode()
        self.assertNotIn('products_gtconfig', content)
        self.assertIn('You do not have permission to see this.', content)

    def test_custom_permissions(self):
        page = self.publish(design(table(perms={'create': ['demoapp.view_product',
                                                           'demoapp.add_product']}),
                                   forms=product_form()), path='custom')
        self.grant('demoapp.add_product')
        url = self.api(page, 'products')
        self.assertEqual(self.post_json(url, {'name': 'X', 'price': '1'}).status_code,
                         403)
        self.grant('demoapp.view_product')
        self.assertEqual(self.post_json(url, {'name': 'X', 'price': '1'}).status_code,
                         201)

    def test_an_unexposed_model_stops_the_endpoints(self):
        self.grant(*ALL_PRODUCT_PERMS)
        exposure.unexpose(Product)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_only_the_form_fields_are_written(self):
        self.grant(*ALL_PRODUCT_PERMS)
        response = self.post_json(self.url, {'name': 'Saw', 'price': '1',
                                             'description': 'injected',
                                             'owner': self.user.pk})
        self.assertEqual(response.status_code, 201)
        saw = Product.objects.get(name='Saw')
        self.assertEqual((saw.description, saw.owner), ('', None))


class CacheTests(DataDesignTestCase):
    def test_classes_are_kept_by_hash_and_node(self):
        document = design(table(list_fields=['name']), forms=product_form())
        page = self.publish(document, path='products')
        resolved, _errors = engine.resolve_page(page)
        build = resolved.nodes['products'].build
        self.assertIsInstance(build, ObjectManagementBuild)
        self.assertEqual(build.page_hash, page.hash)
        viewset = factories.management_viewset_for(build)
        self.assertIs(factories.management_viewset_for(build), viewset)
        self.assertIs(factories.serializer_for(build, 'list'),
                      factories.serializer_for(build, 'list'))
        # The same build resolved again (another process, a cleared engine
        # cache) is equal, and gets the same classes.
        engine.clear_cache()
        again = engine.resolve_page(page)[0].nodes['products'].build
        self.assertIsNot(again, build)
        self.assertIs(factories.management_viewset_for(again), viewset)

    def test_a_new_hash_gets_new_classes(self):
        self.grant('demoapp.view_product')
        page = self.publish(design(table(list_fields=['name']), forms=product_form()),
                            path='products')
        url = self.api(page, 'products')
        old = engine.resolve_page(page)[0].nodes['products'].build
        old_viewset = factories.management_viewset_for(old)
        self.assertEqual(set(self.client.get(url).json()['data'][0]),
                         {'id', 'name', 'actions'})
        page = self.publish(design(table(list_fields=['name', 'price']),
                                   forms=product_form()), path='products')
        new = engine.resolve_page(page)[0].nodes['products'].build
        self.assertNotEqual(new.page_hash, old.page_hash)
        self.assertIsNot(factories.management_viewset_for(new), old_viewset)
        self.assertEqual(set(self.client.get(url).json()['data'][0]),
                         {'id', 'name', 'price', 'actions'})

    def test_a_changed_exposure_gets_new_classes(self):
        page = self.publish(design(table(list_fields=['name', 'price']),
                                   forms=product_form()), path='products')
        build = engine.resolve_page(page)[0].nodes['products'].build
        viewset = factories.management_viewset_for(build)
        exposure.expose(Product, exclude=('owner',))
        changed = engine.resolve_page(page)[0].nodes['products'].build
        self.assertNotEqual(changed.columns, build.columns)
        self.assertIsNot(factories.management_viewset_for(changed), viewset)


class InlineTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.page = self.publish(load('category_products'))
        self.page_url = reverse('gt-design-page', args=['category-products/%d'
                                                        % self.food.pk])
        self.url = self.api(self.page, 'products', '%d/' % self.food.pk)

    def test_the_page_of_one_parent(self):
        self.grant('demoapp.view_product', 'demoapp.view_productcategory')
        response = self.client.get(self.page_url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('"list_url": "%s"' % self.url, content)
        self.assertEqual(response.context['parent'], self.food)
        # Without the pk, with an unknown one, or without the parent's view.
        self.assertEqual(self.client.get(reverse('gt-design-page', args=[
            'category-products'])).status_code, 404)
        self.assertEqual(self.client.get(reverse('gt-design-page', args=[
            'category-products/999'])).status_code, 404)
        self.assertEqual(self.client.get(reverse('gt-design-page', args=[
            'category-products/x'])).status_code, 404)

    def test_the_parent_needs_its_view_permission(self):
        self.grant(*ALL_PRODUCT_PERMS)
        self.assertEqual(self.client.get(self.page_url).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_rows_are_the_parents_and_new_ones_join_it(self):
        self.grant(*ALL_PRODUCT_PERMS, 'demoapp.view_productcategory')
        names = sorted(row['name'] for row in self.client.get(self.url).json()['data'])
        self.assertEqual(names, ['Apple', 'Bread'])
        response = self.post_json(self.url, {'name': 'Milk', 'price': '1.00',
                                             'status': 'active'})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Product.objects.get(name='Milk').category, self.food)
        # A row of another parent is not reachable through this one.
        other = self.url + '%d/' % self.hammer.pk
        self.assertEqual(self.client.get(other).status_code, 404)
        self.assertEqual(self.client.delete(other).status_code, 404)
        # A parent pk that is no pk at all, or of no row.
        for parent_pk in ('x', '999'):
            url = self.api(self.page, 'products', '%s/' % parent_pk)
            self.assertEqual(self.client.get(url).status_code, 404, parent_pk)

    def test_row_links_to_the_page_of_one_object(self):
        self.publish(load('sales_dashboard'))
        self.grant('demoapp.view_product', 'demoapp.view_productcategory')
        content = self.client.get(reverse('gt-design-page', args=['dashboard'])
                                  ).content.decode()
        config = json.loads(content.split('id="categories_table_gtconfig" type="'
                                          'application/json">')[1]
                            .split('</script>')[0])
        link = config['row_links'][0]
        self.assertEqual(link['url'].replace(link['placeholder'], str(self.food.pk)),
                         self.page_url)
        self.assertEqual(link['i_class'], 'fa fa-cubes')


class ChartAndStatTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.publish(load('category_products'))
        self.page = self.publish(load('sales_dashboard'))

    def chart(self, node_id):
        return self.client.get(self.api(self.page, node_id))

    def test_charts_with_real_data(self):
        self.grant('demoapp.view_product', 'demoapp.view_productcategory')
        data = self.chart('by_category').json()
        self.assertEqual(data['type'], 'bar')
        self.assertEqual(data['data']['labels'], ['Food', 'Tools'])
        self.assertEqual(data['data']['datasets'][0]['data'], [2.0, 1.0])
        data = self.chart('by_status').json()
        self.assertEqual(data['type'], 'pie')
        self.assertEqual(dict(zip(data['data']['labels'],
                                  data['data']['datasets'][0]['data'])),
                         {'Active': 2, 'Draft': 1})
        data = self.chart('price_by_month').json()
        this_month = timezone.localdate().strftime('%Y-%m')
        self.assertEqual(data['type'], 'line')
        self.assertEqual(data['data']['labels'][-1], this_month)
        self.assertEqual(data['data']['datasets'][0]['data'][-1], 3.0)
        self.assertEqual(len(data['data']['labels']), 2)

    def test_a_chart_reads_only_the_groups_it_draws(self):
        self.grant('demoapp.view_product', 'demoapp.view_productcategory')
        page = self.publish(design(node('chart', 'top', {
            'model': 'demoapp.product', 'group_by': 'name', 'aggregate': 'sum',
            'value_field': 'price', 'limit': 2})), path='top')
        with CaptureQueriesContext(connection) as queries:
            data = self.client.get(self.api(page, 'top')).json()
        self.assertEqual(data['data']['labels'], ['Hammer', 'Bread'])
        self.assertEqual(data['data']['datasets'][0]['data'], [30.0, 4.0])
        grouped = [query['sql'] for query in queries
                   if 'GROUP BY' in query['sql'].upper()]
        self.assertTrue(grouped)
        self.assertIn('LIMIT 2', grouped[-1].upper())

    def test_a_chart_needs_its_permission(self):
        self.grant('demoapp.view_productcategory')
        self.assertEqual(self.chart('by_category').status_code, 403)

    def test_a_chart_of_a_data_source(self):
        self.grant('demoapp.view_person')
        from demoapp.models import Country, Person  # noqa: PLC0415 -- test data
        country = Country.objects.create(name='Costa Rica')
        for index in range(3):
            Person.objects.create(name='p%d' % index, num_children=index,
                                  country=country, born_date=date(2000, 1, 1),
                                  last_time=timezone.now())
        page = self.publish(design(node('chart', 'people', {
            'datasource': 'demoapp.person', 'group_by': 'country',
            'aggregate': 'sum', 'value_field': 'num_children'})), path='people')
        data = self.client.get(self.api(page, 'people')).json()
        self.assertEqual(data['data']['labels'], ['Costa Rica'])
        self.assertEqual(data['data']['datasets'][0]['data'], [3.0])
        self.user = User.objects.create_user('beto', password='pw')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.api(page, 'people')).status_code, 403)

    def test_stats_in_the_page_and_their_endpoint(self):
        self.grant('demoapp.view_product', 'demoapp.view_productcategory')
        response = self.client.get(reverse('gt-design-page', args=['dashboard']))
        content = response.content.decode()
        # Products, compared by month: the two of this month.
        self.assertIn('<div class="count">2</div>', content)
        self.assertRegex(content, r'<div class="count">12[.,]00</div>')
        stat = self.client.get(self.api(self.page, 'products')).json()
        # Two products this month, one the month before.
        self.assertEqual(stat, {'value': 2, 'previous': 1, 'change': 100.0})
        self.assertIn('100.0%', content)
        self.assertEqual(self.client.get(self.api(self.page, 'average_price')).json(),
                         {'value': 12.0, 'previous': None, 'change': None})

    def test_a_stat_without_permission(self):
        self.grant('demoapp.view_product')
        self.assertEqual(self.client.get(self.api(self.page, 'categories')
                                         ).status_code, 403)
        content = self.client.get(reverse('gt-design-page', args=['dashboard'])
                                  ).content.decode()
        self.assertIn('data-gtdesign="categories"', content)
        self.assertIn('You do not have permission to see this.', content)


class CrudClassicTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.page = self.publish(design(node('crud_classic', 'tags', {
            'model': 'demoapp.ProductTag', 'title': 'Tags'})), path='tags')
        self.base = self.api(self.page, 'tags')
        self.grant(*['demoapp.%s_producttag' % action
                     for action in ('view', 'add', 'change', 'delete')])

    def test_the_list_is_in_the_page(self):
        ProductTag.objects.create(name='<b>bold</b>')
        content = self.client.get(reverse('gt-design-page', args=['tags'])
                                  ).content.decode()
        self.assertIn('gtdesign-crud-list', content)
        self.assertIn('<td>red</td>', content)
        self.assertIn('&lt;b&gt;bold&lt;/b&gt;', content)
        self.assertIn('href="%screate/"' % self.base, content)
        self.assertIn('href="%s%d/update/"' % (self.base, self.red.pk), content)
        # Searched with the page's own query string.
        content = self.client.get(reverse('gt-design-page', args=['tags']),
                                  {'q': 'blu'}).content.decode()
        self.assertIn('<td>blue</td>', content)
        self.assertNotIn('<td>red</td>', content)

    def test_its_pages_through_the_router(self):
        self.assertEqual(self.client.get(self.base).status_code, 200)
        self.assertContains(self.client.get(self.base + 'create/'), 'name="name"')
        response = self.client.post(self.base + 'create/', {'name': 'green'})
        self.assertRedirects(response, self.base, fetch_redirect_response=False)
        green = ProductTag.objects.get(name='green')
        self.assertContains(self.client.get(self.base + '%d/' % green.pk), 'green')
        response = self.client.post(self.base + '%d/update/' % green.pk,
                                    {'name': 'lime'})
        self.assertEqual(response.status_code, 302)
        green.refresh_from_db()
        self.assertEqual(green.name, 'lime')
        response = self.client.post(self.base + '%d/delete/' % green.pk)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ProductTag.objects.filter(pk=green.pk).exists())
        for rest in ('x/', 'x/update/', '%d/' % green.pk):
            self.assertEqual(self.client.get(self.base + rest).status_code, 404)

    def test_permissions_per_page(self):
        self.user.user_permissions.clear()
        self.grant('demoapp.view_producttag')
        self.assertEqual(self.client.get(self.base).status_code, 200)
        self.assertEqual(self.client.get(self.base + 'create/').status_code, 403)
        self.assertEqual(self.client.post(self.base + 'create/', {'name': 'x'}
                                          ).status_code, 403)
        self.assertEqual(self.client.post(self.base + '%d/delete/' % self.red.pk
                                          ).status_code, 403)
        self.assertTrue(ProductTag.objects.filter(pk=self.red.pk).exists())

    def test_link_mode(self):
        page = self.publish(design(node('crud_classic', 'tags', {
            'model': 'demoapp.ProductTag', 'mode': 'link'})), path='tag-link')
        content = self.client.get(reverse('gt-design-page', args=['tag-link'])
                                  ).content.decode()
        self.assertIn('href="%s"' % self.api(page, 'tags'), content)
        self.assertNotIn('gtdesign-crud-list', content)


class FacetsTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.page = self.publish(load('product_admin'))
        self.url = self.api(self.page, 'product_facets')
        self.grant('demoapp.view_product')

    def facets(self, params=None, columns=None):
        query = {'params': json.dumps(params or {})}
        if columns:
            query['columns'] = columns
        response = self.client.get(self.url + 'facets/', query)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def counts(self, entries):
        # The label of the rows without a value is translated: 'Empty' here.
        return {entry['label'] if entry['value'] is not None else 'Empty':
                entry['count'] for entry in entries}

    def test_the_panel_in_the_page(self):
        content = self.client.get(reverse('gt-design-page', args=['products'])
                                  ).content.decode()
        self.assertIn('class="gtdesign-facets" data-url="%s"' % self.url, content)
        self.assertIn('data-group="gtdesign:products"', content)
        self.assertIn('data-columns="status,category,tags,price"', content)

    def test_the_columns(self):
        info = self.client.get(self.url).json()
        self.assertEqual([column['name'] for column in info['columns']],
                         ['status', 'category', 'tags', 'price'])

    def test_counts_respect_the_other_filters(self):
        result = self.facets()
        self.assertEqual(self.counts(result['status']), {'Active': 2, 'Draft': 1})
        self.assertEqual(self.counts(result['category']), {'Food': 2, 'Tools': 1})
        self.assertEqual(self.counts(result['tags']), {'red': 2, 'blue': 1,
                                                       'Empty': 1})
        status = {'column': 'status', 'op': 'in', 'value': ['active']}
        result = self.facets({'filters': [status]})
        # Its own filter does not narrow its own counts...
        self.assertEqual(self.counts(result['status']), {'Active': 2, 'Draft': 1})
        # ...but narrows every other facet.
        self.assertEqual(self.counts(result['category']), {'Food': 1, 'Tools': 1})
        food = {'column': 'category', 'op': 'in', 'value': [self.food.pk]}
        result = self.facets({'filters': [status, food]})
        self.assertEqual(self.counts(result['status']), {'Active': 1, 'Draft': 1})
        self.assertEqual(self.counts(result['category']), {'Food': 1, 'Tools': 1})
        self.assertEqual(self.counts(result['tags']), {'red': 1})

    def test_counts_respect_the_tables_search(self):
        result = self.facets({'search': 'ham'})
        self.assertEqual(self.counts(result['category']), {'Tools': 1})
        # The table's search fields: description too, not just the columns.
        Product.objects.filter(pk=self.apple.pk).update(description='a hammer box')
        result = self.facets({'search': 'hammer'})
        self.assertEqual(self.counts(result['category']), {'Food': 1, 'Tools': 1})

    def test_one_source_per_request(self):
        with mock.patch.object(factories, 'DesignDataSource',
                               wraps=factories.DesignDataSource) as built:
            result = self.facets({'search': 'ham'})
        self.assertEqual(self.counts(result['category']), {'Tools': 1})
        self.assertEqual(built.call_count, 1)

    def test_the_table_applies_the_facets(self):
        table_url = self.api(self.page, 'products')
        response = self.client.get(table_url, {'gtfilters': json.dumps(
            [{'column': 'tags', 'op': 'in', 'value': [self.blue.pk]}])})
        self.assertEqual([row['name'] for row in response.json()['data']], ['Hammer'])

    def test_bad_requests_and_permissions(self):
        response = self.client.get(self.url + 'facets/', {'params': '[1]'})
        self.assertEqual(response.status_code, 400)
        response = self.client.get(self.url + 'facets/', {'columns': 'owner'})
        self.assertEqual(response.status_code, 400)
        response = self.client.get(self.url + 'facets/', {'params': json.dumps(
            {'filters': [{'column': 'owner', 'op': 'eq', 'value': 1}]})})
        self.assertEqual(response.status_code, 400)
        self.user.user_permissions.clear()
        self.client.force_login(User.objects.get(pk=self.user.pk))
        self.assertEqual(self.client.get(self.url + 'facets/').status_code, 403)


# English labels are asserted: the demo runs in Spanish once its .mo, which is
# not versioned, is compiled, and a local run would disagree with CI.
@override_settings(LANGUAGE_CODE='en')
class PreviewTests(DataDesignTestCase):
    """The editor renders a design with ``preview=True``: no row is read."""

    def test_sample_rows_and_empty_querysets(self):
        self.publish(load('category_products'))
        for name in ('product_admin', 'sales_dashboard'):
            resolved, errors = engine.resolve(load(name), preview=True)
            self.assertEqual(errors, [])
            response = engine.render(resolved, self._request())
            content = response.content.decode()
            for product in ('Apple', 'Bread', 'Hammer'):
                self.assertNotIn(product, content)
            if name == 'product_admin':
                self.assertIn('Name 1', content)
                self.assertNotIn('products_gtconfig', content)
                build = resolved.nodes['products'].build
                self.assertTrue(build.preview)
                viewset = factories.management_viewset_for(build)
                instance = viewset()
                instance.request = None
                self.assertFalse(instance.get_queryset().exists())
            else:
                self.assertIn('gtdesign-chart-sample', content)
                self.assertIn('<div class="count">42</div>', content)
                for node_id in ('by_category', 'by_status'):
                    self.assertTrue(all(row['label'] in factories.SAMPLE_LABELS
                                        for row in factories.chart_rows(
                                            resolved.nodes[node_id].build, None)))

    def _request(self):
        request = self.client.get('/').wsgi_request
        request.user = self.user
        return request


class NotificationTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.page = self.publish(load('product_admin'))
        self.url = self.api(self.page, 'products')
        self.grant(*ALL_PRODUCT_PERMS)

    def test_an_email_on_create(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post_json(self.url, {
                'name': '<i>Saw</i>', 'price': '12.50', 'status': 'active',
                'available_since': '', 'category': self.tools.pk, 'tags': [],
                'description': ''})
        self.assertEqual(response.status_code, 201, response.content)
        template = EmailTemplate.objects.get(code='product_created')
        self.assertEqual(template.subject, 'New product: {{ object.name }}')
        email = EmailNotification.objects.get()
        self.assertEqual(email.recipients, ['ana@example.com', 'sales@group.local'])
        self.assertRegex(email.message, r'ana added <strong>&lt;i&gt;Saw&lt;/i&gt;'
                                        r'</strong> at 12[.,]50')

    def test_a_notice_on_update(self):
        detail = self.url + '%d/' % self.apple.pk
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post_json(detail, {
                'name': 'Green apple', 'price': '2.00', 'status': 'active',
                'available_since': '', 'category': self.food.pk, 'tags': [],
                'description': ''}, method='put')
        self.assertEqual(response.status_code, 200, response.content)
        notice = Notification.objects.get()
        self.assertEqual((notice.description, notice.message_type, notice.user),
                         ('Green apple was updated.', 'success', self.user))
        self.assertEqual(notice.link, reverse('gt-design-page', args=['products']))
        self.assertFalse(EmailNotification.objects.exists())

    def test_the_texts_read_only_allowed_data(self):
        document = copy.deepcopy(load('product_admin'))
        table_node = document['root']['children'][0]['children'][2]['children'][0]
        table_node['props']['notify'] = [{
            'on': 'delete', 'kind': 'notice', 'to': ['actor'],
            'message': '{{ object.name }}|{{ user.password }}|{{ object.owner }}'
                       '|{{ object.save }}'}]
        exposure.expose(Product, exclude=('owner',))
        page = self.publish(document, path='other')
        url = self.api(page, 'products') + '%d/' % self.bread.pk
        Product.objects.filter(pk=self.bread.pk).update(owner=self.user)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(Notification.objects.get().description, 'Bread|||')


@override_settings(GT_DESIGNS_LOGIN_REQUIRED=True)
class AnonymousTests(DataDesignTestCase):
    def test_anonymous_users_reach_no_endpoint(self):
        page = self.publish(load('product_admin'))
        self.client.logout()
        for node_id in ('products', 'product_facets'):
            self.assertEqual(self.client.get(self.api(page, node_id)).status_code,
                             403)
