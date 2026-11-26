"""The ``interactive_grid`` design component (C11) and the versions in the
lists of :class:`~djgentelella.locking.OptimisticLockMixin` (C9).

A grid edits several rows of a model and saves them in one batch: one
transaction, nothing saved when a row fails, and the failures of each row in
the answer, ordered as C9 orders them (403, 404, 409, 400).
"""

import tempfile
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.db.models import signals
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import translation
from rest_framework import permissions, serializers, viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.test import APIRequestFactory

from demoapp.models import Product
from djgentelella.async_notification.models import EmailTemplate
from djgentelella.authorization import authorization
from djgentelella.datasources.base import (
    Column, FunctionDataSource, ModelDataSource, register_datasource,
    unregister_datasource,
)
from djgentelella.designs import engine, exposure, factories, grid
from djgentelella.flows.base import watch_deletes
from djgentelella.locking import (
    OptimisticLockMixin, add_version_to_rows, object_version,
)
from djgentelella.tests.Designs_Test import design, node
from djgentelella.tests.DesignsData_Test import (
    ALL_PRODUCT_PERMS, DataDesignTestCase, load, product_form, table,
)
from djgentelella.tests.DesignsHooks_Test import gtconfig
from djgentelella.tests.Translations_Test import compile_catalogs

__all__ = ['GridVersionInListTests', 'GridResolveTests', 'GridPageTests',
           'GridListTests', 'GridBatchTests', 'GridQueryCountTests',
           'GridWriteTests', 'GridSpanishTests']

COLUMNS = ['name', 'price', 'status', 'category']
#: Each test signs a user in: a fast hasher keeps the class from spending
#: seconds per test hashing its password.
fast_passwords = override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])


def grid_node(id_='grid', **props):
    return node('interactive_grid', id_, {'model': 'demoapp.Product',
                                          'columns': list(COLUMNS), **props})


@authorization('tests.grid.not_the_hammer')
def not_the_hammer(request, obj=None):
    return obj is None or obj.name != 'Hammer'


# -- C9: the version of each row of a list -------------------------------------------

class ProductRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price']


class PlainProducts(OptimisticLockMixin, viewsets.ModelViewSet):
    queryset = Product.objects.order_by('pk')
    serializer_class = ProductRowSerializer
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    pagination_class = None


class VersionedProducts(PlainProducts):
    version_in_list = True


class PagedVersionedProducts(VersionedProducts):
    pagination_class = LimitOffsetPagination


class GridVersionInListTests(TestCase):
    def setUp(self):
        for name, price in (('Apple', '2.00'), ('Bread', '4.00')):
            Product.objects.create(name=name, price=Decimal(price))
        self.factory = APIRequestFactory()

    def list(self, viewset, query=''):
        view = viewset.as_view({'get': 'list'})
        with CaptureQueriesContext(connection) as queries:
            response = view(self.factory.get('/' + query))
        return response.data, len(queries)

    def test_each_row_carries_its_version(self):
        rows, _count = self.list(VersionedProducts)
        self.assertEqual([row['_version'] for row in rows],
                         [object_version(obj)
                          for obj in Product.objects.order_by('pk')])

    def test_off_by_default_the_list_does_not_change(self):
        self.assertFalse(OptimisticLockMixin.version_in_list)
        plain, plain_queries = self.list(PlainProducts)
        versioned, versioned_queries = self.list(VersionedProducts)
        self.assertNotIn('_version', plain[0])
        self.assertEqual([dict(row) for row in plain],
                         [{key: value for key, value in row.items()
                           if key != '_version'} for row in versioned])
        # No extra query: the version is computed from the rows already read.
        self.assertEqual(plain_queries, versioned_queries)

    def test_a_paginated_list(self):
        data, _count = self.list(PagedVersionedProducts, '?limit=1')
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['_version'],
                         object_version(Product.objects.order_by('pk').first()))

    def test_rows_inside_a_wrapper(self):
        """The ``data`` of object management's table serializer."""
        wrapper = type('Table', (serializers.Serializer,), {
            'data': serializers.ListField(child=ProductRowSerializer())})
        serializer = add_version_to_rows(wrapper({'data': list(Product.objects.all())}))
        self.assertTrue(all('_version' in row for row in serializer.data['data']))
        # Wrapping twice does not wrap twice.
        add_version_to_rows(serializer)
        self.assertTrue(serializer.fields['data'].child._gt_versioned)

    def test_detail_and_update_do_not_change(self):
        obj = Product.objects.first()
        view = VersionedProducts.as_view({'get': 'retrieve'})
        response = view(self.factory.get('/'), pk=obj.pk)
        self.assertNotIn('_version', response.data)
        self.assertEqual(response['ETag'], '"%s"' % object_version(obj))


