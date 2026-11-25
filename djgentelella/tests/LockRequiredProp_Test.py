"""The ``optimistic_lock_required`` prop of ``object_management``,
``inline_object_management``, ``crud_classic`` and ``interactive_grid`` (C9,
proposed by E6; W20).

With it, saving without the version that was read is refused: 428 in the
API, a form error in the classic CRUD. It needs ``optimistic_lock`` (the
schema check refuses it alone), and off it changes nothing.
"""
from django.test import override_settings

from demoapp.models import Product
from djgentelella.designs import engine, factories, grid
from djgentelella.designs.data_components import InlineObjectManagementComponent
from djgentelella.locking import object_version
from djgentelella.tests.CrudClassicLock_Test import crud
from djgentelella.tests.Designs_Test import design
from djgentelella.tests.DesignsData_Test import (
    ALL_PRODUCT_PERMS, DataDesignTestCase, product_form, table,
)
from djgentelella.tests.InteractiveGrid_Test import grid_node

PROP = 'optimistic_lock_required'


@override_settings(LANGUAGE_CODE='en')
class LockRequiredPropTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.grant(*ALL_PRODUCT_PERMS)

    def payload(self, **changes):
        return {'name': 'Rye bread', 'price': '4.00', 'status': 'draft',
                'category': self.food.pk, **changes}

    def build(self, document, node_id):
        resolved, errors = engine.resolve(document)
        self.assertEqual([str(error) for error in errors], [])
        return resolved.nodes[node_id].build

    def test_the_schema(self):
        documents = (
            lambda **props: design(table(**props), forms=product_form()),
            crud,
            lambda **props: design(grid_node(**props)),
        )
        for make in documents:
            self.assertEqual(self.errors(make(optimistic_lock=True, **{PROP: True})),
                             [])
            self.assertEqual(self.errors(make(**{PROP: False})), [])
            errors = self.errors(make(**{PROP: 'yes'}))
            self.assertEqual(len(errors), 1)
            self.assertIn(PROP, errors[0])
            errors = self.errors(make(optimistic_lock=False, **{PROP: True}))
            self.assertEqual(len(errors), 1)
            self.assertIn('optimistic_lock_required needs optimistic_lock', errors[0])
        # Without the prop locking is off but for the grid, where it is on.
        self.assertEqual(len(self.errors(design(table(**{PROP: True}),
                                                forms=product_form()))), 1)
        self.assertEqual(len(self.errors(crud(**{PROP: True}))), 1)
        self.assertEqual(self.errors(design(grid_node(**{PROP: True}))), [])

    def test_the_inline_table_has_it(self):
        self.assertIn(PROP, InlineObjectManagementComponent.props_schema[
            'properties'])

    def test_object_management_answers_428_without_the_version(self):
        page = self.publish(design(table(optimistic_lock=True, **{PROP: True}),
                                   forms=product_form()), path='required')
        detail = self.api(page, 'products') + '%d/' % self.bread.pk
        response = self.post_json(detail, self.payload(), method='put')
        self.assertEqual(response.status_code, 428)
        self.assertEqual(response.json()['code'], 'version_required')
        self.assertEqual(Product.objects.get(pk=self.bread.pk).name, 'Bread')
        version = object_version(self.bread)
        response = self.post_json(detail, self.payload(_version=version),
                                  method='put')
        self.assertEqual(response.status_code, 200, response.content)

    def test_object_management_without_the_prop_as_before(self):
        build = self.build(design(table(optimistic_lock=True),
                                  forms=product_form()), 'products')
        self.assertFalse(build.optimistic_lock_required)
        self.assertFalse(factories.management_viewset_for(build)
                         .optimistic_lock_required)
        page = self.publish(design(table(optimistic_lock=True),
                                   forms=product_form()), path='optional')
        detail = self.api(page, 'products') + '%d/' % self.bread.pk
        response = self.post_json(detail, self.payload(), method='put')
        self.assertEqual(response.status_code, 200)

    def test_crud_classic_refuses_a_form_without_the_version(self):
        page = self.publish(crud(optimistic_lock=True, **{PROP: True}),
                            path='required-crud')
        url = self.api(page, 'products') + '%d/update/' % self.bread.pk
        build = self.build(crud(optimistic_lock=True, **{PROP: True}), 'products')
        self.assertTrue(factories.DesignCRUDView(build).optimistic_lock_required)
        response = self.client.post(url, self.payload())
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.version_conflict)
        self.assertEqual(form.non_field_errors().as_data()[0].code,
                         'version_required')
        self.assertEqual(Product.objects.get(pk=self.bread.pk).name, 'Bread')
        response = self.client.post(url, self.payload(
            _version=object_version(self.bread)))
        self.assertEqual(response.status_code, 302)

    def test_crud_classic_without_the_prop_as_before(self):
        page = self.publish(crud(optimistic_lock=True), path='optional-crud')
        url = self.api(page, 'products') + '%d/update/' % self.bread.pk
        response = self.client.post(url, self.payload())
        self.assertEqual(response.status_code, 302)

    def test_the_grid(self):
        build = self.build(design(grid_node(**{PROP: True})), 'grid')
        self.assertIsInstance(build, grid.InteractiveGridBuild)
        self.assertTrue(build.optimistic_lock_required)
        self.assertTrue(grid.grid_viewset_for(build).optimistic_lock_required)
        build = self.build(design(grid_node()), 'grid')
        self.assertFalse(build.optimistic_lock_required)
