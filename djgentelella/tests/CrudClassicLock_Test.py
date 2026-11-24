"""
The ``optimistic_lock`` prop of the ``crud_classic`` design component (W19):
the same prop as ``object_management``, validated by the schema, and the
generated CRUD gets ``CRUDView.optimistic_lock``. Off by default, and off
changes nothing.
"""
import re

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from demoapp.models import Product
from djgentelella.designs import engine, factories
from djgentelella.locking import OptimisticLockFormMixin, object_version
from djgentelella.tests.Designs_Test import design, node
from djgentelella.tests.DesignsData_Test import (
    ALL_PRODUCT_PERMS, DataDesignTestCase, product_form,
)
from djgentelella.tests.Locking_Test import without_csrf

DENY = {'auth': 'tests.locking.never'}


def crud(**props):
    return design(node('crud_classic', 'products', {
        'model': 'demoapp.Product', 'form': 'product_form', **props}),
        forms=product_form())


class CrudClassicLockTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.grant(*ALL_PRODUCT_PERMS)

    def page(self, path='locked-crud', **props):
        page = self.publish(crud(**props), path=path)
        return self.api(page, 'products')

    def update_url(self, base, product):
        return base + '%d/update/' % product.pk

    def payload(self, **changes):
        return {'name': 'Rye bread', 'price': '4.00', 'status': 'draft',
                'category': self.food.pk, **changes}

    def test_the_prop_is_validated(self):
        self.assertEqual(self.errors(crud(optimistic_lock=True)), [])
        self.assertEqual(self.errors(crud(optimistic_lock=False)), [])
        errors = self.errors(crud(optimistic_lock='yes'))
        self.assertEqual(len(errors), 1)
        self.assertIn('optimistic_lock', errors[0])

    def test_the_crud_view_gets_it(self):
        for props, expected in (({}, False), ({'optimistic_lock': False}, False),
                                ({'optimistic_lock': True}, True)):
            resolved, errors = engine.resolve(crud(**props))
            self.assertEqual(errors, [])
            build = resolved.nodes['products'].build
            self.assertIs(build.optimistic_lock, expected)
            self.assertIs(factories.DesignCRUDView(build).optimistic_lock, expected)

    def test_the_update_page_carries_the_version(self):
        base = self.page(optimistic_lock=True)
        response = self.client.get(self.update_url(base, self.bread))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="_version"')
        self.assertContains(response,
                            'value="%s"' % object_version(self.bread))

    def test_an_old_version_is_refused_and_the_current_saves(self):
        base = self.page(optimistic_lock=True)
        url = self.update_url(base, self.bread)
        version = object_version(self.bread)
        Product.objects.filter(pk=self.bread.pk).update(name='Whole bread')
        response = self.client.post(url, self.payload(_version=version))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].version_conflict)
        self.assertContains(response, 'gt-version-reload')
        self.assertContains(response, 'href="%s' % url)
        self.assertEqual(Product.objects.get(pk=self.bread.pk).name, 'Whole bread')
        current = object_version(Product.objects.get(pk=self.bread.pk))
        response = self.client.post(url, self.payload(_version=current))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Product.objects.get(pk=self.bread.pk).name, 'Rye bread')

    def test_the_page_condition_comes_before_the_version(self):
        base = self.page(optimistic_lock=True, action_conditions={'update': DENY})
        response = self.client.post(self.update_url(base, self.bread),
                                    self.payload(_version='old'))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Product.objects.get(pk=self.bread.pk).name, 'Bread')

    def test_off_by_default_changes_nothing(self):
        """Without the prop, or with it false, the update page and the number
        of queries of a save are the same; with it, the page only gains the
        hidden version."""
        def update_page():
            return without_csrf(self.client.get(url).content.decode())

        base = self.page(path='plain-crud')
        url = self.update_url(base, self.bread)
        response = self.client.get(url)
        self.assertNotContains(response, '_version')
        self.assertNotIn(OptimisticLockFormMixin,
                         type(response.context['form']).__mro__)
        plain = update_page()

        factories.clear_cache()
        self.page(path='plain-crud', optimistic_lock=False)
        self.assertEqual(update_page(), plain)
        factories.clear_cache()
        self.page(path='plain-crud', optimistic_lock=True)
        locked = update_page()
        hidden = re.compile(r'<input type="hidden" name="_version" value="[^"]*"[^>]*>')
        self.assertRegex(locked, hidden)
        self.assertEqual(re.sub(r'\s+', ' ', hidden.sub('', locked)),
                         re.sub(r'\s+', ' ', plain))

        def save_queries(name, **props):
            factories.clear_cache()
            self.page(path='plain-crud', **props)
            with CaptureQueriesContext(connection) as queries:
                # An old version is not even read when off.
                response = self.client.post(url, self.payload(name=name,
                                                              _version='old'))
            self.assertEqual(response.status_code, 302)
            self.assertEqual(Product.objects.get(pk=self.bread.pk).name, name)
            return [q['sql'] for q in queries.captured_queries]

        off = save_queries('Again')
        false = save_queries('Once more', optimistic_lock=False)
        self.assertEqual(len(false), len(off))
        self.assertFalse([q for q in off + false
                          if 'FOR UPDATE' in q or 'SAVEPOINT' in q])
