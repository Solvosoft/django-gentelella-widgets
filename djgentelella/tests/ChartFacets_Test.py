"""W21: a ``chart`` of a design page follows a ``facets`` panel (its
``facets`` prop) the way the table of the panel does: the browser sends the
panel's filters (``gtfilters``) and the chart aggregates only those rows."""

import json
from decimal import Decimal

from django.test import override_settings

from demoapp.models import PurchaseRequest
from djgentelella.designs import engine, registry
from djgentelella.tests.Designs_Test import design, node
from djgentelella.tests.DesignsData_Test import (
    ALL_PRODUCT_PERMS, DataDesignTestCase, product_form, table,
)
from djgentelella.tests.DesignsHooks_Test import HookReport

__all__ = ['ChartFacetsResolveTests', 'ChartFacetsServeTests',
           'ChartFacetsOverASourceTests']

FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
STATUS_DRAFT = {'column': 'status', 'op': 'in', 'value': ['draft']}


def facets(target='products', columns=('status', 'category'), id_='f'):
    return node('facets', id_, {'target': target, 'columns': list(columns)})


def chart(id_='by_category', **props):
    return node('chart', id_, {'model': 'demoapp.Product', 'group_by': 'category',
                               'facets': 'f', **props})


def page(*nodes, table_props=None):
    return design(table(**(table_props or {})), facets(), *nodes,
                  forms=product_form())


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS)
class ChartFacetsResolveTests(DataDesignTestCase):
    def test_a_chart_bound_to_a_panel(self):
        resolved, errors = engine.resolve(page(chart()))
        self.assertEqual(errors, [])
        build = resolved.nodes['by_category'].build
        self.assertEqual((build.facets, build.facets_target, build.facet_columns),
                         ('f', 'products', ['status', 'category']))

    def test_without_the_prop_it_follows_nothing(self):
        resolved, errors = engine.resolve(page(node(
            'chart', 'by_category', {'model': 'demoapp.Product',
                                     'group_by': 'category'})))
        self.assertEqual(errors, [])
        build = resolved.nodes['by_category'].build
        self.assertEqual((build.facets, build.facets_target, build.facet_columns),
                         ('', '', []))

    def test_what_it_cannot_follow(self):
        self.assertIn("'nope' is not the id of a facets panel of this page",
                      ' '.join(self.errors(page(chart(facets='nope')))))
        self.assertIn("'products' is not the id of a facets panel of this page",
                      ' '.join(self.errors(page(chart(facets='products')))))
        other_model = page(chart(model='demoapp.ProductCategory', group_by='name'))
        self.assertIn('does not filter rows of demoapp.ProductCategory',
                      ' '.join(self.errors(other_model)))
        over_a_source = page(node('chart', 'by_source', {
            'datasource': 'demoapp.country', 'group_by': 'name', 'facets': 'f',
            'perms': ['demoapp.view_country']}))
        self.assertIn("facets panel 'f' does not filter data source "
                      "'demoapp.country'", ' '.join(self.errors(over_a_source)))


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS)
class ChartFacetsServeTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.grant(*ALL_PRODUCT_PERMS, 'demoapp.view_productcategory')

    def counts(self, page, filters=None, node_id='by_category'):
        params = {'gtfilters': json.dumps(filters)} if filters is not None else {}
        response = self.client.get(self.api(page, node_id), params)
        if response.status_code != 200:
            return response.status_code
        data = response.json()['data']
        return dict(zip(data['labels'], data['datasets'][0]['data']))

    def test_the_page_binds_the_chart_to_the_panel(self):
        self.publish(page(chart()), path='dash')
        html = self.client.get('/designs/dash').content.decode()
        self.assertIn('data-gtfacets-target="products"', html)
        self.publish(page(node('chart', 'plain', {'model': 'demoapp.Product',
                                                  'group_by': 'category'})),
                     path='plain')
        self.assertNotIn('data-gtfacets-target',
                         self.client.get('/designs/plain').content.decode())

    def test_the_chart_applies_the_facets(self):
        dash = self.publish(page(chart()), path='dash')
        self.assertEqual(self.counts(dash), {'Food': 2.0, 'Tools': 1.0})
        self.assertEqual(self.counts(dash, [STATUS_DRAFT]), {'Food': 1.0})
        tools = {'column': 'category', 'op': 'in', 'value': [self.tools.pk]}
        self.assertEqual(self.counts(dash, [tools]), {'Tools': 1.0})
        self.assertEqual(self.counts(dash, []), {'Food': 2.0, 'Tools': 1.0})

    def test_only_the_facets_of_its_panel(self):
        dash = self.publish(page(chart()), path='dash')
        name = {'column': 'name', 'op': 'eq', 'value': 'Apple'}
        self.assertEqual(self.counts(dash, [name]), 400)
        self.assertEqual(self.counts(dash, [{'op': 'eq', 'value': 1}]), 400)
        response = self.client.get(self.api(dash, 'by_category'),
                                   {'gtfilters': 'not json'})
        self.assertEqual(response.status_code, 400)

    def test_a_chart_without_facets_takes_no_filters(self):
        dash = self.publish(page(node('chart', 'plain', {
            'model': 'demoapp.Product', 'group_by': 'category'})), path='plain')
        self.assertEqual(self.counts(dash, [STATUS_DRAFT], node_id='plain'), 400)
        self.assertEqual(self.counts(dash, node_id='plain'),
                         {'Food': 2.0, 'Tools': 1.0})

    def test_not_on_a_column_its_table_hides(self):
        self.user.user_permissions.clear()
        self.grant('demoapp.view_product', 'demoapp.view_productcategory')
        dash = self.publish(page(chart(), table_props={'column_conditions': {
            'status': {'perm': 'demoapp.delete_product'}}}), path='dash')
        self.assertEqual(self.counts(dash, [STATUS_DRAFT]), 400)
        food = {'column': 'category', 'op': 'in', 'value': [self.food.pk]}
        self.assertEqual(self.counts(dash, [food]), {'Food': 2.0})


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS)
class ChartFacetsOverASourceTests(DataDesignTestCase):
    """A chart over a data source follows a panel over that source (a node of
    a component that declares ``facets_target``)."""

    def setUp(self):
        super().setUp()
        registry.register(HookReport)
        self.grant('demoapp.view_purchaserequest')
        for title, supplier in (('Paper', 'Acme'), ('Ink', 'Acme'),
                                ('Chairs', 'Office')):
            PurchaseRequest.objects.create(title=title, supplier=supplier,
                                           amount=Decimal('1'), requester=self.user)

    def document(self, source='demoapp.purchases', group_by='supplier'):
        return design(
            node('hook_report', 'report', {'datasource': 'demoapp.purchases'}),
            node('facets', 'filters', {'target': 'report',
                                       'columns': ['title', 'supplier']}),
            node('chart', 'by_supplier', {'datasource': source,
                                          'group_by': group_by,
                                          'facets': 'filters'}))

    def test_it_follows_the_panel_of_its_source(self):
        dash = self.publish(self.document(), path='purchases')
        url = self.api(dash, 'by_supplier')
        data = self.client.get(url).json()['data']
        self.assertEqual(dict(zip(data['labels'], data['datasets'][0]['data'])),
                         {'Acme': 2.0, 'Office': 1.0})
        filters = [{'column': 'title', 'op': 'in', 'value': ['Ink', 'Chairs']}]
        data = self.client.get(url, {'gtfilters': json.dumps(filters)}).json()['data']
        self.assertEqual(dict(zip(data['labels'], data['datasets'][0]['data'])),
                         {'Acme': 1.0, 'Office': 1.0})

    def test_a_panel_of_another_source(self):
        errors = self.errors(self.document(source='demoapp.country',
                                           group_by='name'))
        self.assertIn("facets panel 'filters' does not filter data source "
                      "'demoapp.country'", ' '.join(errors))
