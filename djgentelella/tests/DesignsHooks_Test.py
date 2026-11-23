"""The public hooks of the design engine: the ResolveContext hooks, a
resolve with an injected context and components, ``flow:`` row links, facets
over the targets of other components, the page context setting and the
conditions per column, action and row link."""

import json
import re
import warnings

from django.apps import apps
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.paginator import UnorderedObjectListWarning
from django.test import RequestFactory, override_settings
from django.urls import reverse

from djgentelella.authorization import authorization, set_flag
from djgentelella.designs import engine, publishing, registry
from djgentelella.designs.builds import FacetsBuild
from djgentelella.designs.components import ResolveContext, RuntimeComponent
from djgentelella.designs.data_components import FacetsComponent
from djgentelella.designs.exposure import Exposure, unexpose
from djgentelella.flows.definitions import publish_definition
from djgentelella.tests.Designs_Test import design, node
from djgentelella.tests.designs_fixtures.components import EchoComponent
from djgentelella.tests.DesignsData_Test import (
    ALL_PRODUCT_PERMS, DataDesignTestCase, load, product_form, table,
)

from demoapp.models import Product, ProductCategory

FLAG = 'hook_hooks'
CONDITION = {'flag': FLAG}
TABLE = '$.root.children[0].children[0].children[0]'


@authorization('tests.hooks.food_only')
def food_only(request, obj=None):
    """Holds only for the category called Food: a condition about an object."""
    return obj is not None and getattr(obj, 'name', None) == 'Food'


def gtconfig(content, node_id):
    """The JSON config a table writes in the page."""
    found = re.search(r'<script id="%s_gtconfig" type="application/json">(.*?)'
                      r'</script>' % re.escape(node_id), content, re.S)
    return json.loads(found.group(1)) if found else None


def page_context_hook(request, page):
    return {'breadcrumbs': [{'label': 'App <b>home</b>', 'href': '/app/'},
                            {'label': page.title, 'href': ''}],
            'content': 'replaced', 'hook_theme': 'dark'}


def bad_page_context_hook(request, page):
    return ['not', 'a', 'dict']