# -- resolve ----------------------------------------------------------------------

@fast_passwords
class GridResolveTests(DataDesignTestCase):

    def resolve(self, **props):
        resolved, errors = engine.resolve(design(grid_node(**props)))
        return resolved, [str(error) for error in errors]

    def test_a_valid_grid(self):
        resolved, errors = self.resolve()
        self.assertEqual(errors, [])
        build = resolved.nodes['grid'].build
        self.assertIsInstance(build, grid.InteractiveGridBuild)
        self.assertEqual(build.list_fields, COLUMNS)
        self.assertEqual(build.editable, COLUMNS)
        self.assertEqual(build.actions, list(grid.GRID_ACTIONS))
        self.assertTrue(build.optimistic_lock)
        self.assertEqual(build.form.field_names, COLUMNS)
        self.assertEqual(build.ordering, ['pk'])
        self.assertEqual(build.perms['update'], ['demoapp.change_product'])

    def test_columns_that_do_not_exist_are_refused(self):
        _resolved, errors = self.resolve(columns=['name', 'price', 'nope'])
        self.assertEqual(len(errors), 1, errors)
        self.assertIn('props.columns', errors[0])
        self.assertIn("'nope'", errors[0])

    def test_columns_the_exposure_withholds_are_refused(self):
        exposure.expose(Product, exclude=('price',))
        _resolved, errors = self.resolve()
        self.assertTrue(any("'price'" in error for error in errors), errors)

    def test_what_a_cell_cannot_edit(self):
        _resolved, errors = self.resolve(columns=['name', 'price', 'tags'],
                                         editable=['name', 'price', 'tags'])
        self.assertTrue(any("'tags' cannot be edited" in error for error in errors),
                        errors)
        _resolved, errors = self.resolve(editable=['name', 'price', 'owner'])
        self.assertTrue(any("'owner' is not one of the columns" in error
                            for error in errors), errors)
        # A many-to-many column is shown, read-only, by default.
        resolved, errors = self.resolve(columns=['name', 'price', 'tags'])
        self.assertEqual(errors, [])
        self.assertEqual(resolved.nodes['grid'].build.editable, ['name', 'price'])

    def test_widgets_follow_the_form_rules(self):
        _resolved, errors = self.resolve(widgets={'status': 'TextInput'})
        self.assertTrue(any('widgets.status' in error for error in errors), errors)
        _resolved, errors = self.resolve(widgets={'owner': 'Select'})
        self.assertTrue(any("'owner' is not an editable column" in error
                            for error in errors), errors)
        resolved, errors = self.resolve(widgets={'status': 'RadioHorizontalSelect'})
        self.assertEqual(errors, [])

    def test_adding_rows_needs_the_required_fields(self):
        _resolved, errors = self.resolve(editable=['name', 'status'])
        self.assertTrue(any('props.actions' in error and 'price' in error
                            for error in errors), errors)
        _resolved, errors = self.resolve(editable=['name', 'status'],
                                         actions=['update', 'destroy'])
        self.assertEqual(errors, [])

    def test_model_or_datasource(self):
        _resolved, errors = self.resolve(datasource='products')
        self.assertTrue(any('not both' in error for error in errors), errors)
        document = design(node('interactive_grid', 'grid', {'columns': ['name']}))
        _resolved, errors = engine.resolve(document)
        self.assertTrue(any('not both' in str(error) for error in errors))

    def test_the_props_schema(self):
        _resolved, errors = self.resolve(page_size=500, actions=['explode'],
                                         optimistic_lock='yes', columns=[])
        joined = ' '.join(errors)
        for prop in ('page_size', 'actions', 'optimistic_lock', 'columns'):
            self.assertIn('props.' + prop, joined)

    def test_conditions_name_columns_and_actions(self):
        cond = {'perm': 'demoapp.view_product'}
        cases = (({'column_conditions': {'nope': cond}}, 'column_conditions.nope'),
                 ({'edit_conditions': {'owner': cond}}, 'edit_conditions.owner'),
                 ({'action_conditions': {'retrieve': cond}},
                  'action_conditions.retrieve'))
        for props, where in cases:
            _resolved, errors = self.resolve(**props)
            self.assertEqual(len(errors), 1, errors)
            self.assertIn(where, errors[0])

    def test_unknown_permissions(self):
        _resolved, errors = self.resolve(perms={'update': ['demoapp.fly_product']})
        self.assertTrue(any('fly_product' in error for error in errors), errors)

    def test_the_demo_design(self):
        self.assertEqual(self.errors(load('product_grid')), [])


