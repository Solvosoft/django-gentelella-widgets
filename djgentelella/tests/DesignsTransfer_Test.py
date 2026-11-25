"""Pages and flows as data, and publishing for a Site (W20).

On 4faeda00 ``publishing.publish(document, site=...)`` validated the document
without the Site, so a ``flow:`` row link to a flow published only in that
Site was an error, and there was no public way to export or import a page or
a flow definition.
"""
from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured

from djgentelella.designs import publishing
from djgentelella.designs.models import Page
from djgentelella.flows import (
    export_definition, export_definitions, import_definition, publish_definition,
    validate_definition_data,
)
from djgentelella.flows.models import FlowDefinition
from djgentelella.tests.Designs_Test import design
from djgentelella.tests.DesignsData_Test import (
    DataDesignTestCase, product_form, table,
)
from djgentelella.tests.DesignsHooks_Test import product_flow


def flow_links_page():
    return design(table(row_links=[{'url_name': 'flow:tests.w20.review',
                                    'title': 'Review'}]), forms=product_form())


class PublishForASiteTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.site = Site.objects.create(domain='ventas.example.com', name='Ventas')
        publish_definition(product_flow('tests.w20.review'), site=self.site)

    def test_a_flow_of_the_site(self):
        # The reproduction: on 4faeda00 this answered "no flow
        # 'tests.w20.review'" and saved nothing.
        page, errors = publishing.publish(flow_links_page(), site=self.site,
                                          path='w20/flows')
        self.assertEqual(errors, [])
        self.assertEqual(page.site, self.site)

    def test_not_for_another_site_or_globally(self):
        other = Site.objects.create(domain='other.example.com', name='Other')
        for site in (None, other):
            page, errors = publishing.publish(flow_links_page(), site=site,
                                              path='w20/flows')
            self.assertIsNone(page)
            self.assertIn("no flow 'tests.w20.review'", str(errors[0]))
        self.assertFalse(Page.objects.filter(path='w20/flows').exists())

    def test_validate_takes_the_site(self):
        self.assertEqual(publishing.validate(flow_links_page(), site=self.site), [])
        self.assertEqual(publishing.validate(flow_links_page(), site=self.site.pk),
                         [])
        self.assertEqual(len(publishing.validate(flow_links_page())), 1)


class PageTransferTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.site = Site.objects.create(domain='ventas.example.com', name='Ventas')
        self.page = self.publish(design(table(), forms=product_form()),
                                 path='w20/products', site=self.site)
        self.page.permissions.set([Permission.objects.get(codename='view_product')])
        Page.objects.filter(pk=self.page.pk).update(title='Products!')
        self.page.refresh_from_db()

    def test_export(self):
        data = publishing.export_page(self.page)
        self.assertEqual(set(data), {'path', 'title', 'is_published', 'document',
                                     'permissions'})
        self.assertEqual(data['path'], 'w20/products')
        self.assertEqual(data['title'], 'Products!')
        self.assertTrue(data['is_published'])
        self.assertEqual(data['document'], self.page.document)
        self.assertEqual(data['permissions'], ['demoapp.view_product'])

    def test_a_round_trip_into_another_site(self):
        other = Site.objects.create(domain='other.example.com', name='Other')
        data = publishing.export_page(self.page)
        page, errors = publishing.import_page(data, site=other, user=self.user)
        self.assertEqual(errors, [])
        self.assertNotEqual(page.pk, self.page.pk)
        self.assertEqual(page.site, other)
        self.assertEqual(page.updated_by, self.user)
        page.refresh_from_db()
        self.assertEqual(publishing.export_page(page), data)

    def test_importing_again_replaces_the_page(self):
        data = publishing.export_page(self.page)
        data['title'] = 'Catalogue'
        data['is_published'] = False
        data['permissions'] = []
        page, errors = publishing.import_page(data, site=self.site)
        self.assertEqual(errors, [])
        self.assertEqual(page.pk, self.page.pk)
        page.refresh_from_db()
        self.assertEqual((page.title, page.is_published), ('Catalogue', False))
        self.assertFalse(page.permissions.exists())

    def test_without_permissions_those_of_the_document(self):
        data = publishing.export_page(self.page)
        del data['permissions']
        page, errors = publishing.import_page(data, site=self.site)
        self.assertEqual(errors, [])
        self.assertEqual(sorted(page.required_permissions()), sorted(
            publishing.format.view_permissions(page.document)))

    def assertErrors(self, data, *paths):
        page, errors = publishing.import_page(data, site=self.site)
        self.assertIsNone(page)
        self.assertEqual([error.path for error in errors], list(paths), errors)

    def test_nothing_is_saved_with_errors(self):
        data = publishing.export_page(self.page)
        before = list(Page.objects.values())
        self.assertErrors([], '$')
        self.assertErrors(dict(data, path='/a//b'), '$.path')
        self.assertErrors(dict(data, pk=3), '$.pk')
        self.assertErrors(dict(data, title=5), '$.title')
        self.assertErrors(dict(data, permissions=['demoapp.nothing']),
                          '$.permissions')
        self.assertErrors(dict(data, permissions='demoapp.view_product'),
                          '$.permissions')
        self.assertErrors({'path': 'x'}, '$.document')
        broken = dict(data, document=dict(data['document'], root={'type': 'nope'}))
        page, errors = publishing.import_page(broken, site=self.site)
        self.assertIsNone(page)
        self.assertTrue(errors)
        self.assertEqual(list(Page.objects.values()), before)


class FlowTransferTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.site = Site.objects.create(domain='ventas.example.com', name='Ventas')
        publish_definition(product_flow('tests.w20.one'), site=self.site)
        self.two = publish_definition(product_flow('tests.w20.two'), site=self.site)
        changed = product_flow('tests.w20.two')
        changed['title'] = 'Two, again'
        self.two_v2 = publish_definition(changed, site=self.site)
        publish_definition(product_flow('tests.w20.global'))

    def test_export(self):
        data = export_definition(self.two_v2)
        self.assertEqual(data, {'name': 'tests.w20.two',
                                'document': self.two_v2.document})
        self.assertEqual(data['document']['version'], 2)
        self.assertEqual([item['name'] for item in export_definitions(self.site)],
                         ['tests.w20.one', 'tests.w20.two'])
        self.assertEqual(export_definitions(self.site)[1]['document']['title'],
                         'Two, again')
        self.assertEqual([item['name'] for item in export_definitions()],
                         ['tests.w20.global'])

    def test_a_round_trip_into_another_site(self):
        other = Site.objects.create(domain='other.example.com', name='Other')
        for data in export_definitions(self.site):
            import_definition(data, other)
        self.assertEqual(
            [(item['name'], item['document'].get('title', ''))
             for item in export_definitions(other)],
            [('tests.w20.one', ''), ('tests.w20.two', 'Two, again')])

    def test_the_same_document_is_no_new_version(self):
        data = export_definition(self.two_v2)
        self.assertEqual(import_definition(data, self.site), self.two_v2)
        self.assertEqual(FlowDefinition.objects.filter(
            name='tests.w20.two', site=self.site).count(), 2)

    def test_a_changed_document_is_a_new_version(self):
        data = export_definition(self.two_v2)
        data['document'] = dict(data['document'], title='Three')
        definition = import_definition(data, self.site.pk)
        self.assertEqual(definition.version, 3)
        self.assertTrue(definition.is_active)
        self.two_v2.refresh_from_db()
        self.assertFalse(self.two_v2.is_active)

    def test_invalid_data(self):
        data = export_definition(self.two_v2)
        self.assertEqual([error.path for error in validate_definition_data([])],
                         ['$'])
        self.assertEqual([error.path for error in validate_definition_data(
            dict(data, name='tests.w20.other'))], ['$.document.name'])
        self.assertEqual([error.path for error in validate_definition_data(
            dict(data, extra=1))], ['$.extra'])
        broken = dict(data, document=dict(data['document'], initial='nowhere'))
        with self.assertRaises(ImproperlyConfigured):
            import_definition(broken, self.site)
        self.assertEqual(FlowDefinition.objects.filter(
            name='tests.w20.two', site=self.site).count(), 2)