# These tests compare messages in English: the same text whether or not
# the Spanish catalog is compiled (the demo runs in 'es').
@override_settings(LANGUAGE_CODE='en')
class HooksTestCase(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        # Flags are cached: a test that set one must not leak it.
        cache.clear()
        self.grant(*ALL_PRODUCT_PERMS, 'demoapp.view_productcategory',
                   *['demoapp.%s_producttag' % action
                     for action in ('view', 'add', 'change', 'delete')])

    def page_content(self, path):
        response = self.client.get(reverse('gt-design-page', args=[path]))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()


# -- ResolveContext hooks ----------

class KnownPermissionsContext(ResolveContext):
    """Permissions read from a list, not from auth_permission."""

    known = {'fake.see_products'}

    def check_permissions(self, path, perms):
        self.checked = getattr(self, 'checked', []) + [(path, list(perms))]
        for perm in perms:
            if perm not in self.known:
                self.error(path, 'not in the list: %r' % perm)


class CustomLookupsContext(ResolveContext):
    def lookups(self, model):
        return ['hook_custom_lookup'] if model is ProductCategory else []


class EveryModelContext(ResolveContext):
    """Every model exposed with all its fields, like djgentelella-editor's."""

    def exposure(self, label, path=None):
        try:
            return Exposure(apps.get_model(label))
        except (LookupError, ValueError, AttributeError):
            if path is not None:
                self.error(path, 'unknown model %r' % (label,))
            return None


class NoCategoryContext(ResolveContext):
    """Product without its category field."""

    def exposure(self, label, path=None):
        found = super().exposure(label, path)
        if found is not None and found.model is Product:
            return Exposure(Product, exclude=('category',))
        return found


class ContextHookTests(HooksTestCase):
    def fake_perms(self):
        return design(table(perms={'list': ['fake.see_products']}),
                      forms=product_form(), permissions=['fake.see_products'])

    def test_check_permissions_can_be_overridden(self):
        document = self.fake_perms()
        errors = self.errors(document)
        self.assertIn("$.meta.permissions: unknown permission 'fake.see_products'",
                      errors)
        self.assertIn("%s.props.perms.list: unknown permission 'fake.see_products'"
                      % TABLE, errors)
        rctx = KnownPermissionsContext(document)
        resolved, errors = engine.resolve(document, context=rctx)
        # Only the permissions it does not know: every other check is its own.
        self.assertEqual(sorted({error.path for error in errors}),
                         ['%s.props.perms.%s' % (TABLE, action) for action in
                          sorted(['create', 'destroy', 'detail_template',
                                  'get_values_for_update', 'partial_update',
                                  'retrieve', 'update'])])
        self.assertIn(('$.meta.permissions', ['fake.see_products']), rctx.checked)
        KnownPermissionsContext.known = set(ALL_PRODUCT_PERMS) | {'fake.see_products'}
        try:
            resolved, errors = engine.resolve(document,
                                              context=KnownPermissionsContext)
        finally:
            KnownPermissionsContext.known = {'fake.see_products'}
        self.assertEqual(errors, [])
        self.assertEqual(resolved.nodes['products'].build.perms['list'],
                         ['fake.see_products'])

    def test_the_default_check_refuses_an_empty_list(self):
        rctx = ResolveContext(design())
        rctx.check_permissions('$.x', [])
        rctx.check_permissions('$.y', ['demoapp.view_product'])
        self.assertEqual([str(error) for error in rctx.errors],
                         ['$.x: cannot be empty: AllPermissionByAction refuses an '
                          'action without permissions'])

    def test_lookups_can_be_overridden(self):
        document = design(table(list_fields=['name', 'category']),
                          forms={'product_form': {
                              'model': 'demoapp.Product',
                              'fields': ['name', 'price', 'category'],
                              'widgets': {'category': 'AutocompleteSelect'}}})
        self.assertEqual(ResolveContext(document).lookups(Product), [])
        resolved, errors = engine.resolve(document, context=CustomLookupsContext)
        self.assertEqual(errors, [])
        build = resolved.nodes['products'].build
        self.assertEqual(build.lookups, {'category': 'hook_custom_lookup'})
        category = [item for item in build.form.fields if item.name == 'category'][0]
        self.assertEqual(category.lookup, 'hook_custom_lookup')
        # A lookup the project does not serve: the column just has no URL.
        request = RequestFactory().get('/')
        request.user = self.user
        response = engine.render(engine.resolve(document, preview=True,
                                                context=CustomLookupsContext)[0],
                                 request)
        self.assertEqual(response.status_code, 200)

    def test_exposure_without_a_path_only_asks(self):
        rctx = ResolveContext(design())
        self.assertIsNotNone(rctx.exposure('demoapp.Product'))
        self.assertIsNone(rctx.exposure('demoapp.Nothing'))
        self.assertIsNone(rctx.exposure(42))
        self.assertEqual(rctx.errors, [])

    def test_notifications_use_the_context_exposure(self):
        notify = [{'on': 'create', 'kind': 'notice', 'to': ['actor'],
                   'message': '{{ object.name }} added'},
                  {'on': 'update', 'kind': 'email', 'code': 'hook_product',
                   'subject': 'Changed', 'message': '{{ object.name }}',
                   'to': ['field:category.name']}]
        document = design(table(notify=notify), forms=product_form('name', 'price'))
        unexpose(Product)
        errors = self.errors(document)
        self.assertTrue(errors)
        self.assertTrue(all('not exposed' in error for error in errors), errors)
        # A context that exposes every model: the notifications resolve with
        # it instead of failing on the registered exposures.
        resolved, errors = engine.resolve(document, context=EveryModelContext)
        self.assertEqual(errors, [])
        self.assertEqual(resolved.nodes['products'].build.notify.events,
                         ['create', 'update'])

    def test_recipient_paths_follow_the_context_exposure(self):
        notify = [{'on': 'update', 'kind': 'email', 'code': 'hook_product',
                   'subject': 'Changed', 'message': '{{ object.name }}',
                   'to': ['field:category.name']}]
        document = design(table(notify=notify), forms=product_form('name', 'price'))
        self.assertEqual(self.errors(document), [])
        _resolved, errors = engine.resolve(document, context=NoCategoryContext)
        self.assertEqual([str(error) for error in errors], [
            "%s.props.notify[0].to: demoapp.Product has no field 'category.name' "
            "a design may use" % TABLE])


class HookEcho(EchoComponent):
    type = 'hook_echo'


class PublicResolveTests(HooksTestCase):
    def test_injected_components(self):
        document = design(node('hook_echo', 'hello', {'message': 'hi'}))
        self.assertEqual(self.errors(document), [
            "%s.type: unknown component type 'hook_echo'" % TABLE])
        components = {**registry.get_components(), 'hook_echo': HookEcho()}
        resolved, errors = engine.resolve(document, components=components)
        self.assertEqual(errors, [])
        self.assertIsInstance(resolved.nodes['hello'].component, HookEcho)
        # The registry is left as it was.
        self.assertNotIn('hook_echo', registry.get_components())

    def test_a_context_instance_keeps_what_it_collected(self):
        document = design(table(list_fields=['nothing']), forms=product_form())
        rctx = KnownPermissionsContext(document, preview=True)
        resolved, errors = engine.resolve(document, context=rctx)
        self.assertIsNone(resolved)
        self.assertIs(errors, rctx.errors)
        self.assertTrue(rctx.checked)
        self.assertEqual(rctx.components['page'].type, 'page')

    def test_the_page_renders_with_the_class_it_was_resolved_with(self):
        seen = []

        class Recording(ResolveContext):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                seen.append(self)

        resolved, errors = engine.resolve(design(node('html', 'a', {'html': 'x'})),
                                          context=Recording)
        self.assertEqual(errors, [])
        self.assertIs(resolved.context_class, Recording)
        request = RequestFactory().get('/')
        request.user = self.user
        engine.render(resolved, request)
        self.assertEqual(len(seen), 2)
        self.assertIs(seen[-1].resolved, resolved)

    def test_a_wrong_context_is_a_type_error(self):
        for wrong in (object, object(), 'ResolveContext'):
            with self.assertRaises(TypeError):
                engine.resolve(design(), context=wrong)

    def test_the_old_signature_still_works(self):
        resolved, errors = engine.resolve(design(table(), forms=product_form()),
                                          None, True, allow_templates=False,
                                          allow_js=False)
        self.assertEqual(errors, [])
        self.assertTrue(resolved.preview)
        self.assertIs(resolved.context_class, ResolveContext)


# -- flow: row links ----------

def product_flow(name='tests.hooks.review'):
    return {'schema_version': 2, 'name': name, 'model': 'demoapp.Product',
            'initial': 'new',
            'states': [{'id': 'new'}, {'id': 'ok', 'label': 'Approved'}],
            'transitions': [{'name': 'approve', 'source': 'new', 'target': 'ok'},
                            {'name': 'auto_ok', 'source': 'new', 'target': 'ok',
                             'auto': True}]}


class FlowRowLinkTests(HooksTestCase):
    def setUp(self):
        super().setUp()
        publish_definition(product_flow())
        publish_definition(product_flow('demoapp.hooksreview'))

    def links(self, *names):
        return [{'url_name': name, 'title': 'Go %d' % index}
                for index, name in enumerate(names)]

    def test_valid_flow_links(self):
        document = design(table(row_links=self.links(
            'flow:tests.hooks.review', 'flow:tests.hooks.review:approve',
            'flow:hooksreview')), forms=product_form())
        resolved, errors = engine.resolve(document)
        self.assertEqual(errors, [])
        links = resolved.nodes['products'].build.row_links
        self.assertEqual([(link.flow, link.transition) for link in links], [
            ('tests.hooks.review', ''), ('tests.hooks.review', 'approve'),
            ('demoapp.hooksreview', '')])
        self.publish(document, path='flow-links')
        config = gtconfig(self.page_content('flow-links'), 'products')
        self.assertEqual([link['url'] for link in config['row_links']], [
            reverse('flow_detail', args=['tests.hooks.review', '987654321']),
            reverse('flow_transition', args=['tests.hooks.review', 'approve',
                                             '987654321']),
            reverse('flow_detail', args=['demoapp.hooksreview', '987654321'])])
        self.assertEqual({link['placeholder'] for link in config['row_links']},
                         {'987654321'})
        # The link works for a row.
        url = config['row_links'][0]['url'].replace('987654321', str(self.apple.pk))
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_invalid_flow_links(self):
        document = design(table(row_links=self.links(
            'flow:tests.hooks.nothing', 'flow:tests.hooks.review:nothing',
            'flow:tests.hooks.review:auto_ok', 'flow:demoapp.CountryApprovalFlow',
            'flow:')), forms=product_form())
        errors = self.errors(document)
        where = TABLE + '.props.row_links[%d]: '
        self.assertEqual(errors, [
            where % 0 + "'flow:tests.hooks.nothing': no flow 'tests.hooks.nothing' "
                        "(djgentelella.flows)",
            where % 1 + "flow 'tests.hooks.review' has no transition 'nothing' a "
                        "user can run",
            where % 2 + "flow 'tests.hooks.review' has no transition 'auto_ok' a "
                        "user can run",
            where % 3 + "flow 'demoapp.CountryApprovalFlow' is about "
                        "demoapp.Country, not demoapp.Product",
            where % 4 + "'flow:': no flow '' (djgentelella.flows)"])

    def test_the_other_links_still_work(self):
        self.publish(load('category_products'))
        document = design(table(row_links=[
            {'url_name': 'page:category-products', 'title': 'Wrong model'}]),
            forms=product_form())
        self.assertIn('is not a page of one demoapp.Product',
                      self.errors(document)[0])


# -- facets over the targets of other components ----------

class HookReport(RuntimeComponent):
    """A node over a data source that facets may filter."""

    type = 'hook_report'
    facets_target = True
    props_schema = {'type': 'object', 'additionalProperties': False,
                    'properties': {'datasource': {'type': 'string'}}}

    def facets_source(self, node, rctx, path):
        name = (node.get('props') or {}).get('datasource')
        if not name:
            rctx.error(path, 'the report has no data source')
        return name


class HookNoFacets(HookReport):
    type = 'hook_no_facets'
    facets_target = False


class FacetTargetTests(HooksTestCase):
    def setUp(self):
        super().setUp()
        registry.register(HookReport)
        registry.register(HookNoFacets)
        self.grant('demoapp.view_purchaserequest')

    def facets(self, target='report', columns=('title', 'supplier'), **props):
        return node('facets', 'filters', {'target': target, 'columns': list(columns),
                                          **props})

    def test_a_declared_target(self):
        document = design(node('hook_report', 'report',
                               {'datasource': 'demoapp.purchases'}),
                          self.facets())
        resolved, errors = engine.resolve(document)
        self.assertEqual(errors, [])
        build = resolved.nodes['filters'].build
        self.assertIsInstance(build, FacetsBuild)
        self.assertEqual((build.datasource, build.columns, build.model),
                         ('demoapp.purchases', ['title', 'supplier'], None))
        self.assertEqual(resolved.nodes['filters'].component.endpoints(build), [])
        self.publish(document, path='report-facets')
        content = self.page_content('report-facets')
        self.assertIn('gtdesign-facets', content)
        self.assertIn(reverse('gtdatasource', kwargs={'name': 'demoapp.purchases'}),
                      content)
        self.assertIn('gtdesign:report', content)
        # Without the data source's permission the panel says so.
        self.user.user_permissions.remove(
            *self.user.user_permissions.filter(codename='view_purchaserequest'))
        self.client.force_login(User.objects.get(pk=self.user.pk))
        self.assertNotIn('gtdesign:report', self.page_content('report-facets'))

    def test_targets_that_cannot_be_filtered(self):
        cases = [
            (node('hook_no_facets', 'report', {'datasource': 'demoapp.purchases'}),
             'is not the id of a table'),
            (node('hook_report', 'report', {}), 'the report has no data source'),
            (node('hook_report', 'report', {'datasource': 'hooks.nothing'}),
             "unknown data source 'hooks.nothing'"),
        ]
        for target, message in cases:
            errors = self.errors(design(target, self.facets()))
            self.assertTrue(any(message in error for error in errors),
                            (message, errors))
        errors = self.errors(design(
            node('hook_report', 'report', {'datasource': 'demoapp.purchases'}),
            self.facets(columns=['title', 'nothing'])))
        self.assertEqual(errors, ["$.root.children[0].children[0].children[1]"
                                  ".props.columns: 'nothing' cannot have a facet"])

    def test_the_error_lists_the_declared_targets(self):
        errors = self.errors(design(self.facets(target='missing')))
        self.assertIn('hook_report', errors[0])
        self.assertNotIn('hook_no_facets', errors[0])

    def test_tables_still_work(self):
        self.assertEqual(self.errors(load('product_admin')), [])


# -- the page context ----------

class PageContextTests(HooksTestCase):
    def setUp(self):
        super().setUp()
        self.publish(design(node('html', 'a', {'html': '<p>the content</p>'})),
                     path='themed')

    def test_nothing_by_default(self):
        response = self.client.get(reverse('gt-design-page', args=['themed']))
        self.assertNotIn('gt-breadcrumb', response.content.decode())
        self.assertNotIn('hook_theme', response.context)
        self.assertEqual(response.context['base_template'], 'gentelella/base.html')

    @override_settings(GT_DESIGNS_PAGE_CONTEXT='djgentelella.tests.DesignsHooks_Test.'
                                               'page_context_hook')
    def test_the_hook_adds_to_the_context(self):
        response = self.client.get(reverse('gt-design-page', args=['themed']))
        content = response.content.decode()
        self.assertEqual(response.context['hook_theme'], 'dark')
        self.assertIn('gt-breadcrumb', content)
        # Escaped, as any context value.
        self.assertIn('App &lt;b&gt;home&lt;/b&gt;', content)
        # It cannot replace what the page is.
        self.assertIn('the content', content)
        self.assertNotIn('replaced', content)

    @override_settings(GT_DESIGNS_PAGE_CONTEXT=lambda request, page: {
        'base_template': 'gentelella/base_site.html'})
    def test_the_hook_can_change_the_layout(self):
        response = self.client.get(reverse('gt-design-page', args=['themed']))
        self.assertIn('gentelella/base_site.html',
                      [template.name for template in response.templates])

    @override_settings(GT_DESIGNS_BASE_TEMPLATE='gentelella/base_site.html')
    def test_the_base_template_setting(self):
        response = self.client.get(reverse('gt-design-page', args=['themed']))
        self.assertIn('gentelella/base_site.html',
                      [template.name for template in response.templates])
        self.assertIn('the content', response.content.decode())

    @override_settings(GT_DESIGNS_PAGE_CONTEXT='djgentelella.tests.DesignsHooks_Test.'
                                               'bad_page_context_hook')
    def test_a_hook_that_returns_no_dict(self):
        with self.assertRaises(ImproperlyConfigured):
            self.client.get(reverse('gt-design-page', args=['themed']))


# -- conditions inside the components ----------

class TableConditionTests(HooksTestCase):
    def setUp(self):
        super().setUp()
        self.document = design(
            table(list_fields=['name', 'price', 'status'],
                  search_fields=['name'],
                  column_conditions={'price': CONDITION},
                  action_conditions={'destroy': CONDITION, 'create': CONDITION}),
            forms=product_form())
        self.page = self.publish(self.document, path='conditional-table')
        self.url = self.api(self.page, 'products')

    def rows(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['data']

    def test_hidden_column_and_refused_actions(self):
        config = gtconfig(self.page_content('conditional-table'), 'products')
        self.assertEqual([column['name'] for column in config['columns']],
                         ['name', 'status'])
        self.assertEqual(sorted(config['modal_ids']), ['detail', 'update'])
        rows = self.rows()
        self.assertTrue(rows)
        self.assertTrue(all('price' not in row for row in rows))
        self.assertTrue(all(row['actions'] == {'destroy': False, 'update': True,
                                               'detail': True} for row in rows))
        detail = self.client.get(self.url + '%d/' % self.apple.pk).json()
        self.assertNotIn('price', detail)
        self.assertEqual(detail['name'], 'Apple')
        # Nor in the values of the update form (HiddenColumnUpdateTests).
        values = self.client.get(self.url + '%d/get_values_for_update/'
                                 % self.apple.pk).json()
        self.assertNotIn('price', values)
        template = self.client.get(self.url + 'detail_template/').json()['template']
        self.assertNotIn('Price', template)
        # Not filtered, searched nor ordered by.
        self.assertEqual(len(self.rows(price='30.00')), 3)
        self.assertEqual([row['name'] for row in self.rows(ordering='-price')],
                         [row['name'] for row in self.rows()])
        response = self.client.get(self.url, {'gtfilters': json.dumps(
            [{'column': 'price', 'op': 'gt', 'value': 10}])})
        self.assertEqual(response.status_code, 400)
        # Refused actions are 403s.
        response = self.post_json(self.url, {'name': 'Milk', 'price': '1.00',
                                             'status': 'active'})
        self.assertEqual(response.status_code, 403)
        response = self.client.delete(self.url + '%d/' % self.apple.pk)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.apple.pk).exists())
        response = self.post_json(self.url + '%d/' % self.apple.pk,
                                  {'name': 'Apple', 'price': '3.00',
                                   'status': 'active'}, method='put')
        self.assertEqual(response.status_code, 200, response.content)

    def test_shown_when_the_conditions_hold(self):
        set_flag(FLAG, True)
        config = gtconfig(self.page_content('conditional-table'), 'products')
        self.assertEqual([column['name'] for column in config['columns']],
                         ['name', 'price', 'status'])
        self.assertEqual(sorted(config['modal_ids']),
                         ['create', 'destroy', 'detail', 'update'])
        self.assertEqual(self.rows()[0]['actions']['destroy'], True)
        self.assertEqual(len(self.rows(price='30.00')), 1)
        self.assertEqual(self.rows(ordering='-price')[0]['name'], 'Hammer')
        response = self.client.delete(self.url + '%d/' % self.apple.pk)
        self.assertEqual(response.status_code, 204)
        response = self.post_json(self.url, {'name': 'Milk', 'price': '1.00',
                                             'status': 'active'})
        self.assertEqual(response.status_code, 201, response.content)

    def test_refused_detail(self):
        document = design(table(action_conditions={'retrieve': CONDITION}),
                          forms=product_form())
        page = self.publish(document, path='no-detail')
        url = self.api(page, 'products')
        self.assertEqual(self.client.get(url + '%d/' % self.apple.pk).status_code,
                         403)
        self.assertEqual(self.client.get(url + 'detail_template/').status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_invalid_conditions(self):
        props = TABLE + '.props'
        errors = self.errors(design(table(action_conditions={'list': CONDITION}),
                                    forms=product_form()))
        self.assertEqual(errors, [props + '.action_conditions.list: unexpected '
                                          'property'])
        errors = self.errors(design(table(
            list_fields=['name'],
            column_conditions={'price': CONDITION, 'name': {'perm': 42}},
            row_links=[{'url_name': 'flow:x', 'title': 'x',
                        'condition': {'nothing': 1}}]), forms=product_form()))
        self.assertIn(props + ".column_conditions.price: 'price' is not a column of "
                      "this component (name)", errors)
        self.assertTrue(any(error.startswith(props + '.column_conditions.name')
                            for error in errors), errors)
        self.assertTrue(any(error.startswith(props + '.row_links[0].condition')
                            for error in errors), errors)

    def test_row_link_conditions(self):
        self.publish(load('category_products'))
        document = design(
            node('object_management', 'categories', {
                'model': 'demoapp.ProductCategory', 'form': 'category_form',
                'row_links': [
                    {'url_name': 'category_products', 'title': 'Always'},
                    {'url_name': 'category_products', 'title': 'Flagged',
                     'condition': CONDITION}]}),
            forms={'category_form': {'model': 'demoapp.ProductCategory',
                                     'fields': ['name']}})
        self.grant('demoapp.add_productcategory', 'demoapp.change_productcategory',
                   'demoapp.delete_productcategory')
        self.publish(document, path='categories')
        config = gtconfig(self.page_content('categories'), 'categories')
        self.assertEqual([link['title'] for link in config['row_links']], ['Always'])
        set_flag(FLAG, True)
        config = gtconfig(self.page_content('categories'), 'categories')
        self.assertEqual([link['title'] for link in config['row_links']],
                         ['Always', 'Flagged'])

    def test_facets_of_a_hidden_column(self):
        document = design(
            table(list_fields=['name', 'status'],
                  column_conditions={'status': CONDITION}),
            node('facets', 'facets', {'target': 'products',
                                      'columns': ['status', 'category']}),
            forms=product_form())
        page = self.publish(document, path='hidden-facet')
        url = self.api(page, 'facets')
        content = self.page_content('hidden-facet')
        self.assertIn('data-columns="category"', content)
        description = self.client.get(url).json()
        self.assertEqual([column['name'] for column in description['columns']],
                         ['category'])
        self.assertEqual(self.client.get(url + 'facets/', {'columns': 'status'})
                         .status_code, 400)
        self.assertEqual(list(self.client.get(url + 'facets/').json()), ['category'])
        set_flag(FLAG, True)
        self.assertIn('data-columns="status,category"',
                      self.page_content('hidden-facet'))
        self.assertEqual(sorted(self.client.get(url + 'facets/').json()),
                         ['category', 'status'])


# English labels are asserted: the demo runs in Spanish once its .mo, which is
# not versioned, is compiled, and a local run would disagree with CI.
@override_settings(LANGUAGE_CODE='en')
class CrudConditionTests(HooksTestCase):
    def setUp(self):
        super().setUp()
        self.page = self.publish(design(node('crud_classic', 'products', {
            'model': 'demoapp.Product', 'form': 'product_form',
            'list_fields': ['name', 'price'], 'search_fields': ['name'],
            'column_conditions': {'price': CONDITION, 'status': CONDITION},
            'action_conditions': {'delete': CONDITION}}), forms=product_form()),
            path='conditional-crud')
        self.base = self.api(self.page, 'products')

    def test_hidden_column_and_refused_page(self):
        content = self.page_content('conditional-crud')
        self.assertIn('Apple', content)
        self.assertNotIn('<th>Price</th>', content)
        self.assertNotIn('2.00', content)
        self.assertNotIn('/delete/', content)
        detail = self.client.get(self.base + '%d/' % self.apple.pk).content.decode()
        self.assertIn('Apple', detail)
        self.assertNotIn('<th>Price</th>', detail)
        self.assertNotIn('<th>Status</th>', detail)
        delete = self.base + '%d/delete/' % self.apple.pk
        self.assertEqual(self.client.get(delete).status_code, 403)
        self.assertEqual(self.client.post(delete).status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.apple.pk).exists())

    def test_an_update_neither_shows_nor_writes_a_hidden_column(self):
        update = self.base + '%d/update/' % self.apple.pk
        content = self.client.get(update).content.decode()
        self.assertIn('Apple', content)
        self.assertNotIn('name="price"', content)
        self.assertNotIn('name="status"', content)
        response = self.client.post(update, {'name': 'Green apple',
                                             'price': '1.11', 'status': 'retired'})
        self.assertEqual(response.status_code, 302)
        self.apple.refresh_from_db()
        self.assertEqual(self.apple.name, 'Green apple')
        self.assertNotEqual(str(self.apple.price), '1.11')
        self.assertNotEqual(self.apple.status, 'retired')
        set_flag(FLAG, True)
        self.assertIn('name="price"', self.client.get(update).content.decode())

    def test_a_hidden_column_is_not_searched(self):
        self.publish(design(node('crud_classic', 'products', {
            'model': 'demoapp.Product', 'form': 'product_form',
            'list_fields': ['name', 'status'], 'search_fields': ['name'],
            'column_conditions': {'name': CONDITION}}), forms=product_form()),
            path='hidden-search')
        url = reverse('gt-design-page', args=['hidden-search'])
        content = self.client.get(url, {'q': 'Apple'}).content.decode()
        # Not searched: every row is listed, and no name is shown.
        self.assertEqual(content.count('/update/'), 3)
        self.assertNotIn('Hammer', content)
        set_flag(FLAG, True)
        content = self.client.get(url, {'q': 'Apple'}).content.decode()
        self.assertEqual(content.count('/update/'), 1)
        self.assertIn('Apple', content)

    def test_the_rows_keep_their_order_when_a_column_shows(self):
        self.publish(design(node('crud_classic', 'products', {
            'model': 'demoapp.Product', 'form': 'product_form',
            'list_fields': ['name', 'status'],
            'column_conditions': {'name': CONDITION}}), forms=product_form()),
            path='ordered-crud')
        url = reverse('gt-design-page', args=['ordered-crud'])

        def rows():
            # Product has no Meta.ordering: unordered, paginating would warn.
            with warnings.catch_warnings():
                warnings.simplefilter('error', UnorderedObjectListWarning)
                content = self.client.get(url).content.decode()
            return re.findall(r'/(\d+)/update/', content)

        hidden = rows()
        set_flag(FLAG, True)
        self.assertEqual(rows(), hidden)
        self.assertEqual(hidden, sorted(hidden, key=int, reverse=True))

    def test_shown_when_the_conditions_hold(self):
        set_flag(FLAG, True)
        content = self.page_content('conditional-crud')
        self.assertIn('<th>Price</th>', content)
        self.assertIn('/delete/', content)
        detail = self.client.get(self.base + '%d/' % self.apple.pk).content.decode()
        self.assertIn('<th>Status</th>', detail)
        delete = self.base + '%d/delete/' % self.apple.pk
        self.assertEqual(self.client.get(delete).status_code, 200)

    def test_invalid_conditions(self):
        errors = self.errors(design(node('crud_classic', 'products', {
            'model': 'demoapp.Product', 'form': 'product_form',
            'column_conditions': {'owner': CONDITION}}), forms=product_form()))
        self.assertEqual(errors, [
            TABLE + ".props.column_conditions.owner: 'owner' is not a column of "
                    "this component (name, price, status, category)"])
        errors = self.errors(design(node('crud_classic', 'products', {
            'model': 'demoapp.Product', 'action_conditions': {'list': CONDITION}})))
        self.assertEqual(errors, [
            TABLE + '.props.action_conditions.list: unexpected property'])