# -- the page -------------------------------------------------------------------

@fast_passwords
class GridPageTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.grant(*ALL_PRODUCT_PERMS)

    def config(self, response):
        return gtconfig(response.content.decode(), 'grid')

    def test_the_page_has_the_grid_and_its_cells(self):
        self.publish(design(grid_node()), path='grid')
        response = self.client.get('/designs/grid')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('gtdesign-grid', html)
        self.assertIn('interactive_grid.js', html)
        for name in COLUMNS:
            self.assertIn('data-gtgrid-cell="%s"' % name, html)
        # The widgets of the cells, with a prefix the browser replaces per row.
        self.assertIn('name="grid-__row__-price"', html)
        config = self.config(response)
        self.assertEqual([column['name'] for column in config['columns']], COLUMNS)
        self.assertTrue(all(column['editable'] for column in config['columns']))
        self.assertEqual(config['allowed'],
                         {'create': True, 'update': True, 'destroy': True})
        category = config['columns'][3]
        self.assertEqual((category['kind'], category['widget'], category['lookup']),
                         ('fk', 'Select', False))

    def test_permissions_and_conditions_shape_the_page(self):
        self.user.user_permissions.clear()
        self.grant('demoapp.view_product', 'demoapp.change_product')
        self.publish(design(grid_node(
            column_conditions={'category': {'perm': 'demoapp.delete_product'}},
            edit_conditions={'price': {'perm': 'demoapp.delete_product'}})),
            path='grid')
        response = self.client.get('/designs/grid')
        config = self.config(response)
        html = response.content.decode()
        self.assertEqual(config['allowed'],
                         {'create': False, 'update': True, 'destroy': False})
        self.assertEqual([column['name'] for column in config['columns']],
                         ['name', 'price', 'status'])
        self.assertFalse(config['columns'][1]['editable'])
        self.assertNotIn('data-gtgrid-cell="price"', html)
        self.assertNotIn('data-gtgrid-cell="category"', html)
        self.assertNotIn('gtgrid-add', html)

    def test_without_the_list_permission(self):
        self.user.user_permissions.clear()
        self.publish(design(grid_node()), path='grid')
        self.assertNotIn('gtdesign-grid', self.client.get('/designs/grid')
                         .content.decode())

    def test_the_preview_has_sample_rows(self):
        resolved, errors = engine.resolve(design(grid_node()), preview=True)
        self.assertEqual(errors, [])
        request = self.client.get('/').wsgi_request
        request.user = self.user
        html = engine.render(resolved, request).content.decode()
        self.assertIn('Name 1', html)
        self.assertNotIn('Bread', html)
        self.assertNotIn('grid_gtconfig', html)


# -- the list -------------------------------------------------------------------