class ObjectConditionTests(HooksTestCase):
    """The conditions of a page about one object hold that object."""

    def setUp(self):
        super().setUp()
        document = load('category_products')
        for item in self.walk(document['root']):
            if item['id'] == 'products':
                item['props']['condition'] = {'auth': 'tests.hooks.food_only'}
                item['props']['action_conditions'] = {
                    'create': {'auth': 'tests.hooks.food_only'}}
        self.page = self.publish(document)

    def walk(self, item):
        yield item
        for child in item.get('children') or []:
            yield from self.walk(child)

    def test_the_condition_gets_the_parent(self):
        food = self.page_content('category-products/%d' % self.food.pk)
        food_url = self.api(self.page, 'products', '%d/' % self.food.pk)
        self.assertIn('"list_url": "%s"' % food_url, food)
        self.assertEqual(self.client.get(food_url).status_code, 200)
        response = self.post_json(food_url, {'name': 'Milk', 'price': '1.00',
                                             'status': 'active'})
        self.assertEqual(response.status_code, 201, response.content)

        tools = self.page_content('category-products/%d' % self.tools.pk)
        tools_url = self.api(self.page, 'products', '%d/' % self.tools.pk)
        self.assertNotIn('"list_url"', tools)
        self.assertEqual(self.client.get(tools_url).status_code, 404)
        response = self.post_json(tools_url, {'name': 'Saw', 'price': '9.00',
                                              'status': 'active'})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Product.objects.filter(name='Saw').exists())

    def test_without_a_parent_pk_it_does_not_hold(self):
        url = self.api(self.page, 'products', 'x/')
        self.assertEqual(self.client.get(url).status_code, 404)
        resolved, _errors = engine.resolve_page(self.page)
        self.assertIs(resolved.parent_model, ProductCategory)
        self.assertFalse(resolved.node_visible('products', None))
        self.assertTrue(resolved.node_visible('products', None, self.food))


class FacetsComponentApiTests(HooksTestCase):
    """What other components build on stays importable and callable."""

    def test_the_component_api(self):
        component = FacetsComponent()
        self.assertFalse(component.facets_target)
        self.assertIsNone(RuntimeComponent().facets_source({}, None, '$'))
        rctx = ResolveContext(design())
        self.assertEqual(rctx.component('facets').type, 'facets')
        self.assertIsNone(rctx.component('hook_nothing'))


# -- correction round: the page and the API decide the same ----------

FOOD_ONLY = {'auth': 'tests.hooks.food_only'}


def category_page(*nodes):
    """The demo page about one category, with ``nodes`` after its own."""
    document = load('category_products')
    body = document['root']['children'][0]['children'][0]
    body['children'].extend(nodes)
    document['forms'] = {**(document.get('forms') or {}), **product_form()}
    return document


class ObjectPageEndpointTests(HooksTestCase):
    """On a page about one object, a node whose endpoints do not carry the
    object is evaluated without it: on the page and in its API alike."""

    def food_page(self):
        return self.page_content('category-products/%d' % self.food.pk)

    def test_the_parent_model_follows_the_context_exposure(self):
        document = load('category_products')
        unexpose(ProductCategory)
        # Not registered, but the context exposes it.
        resolved, errors = engine.resolve(document, context=EveryModelContext)
        self.assertEqual(errors, [])
        self.assertIs(resolved.parent_model, ProductCategory)

    def test_which_nodes_take_the_parent(self):
        page = self.publish(category_page(
            table('allprod'), node('chart', 'chart', {
                'model': 'demoapp.Product', 'group_by': 'status'})))
        resolved, _errors = engine.resolve_page(page)
        self.assertTrue(resolved.takes_parent('products'))
        self.assertTrue(resolved.takes_parent('back'))
        self.assertTrue(resolved.takes_parent('body'))
        self.assertFalse(resolved.takes_parent('allprod'))
        self.assertFalse(resolved.takes_parent('chart'))
        self.assertIs(resolved.condition_object('products', self.food), self.food)
        self.assertIsNone(resolved.condition_object('allprod', self.food))

    def test_a_node_condition_about_the_object(self):
        allprod = table('allprod')
        allprod['props']['condition'] = FOOD_ONLY
        chart = node('chart', 'chart', {'model': 'demoapp.Product',
                                        'group_by': 'status',
                                        'condition': FOOD_ONLY})
        page = self.publish(category_page(allprod, chart))
        content = self.food_page()
        # The inline table, whose API knows the category, is there.
        self.assertIn(self.api(page, 'products', '%d/' % self.food.pk), content)
        # The others are not: their API could not check the condition.
        self.assertIsNone(gtconfig(content, 'allprod'))
        self.assertNotIn(self.api(page, 'allprod'), content)
        self.assertNotIn(self.api(page, 'chart'), content)
        self.assertEqual(self.client.get(self.api(page, 'allprod')).status_code, 404)
        self.assertEqual(self.client.get(self.api(page, 'chart')).status_code, 404)

    def test_a_condition_without_the_object_still_works(self):
        allprod = table('allprod')
        allprod['props']['condition'] = CONDITION
        page = self.publish(category_page(allprod))
        self.assertIsNone(gtconfig(self.food_page(), 'allprod'))
        self.assertEqual(self.client.get(self.api(page, 'allprod')).status_code, 404)
        set_flag(FLAG, True)
        self.assertIsNotNone(gtconfig(self.food_page(), 'allprod'))
        self.assertEqual(self.client.get(self.api(page, 'allprod')).status_code, 200)

    def test_an_ancestor_condition_about_the_object(self):
        box = node('row', 'box', children=[node('col', 'inner', {
            'width': 12, 'condition': FOOD_ONLY}, [
                node('html', 'note', {'html': '<p>food-note</p>'}),
                table('allprod')])])
        page = self.publish(category_page(box))
        content = self.food_page()
        self.assertIn('food-note', content)
        self.assertIsNone(gtconfig(content, 'allprod'))
        self.assertEqual(self.client.get(self.api(page, 'allprod')).status_code, 404)
        tools = self.page_content('category-products/%d' % self.tools.pk)
        self.assertNotIn('food-note', tools)

    def test_action_and_column_conditions_about_the_object(self):
        page = self.publish(category_page(table(
            'allprod', list_fields=['name', 'price'],
            column_conditions={'price': FOOD_ONLY},
            action_conditions={'create': FOOD_ONLY})))
        config = gtconfig(self.food_page(), 'allprod')
        self.assertNotIn('create', config['modal_ids'])
        self.assertEqual([column['name'] for column in config['columns']], ['name'])
        url = self.api(page, 'allprod')
        response = self.post_json(url, {'name': 'Milk', 'price': '1.00',
                                        'status': 'active'})
        self.assertEqual(response.status_code, 403)
        rows = self.client.get(url).json()['data']
        self.assertTrue(rows)
        self.assertTrue(all('price' not in row for row in rows))

    def test_inline_conditions_still_get_the_object(self):
        document = category_page()
        for item in document['root']['children'][0]['children'][0]['children']:
            if item['id'] == 'products':
                item['props']['action_conditions'] = {'create': FOOD_ONLY}
                item['props']['column_conditions'] = {'price': FOOD_ONLY}
        page = self.publish(document)
        config = gtconfig(self.food_page(), 'products')
        self.assertIn('create', config['modal_ids'])
        self.assertIn('price', [column['name'] for column in config['columns']])
        url = self.api(page, 'products', '%d/' % self.food.pk)
        rows = self.client.get(url).json()['data']
        self.assertTrue(all('price' in row for row in rows))
        tools = gtconfig(self.page_content('category-products/%d' % self.tools.pk),
                         'products')
        self.assertNotIn('create', tools['modal_ids'])

    def test_a_classic_crud_on_an_object_page(self):
        page = self.publish(category_page(node('crud_classic', 'crud', {
            'model': 'demoapp.Product', 'form': 'product_form',
            'list_fields': ['name', 'price'],
            'column_conditions': {'price': FOOD_ONLY},
            'action_conditions': {'delete': FOOD_ONLY}})))
        content = self.food_page()
        self.assertIn('Apple', content)
        self.assertNotIn('<th>Price</th>', content)
        self.assertNotIn('/delete/', content)
        delete = self.api(page, 'crud', '%d/delete/' % self.apple.pk)
        self.assertEqual(self.client.get(delete).status_code, 403)