@fast_passwords
class GridTestCase(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.grant(*ALL_PRODUCT_PERMS)

    def page(self, path='grid', **props):
        page = self.publish(design(grid_node(**props)), path=path)
        return self.api(page, 'grid')

    def rows(self, url):
        response = self.client.get(url + '?limit=100')
        self.assertEqual(response.status_code, 200, response.content)
        return {row['name']: row for row in response.json()['data']}

    def save(self, url, *rows):
        return self.post_json(url + 'save/', {'rows': list(rows)})

    def update(self, obj, key=None, version=None, **data):
        return {'key': key or 'r%d' % obj.pk, 'op': 'update', 'id': obj.pk,
                '_version': version or object_version(obj), 'data': data}

    def failures(self, response):
        return {row['key']: row for row in response.json()['rows']}


class GridListTests(GridTestCase):
    def test_rows_carry_their_version_and_actions(self):
        url = self.page()
        response = self.client.get(url)
        data = response.json()
        self.assertEqual(data['count'], 3)
        self.assertEqual([row['name'] for row in data['data']],
                         ['Apple', 'Bread', 'Hammer'])
        bread = data['data'][1]
        self.assertEqual(bread['_version'], object_version(self.bread))
        self.assertEqual(bread['category'], {'id': self.food.pk, 'text': 'Food',
                                             'selected': True, 'disabled': False})
        self.assertEqual(bread['actions'], {'update': True, 'destroy': True})
        self.assertEqual(bread['readonly'], [])

    def test_per_row_conditions(self):
        url = self.page(
            action_conditions={'update': {'auth': 'tests.grid.not_the_hammer'}},
            edit_conditions={'price': {'auth': 'tests.grid.not_the_hammer'}})
        rows = self.rows(url)
        self.assertEqual(rows['Hammer']['actions'],
                         {'update': False, 'destroy': True})
        self.assertEqual(rows['Hammer']['readonly'], ['price'])
        self.assertEqual(rows['Bread']['actions'], {'update': True, 'destroy': True})
        self.assertEqual(rows['Bread']['readonly'], [])

    def test_hidden_columns_leave_the_rows(self):
        url = self.page(column_conditions={'price': {'perm': 'demoapp.fly'}})
        self.assertNotIn('price', self.rows(url)['Bread'])
        detail = self.client.get(url + '%d/' % self.bread.pk).json()
        self.assertNotIn('price', detail)

    def test_pages_and_search(self):
        url = self.page(page_size=2)
        data = self.client.get(url).json()
        self.assertEqual((len(data['data']), data['count']), (2, 3))
        data = self.client.get(url + '?limit=2&offset=2').json()
        self.assertEqual([row['name'] for row in data['data']], ['Hammer'])
        data = self.client.get(url + '?search=bre').json()
        self.assertEqual([row['name'] for row in data['data']], ['Bread'])

    def test_one_row_again(self):
        url = self.page()
        response = self.client.get(url + '%d/' % self.bread.pk)
        self.assertEqual(response.status_code, 200)
        version = object_version(self.bread)
        self.assertEqual(response.json()['_version'], version)
        self.assertEqual(response['ETag'], '"%s"' % version)
        self.assertEqual(self.client.get(url + '999999/').status_code, 404)
        self.assertEqual(self.client.get(url + 'abc/').status_code, 404)

    def test_the_list_needs_its_permission(self):
        url = self.page()
        self.user.user_permissions.clear()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.save(url, self.update(self.bread, name='x')).status_code,
                         403)

    def test_object_management_lists_stay_as_they_were(self):
        """The prop is off by default: a table, even with optimistic_lock,
        does not add versions to its rows."""
        page = self.publish(design(table(optimistic_lock=True), forms=product_form()),
                            path='products')
        data = self.client.get(self.api(page, 'products')).json()
        self.assertTrue(data['data'])
        self.assertTrue(all('_version' not in row for row in data['data']))
        resolved, _errors = engine.resolve(design(table(optimistic_lock=True),
                                                  forms=product_form()))
        viewset = factories.management_viewset_for(resolved.nodes['products'].build)
        self.assertFalse(viewset.version_in_list)


# -- the batch ------------------------------------------------------------------