class HiddenColumnUpdateTests(HooksTestCase):
    """A hidden column that is a field of the form is not read nor written by
    an update; creating a row still takes it."""

    def setUp(self):
        super().setUp()
        self.page = self.publish(design(
            table(list_fields=['name', 'price', 'status'],
                  column_conditions={'price': CONDITION}),
            forms=product_form()), path='hidden-update')
        self.url = self.api(self.page, 'products')

    def test_the_update_form_and_api_leave_it_out(self):
        content = self.page_content('hidden-update')
        self.assertNotIn('name="products_update-price"', content)
        self.assertIn('name="products_update-name"', content)
        self.assertIn('name="products_create-price"', content)
        values = self.client.get(self.url + '%d/get_values_for_update/'
                                 % self.apple.pk).json()
        self.assertNotIn('price', values)
        self.assertEqual(values['name'], 'Apple')
        response = self.post_json(self.url + '%d/' % self.apple.pk,
                                  {'name': 'Green apple', 'price': '9.00',
                                   'status': 'active'}, method='put')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn('price', response.json())
        response = self.post_json(self.url + '%d/' % self.apple.pk,
                                  {'price': '8.00'}, method='patch')
        self.assertEqual(response.status_code, 200, response.content)
        self.apple.refresh_from_db()
        self.assertEqual(self.apple.name, 'Green apple')
        self.assertEqual(str(self.apple.price), '2.00')
        response = self.post_json(self.url, {'name': 'Milk', 'price': '1.50',
                                             'status': 'active'})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(str(Product.objects.get(name='Milk').price), '1.50')

    def test_shown_it_is_edited(self):
        set_flag(FLAG, True)
        self.assertIn('name="products_update-price"',
                      self.page_content('hidden-update'))
        values = self.client.get(self.url + '%d/get_values_for_update/'
                                 % self.apple.pk).json()
        self.assertEqual(values['price'], '2.00')
        response = self.post_json(self.url + '%d/' % self.apple.pk,
                                  {'name': 'Apple', 'price': '9.00',
                                   'status': 'active'}, method='put')
        self.assertEqual(response.status_code, 200, response.content)
        self.apple.refresh_from_db()
        self.assertEqual(str(self.apple.price), '9.00')