class GridBatchTests(GridTestCase):
    def test_two_rows_are_saved_together(self):
        url = self.page()
        response = self.save(url, self.update(self.bread, name='Rye bread'),
                             self.update(self.apple, price='2.50',
                                         category=self.tools.pk))
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['saved'])
        self.bread.refresh_from_db()
        self.apple.refresh_from_db()
        self.assertEqual(self.bread.name, 'Rye bread')
        self.assertEqual((self.apple.price, self.apple.category),
                         (Decimal('2.50'), self.tools))
        saved = {row['key']: row for row in data['rows']}
        self.assertEqual(saved['r%d' % self.bread.pk]['row']['_version'],
                         object_version(self.bread))
        self.assertEqual(saved['r%d' % self.apple.pk]['row']['category']['text'],
                         'Tools')

    def test_one_invalid_row_saves_nothing(self):
        url = self.page()
        response = self.save(url, self.update(self.bread, name='Rye bread'),
                             self.update(self.apple, price='cheap', status='gone'))
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['saved'])
        self.assertEqual(data['code'], 'batch_rejected')
        failures = self.failures(response)
        self.assertEqual(list(failures), ['r%d' % self.apple.pk])
        apple = failures['r%d' % self.apple.pk]
        self.assertEqual((apple['status'], apple['code'], apple['id']),
                         (400, 'invalid', self.apple.pk))
        self.assertEqual(sorted(apple['errors']), ['price', 'status'])
        self.assertEqual(Product.objects.get(pk=self.bread.pk).name, 'Bread')

    def test_a_version_conflict(self):
        url = self.page()
        old = object_version(self.bread)
        Product.objects.filter(pk=self.bread.pk).update(name='Whole bread')
        response = self.save(url, self.update(self.bread, version=old, name='Rye'),
                             self.update(self.apple, name='Green apple'))
        self.assertEqual(response.status_code, 409)
        failure = self.failures(response)['r%d' % self.bread.pk]
        self.assertEqual(failure['code'], 'version_conflict')
        current = Product.objects.get(pk=self.bread.pk)
        self.assertEqual(failure['version'], object_version(current))
        self.assertEqual(current.name, 'Whole bread')
        self.assertEqual(Product.objects.get(pk=self.apple.pk).name, 'Apple')
        # With the version read again, the same batch goes through.
        response = self.save(url, self.update(current, version=failure['version'],
                                              name='Rye'),
                             self.update(self.apple, name='Green apple'))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Product.objects.get(pk=self.bread.pk).name, 'Rye')

    def test_a_condition_comes_before_the_version(self):
        url = self.page(
            action_conditions={'update': {'auth': 'tests.grid.not_the_hammer'}})
        response = self.save(url, self.update(self.hammer, version='old', name='x'),
                             self.update(self.bread, version='old', name='y'),
                             self.update(self.apple, name=''))
        # 403 of the hammer wins over the 409 of the bread and the 400 of
        # the apple; each row says what it got.
        self.assertEqual(response.status_code, 403)
        failures = self.failures(response)
        self.assertEqual(failures['r%d' % self.hammer.pk]['code'], 'permission_denied')
        self.assertEqual(failures['r%d' % self.bread.pk]['code'], 'version_conflict')
        self.assertEqual(failures['r%d' % self.apple.pk]['code'], 'invalid')
        self.assertEqual(Product.objects.get(pk=self.apple.pk).name, 'Apple')

    def test_the_version_comes_before_the_data(self):
        url = self.page()
        response = self.save(url, self.update(self.bread, version='old', price='x'))
        self.assertEqual(response.status_code, 409)

    def test_new_and_deleted_rows(self):
        url = self.page()
        response = self.save(
            url,
            {'key': 'n1', 'op': 'create',
             'data': {'name': 'Pear', 'price': '1.20', 'status': 'active',
                      'category': self.food.pk}},
            {'key': 'n2', 'op': 'create', 'data': {'name': 'Saw', 'price': '20'}},
            {'key': 'd1', 'op': 'delete', 'id': self.hammer.pk,
             '_version': object_version(self.hammer)},
            self.update(self.bread, name='Rye bread'))
        self.assertEqual(response.status_code, 200, response.content)
        saved = {row['key']: row for row in response.json()['rows']}
        pear = Product.objects.get(name='Pear')
        self.assertEqual((saved['n1']['id'], saved['n1']['row']['name']),
                         (pear.pk, 'Pear'))
        self.assertEqual(pear.category, self.food)
        self.assertEqual(Product.objects.get(name='Saw').status, 'draft')
        self.assertEqual(saved['d1'], {'key': 'd1', 'op': 'delete',
                                       'id': self.hammer.pk})
        self.assertFalse(Product.objects.filter(pk=self.hammer.pk).exists())
        self.assertEqual(Product.objects.get(pk=self.bread.pk).name, 'Rye bread')

    def test_a_failing_new_row_keeps_the_deletes(self):
        url = self.page()
        response = self.save(
            url, {'key': 'n1', 'op': 'create', 'data': {'name': 'Pear'}},
            {'key': 'd1', 'op': 'delete', 'id': self.hammer.pk,
             '_version': object_version(self.hammer)})
        self.assertEqual(response.status_code, 400)
        self.assertIn('price', self.failures(response)['n1']['errors'])
        self.assertTrue(Product.objects.filter(pk=self.hammer.pk).exists())
        self.assertFalse(Product.objects.filter(name='Pear').exists())

    def test_deleting_a_changed_row_is_a_conflict(self):
        url = self.page()
        old = object_version(self.hammer)
        Product.objects.filter(pk=self.hammer.pk).update(price=Decimal('31.00'))
        response = self.save(url, {'key': 'd1', 'op': 'delete', 'id': self.hammer.pk,
                                   '_version': old})
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Product.objects.filter(pk=self.hammer.pk).exists())

    def test_rows_that_do_not_exist(self):
        url = self.page()
        for pk in (999999, 'abc'):
            response = self.save(url, {'key': 'x', 'op': 'update', 'id': pk,
                                       '_version': 'v', 'data': {'name': 'x'}})
            self.assertEqual(response.status_code, 404)
            self.assertEqual(self.failures(response)['x']['code'], 'not_found')

    def test_a_version_is_required(self):
        url = self.page()
        row = self.update(self.bread, name='x')
        del row['_version']
        response = self.save(url, row)
        self.assertEqual(response.status_code, 428)
        self.assertEqual(self.failures(response)[row['key']]['code'],
                         'version_required')
        # Without optimistic_lock the version is not checked.
        url = self.page(path='grid2', optimistic_lock=False)
        response = self.save(url, row, self.update(self.apple, version='old',
                                                   name='Green'))
        self.assertEqual(response.status_code, 200, response.content)

    def test_permissions_per_action(self):
        self.user.user_permissions.clear()
        self.grant('demoapp.view_product', 'demoapp.change_product')
        url = self.page()
        response = self.save(
            url, self.update(self.bread, name='Rye'),
            {'key': 'n1', 'op': 'create', 'data': {'name': 'Pear', 'price': '1'}},
            {'key': 'd1', 'op': 'delete', 'id': self.hammer.pk,
             '_version': object_version(self.hammer)})
        self.assertEqual(response.status_code, 403)
        failures = self.failures(response)
        self.assertEqual(sorted(failures), ['d1', 'n1'])
        self.assertEqual(Product.objects.get(pk=self.bread.pk).name, 'Bread')

    def test_actions_the_grid_does_not_offer(self):
        url = self.page(actions=['update'])
        response = self.save(url, {'key': 'd1', 'op': 'delete', 'id': self.hammer.pk,
                                   '_version': object_version(self.hammer)})
        self.assertEqual(response.status_code, 403)

    def test_columns_a_row_cannot_write(self):
        url = self.page(columns=['name', 'price', 'status', 'category', 'tags'],
                        column_conditions={'status': {'perm': 'demoapp.fly'}})
        # A hidden column is a 403, a column that is not editable a 400.
        response = self.save(url, self.update(self.bread, status='active'))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.failures(response)['r%d' % self.bread.pk]['fields'],
                         ['status'])
        response = self.save(url, self.update(self.bread, tags=[self.red.pk],
                                              owner=self.user.pk))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(sorted(self.failures(response)['r%d' % self.bread.pk]
                                ['errors']), ['owner', 'tags'])

    def test_edit_conditions(self):
        url = self.page(
            edit_conditions={'price': {'perm': 'demoapp.fly'},
                             'name': {'auth': 'tests.grid.not_the_hammer'}})
        response = self.save(url, self.update(self.bread, price='9'))
        self.assertEqual(response.status_code, 403)
        response = self.save(url, self.update(self.hammer, name='Mallet'))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.failures(response)['r%d' % self.hammer.pk]['fields'],
                         ['name'])
        response = self.save(url, self.update(self.bread, name='Rye'))
        self.assertEqual(response.status_code, 200, response.content)

    def test_an_unknown_relation_is_a_field_error(self):
        url = self.page()
        for value in (999999, 'abc'):
            response = self.save(url, self.update(self.bread, category=value))
            self.assertEqual(response.status_code, 400)
            self.assertIn('category',
                          self.failures(response)['r%d' % self.bread.pk]['errors'])
        response = self.save(url, self.update(self.bread, category=None))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(Product.objects.get(pk=self.bread.pk).category)

    def test_bodies_that_are_not_a_batch(self):
        url = self.page()
        version = object_version(self.bread)
        for body in ({}, {'rows': []}, {'rows': 'x'}, [1],
                     {'rows': [{'op': 'explode'}]},
                     {'rows': [{'key': 'a', 'op': 'update', 'data': {}}]},
                     {'rows': [{'key': 'a', 'op': 'create', 'id': 1}]},
                     {'rows': [{'key': 'a', 'op': 'create', 'data': []}]},
                     {'rows': [{'key': 'a', 'op': 'create'},
                               {'key': 'a', 'op': 'create'}]},
                     {'rows': [{'key': 'a', 'op': 'update', 'id': 1,
                                '_version': version},
                               {'key': 'b', 'op': 'delete', 'id': 1,
                                '_version': version}]}):
            response = self.post_json(url + 'save/', body)
            self.assertEqual(response.status_code, 400, body)
            self.assertEqual(response.json()['code'], 'invalid_batch', body)
        # The limit of the viewset (MAX_BATCH_ROWS by default).
        with mock.patch.object(grid.GridMixin, 'max_batch_rows', 2):
            response = self.post_json(url + 'save/', {'rows': [
                {'key': str(index), 'op': 'create'} for index in range(3)]})
            self.assertEqual(response.status_code, 400)

    def test_a_data_source_limits_the_rows(self):
        source = ModelDataSource(Product, name='tests.grid.food',
                                 queryset=Product.objects.filter(category__name='Food'),
                                 fields=['name', 'price', 'status', 'category'])
        register_datasource(source)
        self.addCleanup(unregister_datasource, 'tests.grid.food')
        page = self.publish(design(node('interactive_grid', 'grid', {
            'datasource': 'tests.grid.food', 'columns': COLUMNS})), path='food')
        url = self.api(page, 'grid')
        self.assertEqual(sorted(self.rows(url)), ['Apple', 'Bread'])
        response = self.save(url, self.update(self.hammer, name='x'))
        self.assertEqual(response.status_code, 404)
        response = self.save(url, self.update(self.bread, name='Rye'))
        self.assertEqual(response.status_code, 200, response.content)
        # A column the source does not offer is not a column of the grid.
        _resolved, errors = engine.resolve(design(node('interactive_grid', 'grid', {
            'datasource': 'tests.grid.food', 'columns': ['name', 'owner']})))
        self.assertTrue(any("'owner'" in str(error) for error in errors))

    def test_an_unknown_data_source(self):
        _resolved, errors = engine.resolve(design(node('interactive_grid', 'grid', {
            'datasource': 'tests.grid.none', 'columns': ['name']})))
        self.assertTrue(any('unknown data source' in str(error) for error in errors))

    def test_a_data_source_without_a_model_is_read_only(self):
        register_datasource(FunctionDataSource(
            lambda request: Product.objects.all(),
            [Column('name', 'Name', 'string')], name='tests.grid.nomodel', perms=[]))
        self.addCleanup(unregister_datasource, 'tests.grid.nomodel')
        resolved, errors = engine.resolve(design(node('interactive_grid', 'grid', {
            'datasource': 'tests.grid.nomodel', 'columns': ['name']})))
        self.assertEqual(errors, [])
        build = resolved.nodes['grid'].build
        self.assertTrue(build.list_only)
        self.assertEqual((build.editable, build.actions), ([], []))
        self.assertIsNone(build.form)
        _resolved, errors = engine.resolve(design(node('interactive_grid', 'grid', {
            'datasource': 'tests.grid.nomodel', 'columns': ['name'],
            'editable': ['name']})))
        self.assertTrue(any("it has no 'editable'" in str(error) for error in errors))