class HiddenColumnOrderingTests(HooksTestCase):
    """The default order of the rows does not follow a hidden column."""

    def names(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        return [row['name'] for row in response.json()['data']]

    def test_the_table_ordering(self):
        page = self.publish(design(
            table(list_fields=['name', 'price'], ordering=['price'],
                  column_conditions={'price': CONDITION}),
            forms=product_form()), path='hidden-order')
        url = self.api(page, 'products')
        self.assertEqual(self.names(url), ['Hammer', 'Bread', 'Apple'])
        set_flag(FLAG, True)
        self.assertEqual(self.names(url), ['Apple', 'Bread', 'Hammer'])

    def test_a_shown_ordering_is_kept(self):
        page = self.publish(design(
            table(list_fields=['name', 'price'], ordering=['name', 'price'],
                  column_conditions={'price': CONDITION}),
            forms=product_form()), path='shown-order')
        self.assertEqual(self.names(self.api(page, 'products')),
                         ['Apple', 'Bread', 'Hammer'])

    def test_the_classic_crud_ordering(self):
        # ProductCategory is ordered by name: Aaa, Food, Tools.
        newest = ProductCategory.objects.create(name='Aaa')
        self.grant('demoapp.change_productcategory')
        self.publish(design(node('crud_classic', 'cats', {
            'model': 'demoapp.ProductCategory', 'list_fields': ['name', 'description'],
            'column_conditions': {'name': CONDITION}})), path='hidden-crud-order')

        def order():
            content = self.page_content('hidden-crud-order')
            return [int(pk) for pk in re.findall(r'/(\d+)/update/', content)]

        self.assertEqual(order(), [newest.pk, self.tools.pk, self.food.pk])
        set_flag(FLAG, True)
        self.assertEqual(order(), [newest.pk, self.food.pk, self.tools.pk])


class ExtraArgumentsContext(ResolveContext):
    """A context whose ``__init__`` takes one more argument."""

    def __init__(self, design, app_name, request=None, preview=False, **kwargs):
        super().__init__(design, request, preview, **kwargs)
        self.app_name = app_name


class ContextCopyTests(HooksTestCase):
    def test_render_copies_the_instance_it_was_resolved_with(self):
        document = design(node('html', 'a', {'html': 'x'}))
        rctx = ExtraArgumentsContext(document, 'sales')
        resolved, errors = engine.resolve(document, context=rctx)
        self.assertEqual(errors, [])
        self.assertIs(resolved.context, rctx)
        self.assertIs(resolved.context_class, ExtraArgumentsContext)
        request = RequestFactory().get('/')
        request.user = self.user
        response = engine.render(resolved, request)
        self.assertEqual(response.status_code, 200)
        # The resolving instance is left as it was.
        self.assertIsNone(rctx.request)
        self.assertIsNone(rctx.resolved)

    def test_copy_for(self):
        rctx = ExtraArgumentsContext(design(), 'sales')
        rctx.error('$', 'collected')
        request = RequestFactory().get('/')
        request.user = self.user
        clone = rctx.copy_for(request)
        self.assertIsInstance(clone, ExtraArgumentsContext)
        self.assertEqual(clone.app_name, 'sales')
        self.assertIs(clone.request, request)
        self.assertEqual(clone.user, self.user)
        self.assertEqual(clone.errors, [])
        self.assertEqual(len(rctx.errors), 1)

    def test_a_class_is_not_kept(self):
        resolved, _errors = engine.resolve(design(), context=ResolveContext)
        self.assertIsNone(resolved.context)