class GridQueryCountTests(GridTestCase):
    """A batch reads its rows in one query and writes them in one: one row or
    ten cost the same."""

    def setUp(self):
        super().setUp()
        for index in range(10):
            Product.objects.create(name='P%d' % index, price=Decimal(index),
                                   category=self.food)
        self.url = self.page()
        # The page and its classes are cached by the first request.
        self.client.get(self.url)

    def count(self, rows):
        with CaptureQueriesContext(connection) as queries:
            response = self.save(self.url, *rows)
        self.assertEqual(response.status_code, 200, response.content)
        return len(queries)

    def updates(self, count, **data):
        return [self.update(obj, **data) for obj in
                Product.objects.filter(name__startswith='P').order_by('pk')[:count]]

    def test_updates(self):
        one = self.count(self.updates(1, price='1.50'))
        ten = self.count(self.updates(10, price='2.50'))
        self.assertEqual(one, ten)
        rows = self.updates(5, status='active')
        with self.assertNumQueries(one):
            self.save(self.url, *rows)
        # A new relation is read once for all the rows.
        one = self.count(self.updates(1, category=self.tools.pk))
        ten = self.count(self.updates(10, category=self.food.pk))
        self.assertEqual(one, ten)

    def test_creates_and_deletes(self):
        def creates(count):
            return [{'key': 'n%d' % index, 'op': 'create',
                     'data': {'name': 'N%d' % index, 'price': '1'}}
                    for index in range(count)]

        def deletes(count):
            return [{'key': 'd%d' % obj.pk, 'op': 'delete', 'id': obj.pk,
                     '_version': object_version(obj)} for obj in
                    Product.objects.filter(name__startswith='N').order_by('pk')[:count]]

        self.assertEqual(self.count(creates(1)), self.count(creates(10)))
        # One DELETE per table while nothing listens to the deletes of the
        # model. djgentelella.flows listens to the models its flows run on
        # (watch_deletes), and an earlier test may have published one on
        # Product: then Django's collector sends the signal row by row.
        uid = 'gtflows-delete-%s' % Product._meta.label_lower
        if signals.post_delete.disconnect(sender=Product, dispatch_uid=uid):
            self.addCleanup(watch_deletes, Product)
        self.assertFalse(signals.post_delete.has_listeners(Product))
        self.assertEqual(self.count(deletes(1)), self.count(deletes(10)))

    def test_the_exact_numbers(self):
        """Pinned, so a change shows. Saving 1 or N rows costs what the
        endpoint costs (Site, page and its permissions, session, user and
        the user's permissions: 7), plus the transaction of the batch and the
        savepoint of its writes (4), the rows read and locked (1), one
        bulk_update (1) and the rows read again for the answer (1)."""
        for count in (1, 7):
            rows = self.updates(count, name='Q%d' % count)
            with self.assertNumQueries(14):
                self.save(self.url, *rows)


class GridWriteTests(GridTestCase):
    """How the rows are written: one ``bulk_update`` when the model allows
    it, ``save()`` of each row when it has its own or a signal listens."""

    def test_a_model_with_its_own_save_saves_each_row(self):
        url = self.page()
        calls = []
        original = Product.save

        def save(obj, *args, **kwargs):
            calls.append(obj.pk)
            return original(obj, *args, **kwargs)

        with mock.patch.object(Product, 'save', save):
            response = self.save(url, self.update(self.bread, name='Rye'),
                                 self.update(self.apple, name='Green'),
                                 {'key': 'n', 'op': 'create',
                                  'data': {'name': 'Pear', 'price': '1'}})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(calls), 3)
        self.assertEqual(Product.objects.get(pk=self.apple.pk).name, 'Green')

    def test_auto_now_and_a_duplicate_in_the_batch(self):
        exposure.expose(EmailTemplate)
        template = EmailTemplate.objects.create(code='hello', subject='Hi',
                                                message='<p>Hi</p>')
        EmailTemplate.objects.filter(pk=template.pk).update(
            updated_at='2001-01-01T00:00:00Z')
        template.refresh_from_db()
        self.grant(*['async_notification.%s_emailtemplate' % action
                     for action in ('view', 'add', 'change', 'delete')])
        page = self.publish(design(node('interactive_grid', 'templates', {
            'model': 'async_notification.EmailTemplate',
            'columns': ['code', 'subject', 'message']})), path='templates')
        url = self.api(page, 'templates')
        response = self.save(url, {'key': 'a', 'op': 'update', 'id': template.pk,
                                   '_version': object_version(template),
                                   'data': {'subject': 'Hello'}})
        self.assertEqual(response.status_code, 200, response.content)
        template.refresh_from_db()
        self.assertEqual(template.subject, 'Hello')
        # What save() would have done: auto_now moved.
        self.assertGreater(template.updated_at.year, 2001)
        # Two new rows with the same unique code: the database says no, and
        # nothing is saved.
        response = self.save(
            url, {'key': 'a', 'op': 'update', 'id': template.pk,
                  '_version': object_version(template), 'data': {'subject': 'Bye'}},
            *[{'key': 'n%d' % index, 'op': 'create',
               'data': {'code': 'twice', 'subject': 's', 'message': 'm'}}
              for index in range(2)])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'batch_rejected')
        self.assertFalse(EmailTemplate.objects.filter(code='twice').exists())
        self.assertEqual(EmailTemplate.objects.get(pk=template.pk).subject, 'Hello')
        # A duplicate of a saved row is a field error of its row.
        response = self.save(url, {'key': 'n', 'op': 'create', 'data': {
            'code': 'hello', 'subject': 's', 'message': 'm'}})
        self.assertEqual(response.status_code, 400)
        self.assertIn('code', self.failures(response)['n']['errors'])


class GridSpanishTests(GridTestCase):
    """The answers speak the language of the request."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        compile_catalogs(cls.tmp.name)

    def test_in_spanish(self):
        url = self.page(actions=['update'])
        with override_settings(LOCALE_PATHS=[self.tmp.name]), \
                translation.override('es'):
            response = self.save(url, {'key': 'n', 'op': 'create', 'data': {}},
                                 self.update(self.bread, version='old', name='x'))
            data = response.json()
            self.assertIn('No se guardó nada', data['detail'])
            failures = self.failures(response)
            self.assertEqual(failures['n']['detail'], 'Aquí no puedes añadir filas.')
            self.assertIn('Otra persona modificó', failures['r%d' % self.bread.pk]
                          ['detail'])
            response = self.post_json(url + 'save/', {'rows': []})
            self.assertIn('al menos una fila', response.json()['detail'])
