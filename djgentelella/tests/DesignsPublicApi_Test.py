"""The public API of djgentelella.designs for the tools built on it:
``parse_flow_link``, the ``row_link`` hook of the resolve context, the
conditions of a table evaluated per row and the condition hooks of
``CRUDView``."""

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase

from demoapp.models import Product
from djgentelella.authorization import authorization, set_flag
from djgentelella.cruds.base import CRUDMixin, CRUDView
from djgentelella.designs import data_components, engine
from djgentelella.designs.builds import ROW_ACTIONS, RowLink
from djgentelella.designs.components import ResolveContext
from djgentelella.designs.conditions import about_object, row_conditions
from djgentelella.designs.data_components import PK_PLACEHOLDERS, parse_flow_link
from djgentelella.tests.Designs_Test import design
from djgentelella.tests.DesignsData_Test import product_form, table
from djgentelella.tests.DesignsHooks_Test import (
    FOOD_ONLY, HooksTestCase, category_page, gtconfig,
)

FLAG = 'public_api'
OWNER = {'auth': 'tests.public.owner'}
TABLE = '$.root.children[0].children[0].children[0]'


@authorization('tests.public.owner')
def is_owner(request, obj=None):
    """Holds for the rows of the user: a condition about each row."""
    user = getattr(request, 'user', None)
    return obj is not None and user is not None and obj.owner_id == user.pk


class ParseFlowLinkTests(SimpleTestCase):
    def test_links(self):
        self.assertEqual(parse_flow_link('flow:sales.order'), ('sales.order', ''))
        self.assertEqual(parse_flow_link('flow:sales.order:approve'),
                         ('sales.order', 'approve'))
        self.assertEqual(parse_flow_link('flow:order:'), ('order', ''))
        self.assertEqual(parse_flow_link('flow:a:b:c'), ('a:b', 'c'))

    def test_what_is_not_a_flow_link(self):
        for text in ('flow:', 'flow::approve', 'page:sales', 'sales.order', '', None,
                     42):
            self.assertIsNone(parse_flow_link(text), text)

    def test_a_flow_name_with_a_colon(self):
        known = {'a:b'}.__contains__
        self.assertEqual(parse_flow_link('flow:a:b', known), ('a:b', ''))
        self.assertEqual(parse_flow_link('flow:a:b:go', known), ('a:b', 'go'))
        self.assertEqual(parse_flow_link('flow:x:go', known), ('x', 'go'))
        # Without a colon the name is not asked about.
        self.assertEqual(parse_flow_link('flow:x', lambda name: 1 / 0), ('x', ''))

    def test_public_names(self):
        for name in ('PK_PLACEHOLDERS', 'parse_flow_link', 'resolve_row_link',
                     'FLOW_PREFIX', 'PAGE_PREFIX'):
            self.assertIn(name, data_components.__all__)
        self.assertEqual(PK_PLACEHOLDERS[0], '987654321')


class GeneratedLinksContext(ResolveContext):
    """Links ``page:generated`` to a page the context knows about, and
    leaves the rest to the engine."""

    asked = None

    def row_link(self, link, model, path):
        type(self).asked = (link['url_name'], model, path)
        if link['url_name'] == 'page:generated':
            return RowLink(link['title'], 'fa fa-star', url_name='generated',
                           condition=link.get('condition'))
        return super().row_link(link, model, path)


class RowLinkHookTests(HooksTestCase):
    def document(self, *links):
        return design(table(row_links=list(links)), forms=product_form())

    def test_by_default_an_unknown_page_is_an_error(self):
        errors = self.errors(self.document({'url_name': 'page:generated',
                                            'title': 'Generated'}))
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith(TABLE + '.props.row_links[0]: '
                                             "'page:generated' is neither"))

    def test_an_overridden_hook(self):
        condition = {'flag': FLAG}
        document = self.document({'url_name': 'page:generated', 'title': 'Generated',
                                  'condition': condition})
        resolved, errors = engine.resolve(document, context=GeneratedLinksContext)
        self.assertEqual(errors, [])
        links = resolved.nodes['products'].build.row_links
        self.assertEqual(links, [RowLink('Generated', 'fa fa-star',
                                         url_name='generated', condition=condition)])

    def test_the_hook_can_leave_a_link_to_the_engine(self):
        document = self.document(
            {'url_name': 'page:generated', 'title': 'Generated'},
            {'url_name': 'page:nowhere', 'title': 'Nowhere'})
        _resolved, errors = engine.resolve(document, context=GeneratedLinksContext)
        self.assertEqual([str(error) for error in errors], [
            TABLE + ".props.row_links[1]: 'page:nowhere' is neither a URL name of "
            'the project that takes one pk, a design page ("page:<path>" or its '
            'meta.url_name) nor a flow ("flow:<name>")'])
        self.assertEqual(GeneratedLinksContext.asked,
                         ('page:nowhere', Product, TABLE + '.props.row_links[1]'))

    def test_the_condition_is_checked_before_the_hook(self):
        GeneratedLinksContext.asked = None
        document = self.document({'url_name': 'page:generated', 'title': 'Bad',
                                  'condition': {'perm': 42}})
        _resolved, errors = engine.resolve(document, context=GeneratedLinksContext)
        self.assertTrue(errors[0].path.startswith(TABLE + '.props.row_links[0]'
                                                  '.condition'))
        self.assertIsNone(GeneratedLinksContext.asked)


class AboutObjectTests(SimpleTestCase):
    def test_conditions_that_name_an_authorization(self):
        self.assertTrue(about_object(OWNER))
        self.assertTrue(about_object({'all': [{'perm': 'a.b'}, {'not': OWNER}]}))
        self.assertTrue(about_object({'any': [{'flag': 'x'}, OWNER]}))
        self.assertFalse(about_object({'all': [{'perm': 'a.b'}, {'flag': 'x'}]}))
        self.assertFalse(about_object({'not': {'group': 'x'}}))
        self.assertFalse(about_object(None))

    def test_only_the_actions_on_one_row(self):
        class Build:
            row_actions = ROW_ACTIONS
            action_conditions = {'create': OWNER, 'update': OWNER,
                                 'destroy': {'flag': 'x'}}
        self.assertEqual(row_conditions(Build), {'update': OWNER})
        Build.row_actions = ()
        self.assertEqual(row_conditions(Build), {})


class RowConditionTests(HooksTestCase):
    """``update``, ``destroy`` and ``retrieve`` conditions about the object
    are evaluated with each row."""

    def setUp(self):
        super().setUp()
        Product.objects.filter(pk=self.apple.pk).update(owner=self.user)
        self.document = design(
            table(list_fields=['name', 'price'],
                  action_conditions={'update': OWNER, 'destroy': OWNER,
                                     'retrieve': OWNER,
                                     'create': {'flag': FLAG}}),
            forms=product_form())
        self.page = self.publish(self.document, path='owned-rows')
        self.url = self.api(self.page, 'products')

    def test_each_row_says_what_it_allows(self):
        rows = {row['name']: row['actions']
                for row in self.client.get(self.url).json()['data']}
        self.assertEqual(rows['Apple'], {'destroy': True, 'update': True,
                                         'detail': True})
        self.assertEqual(rows['Bread'], {'destroy': False, 'update': False,
                                         'detail': False})
        self.assertEqual(rows['Hammer'], rows['Bread'])

    def test_the_page_keeps_the_modals_of_per_row_actions(self):
        config = gtconfig(self.page_content('owned-rows'), 'products')
        # create is not about a row: refused for the whole table.
        self.assertEqual(sorted(config['modal_ids']), ['destroy', 'detail', 'update'])

    def test_a_refused_row_is_a_403(self):
        bread = self.url + '%d/' % self.bread.pk
        self.assertEqual(self.client.get(bread).status_code, 403)
        self.assertEqual(self.client.get(bread + 'get_values_for_update/')
                         .status_code, 403)
        response = self.post_json(bread, {'name': 'Rye', 'price': '5.00',
                                          'status': 'active'}, method='put')
        self.assertEqual(response.status_code, 403)
        response = self.post_json(bread, {'name': 'Rye'}, method='patch')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.delete(bread).status_code, 403)
        self.bread.refresh_from_db()
        self.assertEqual(self.bread.name, 'Bread')
        # The detail template has no row: it is served.
        self.assertEqual(self.client.get(self.url + 'detail_template/').status_code,
                         200)

    def test_an_allowed_row_works(self):
        apple = self.url + '%d/' % self.apple.pk
        self.assertEqual(self.client.get(apple).json()['name'], 'Apple')
        response = self.post_json(apple, {'name': 'Green apple', 'price': '2.50',
                                          'status': 'active'}, method='put')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.client.delete(apple).status_code, 204)
        self.assertFalse(Product.objects.filter(pk=self.apple.pk).exists())

    def test_a_missing_row_is_still_a_404(self):
        self.assertEqual(self.client.get(self.url + '999999/').status_code, 404)

    def test_create_is_evaluated_once(self):
        response = self.post_json(self.url, {'name': 'Milk', 'price': '1.00',
                                             'status': 'active'})
        self.assertEqual(response.status_code, 403)
        set_flag(FLAG, True)
        response = self.post_json(self.url, {'name': 'Milk', 'price': '1.00',
                                             'status': 'active'})
        self.assertEqual(response.status_code, 201, response.content)


class InlineRowConditionTests(HooksTestCase):
    """An inline table evaluates the conditions of its row actions with the
    object of the page, not with each row."""

    def setUp(self):
        super().setUp()
        document = category_page()
        for item in document['root']['children'][0]['children'][0]['children']:
            if item['id'] == 'products':
                item['props']['action_conditions'] = {'update': FOOD_ONLY,
                                                      'destroy': FOOD_ONLY}
        self.page = self.publish(document)

    def rows(self, category):
        url = self.api(self.page, 'products', '%d/' % category.pk)
        return url, {row['name']: row['actions']
                     for row in self.client.get(url).json()['data']}

    def test_no_condition_is_per_row(self):
        build = engine.resolve_page(self.page)[0].nodes['products'].build
        self.assertTrue(build.inline)
        self.assertEqual(row_conditions(build), {})

    def test_the_parent_decides(self):
        # food_only holds for the category Food, never for a product.
        url, rows = self.rows(self.food)
        self.assertEqual(rows['Apple'], {'destroy': True, 'update': True,
                                         'detail': True})
        response = self.post_json(url + '%d/' % self.apple.pk,
                                  {'name': 'Green apple', 'price': '2.50',
                                   'status': 'active'}, method='put')
        self.assertEqual(response.status_code, 200, response.content)
        config = gtconfig(self.page_content(
            'category-products/%d' % self.food.pk), 'products')
        self.assertIn('update', config['modal_ids'])

    def test_refused_for_another_parent(self):
        config = gtconfig(self.page_content(
            'category-products/%d' % self.tools.pk), 'products')
        self.assertNotIn('update', config['modal_ids'])
        self.assertNotIn('destroy', config['modal_ids'])
        url = self.api(self.page, 'products', '%d/' % self.tools.pk)
        response = self.client.delete(url + '%d/' % self.hammer.pk)
        self.assertEqual(response.status_code, 403)


# -- the condition hooks of CRUDView ----------

class ProductCRUD(CRUDView):
    model = Product
    list_fields = ['name', 'price', 'status']
    display_fields = ['name', 'price', 'status']
    search_fields = ['name__icontains', 'price__icontains']
    column_conditions = {'price': {'flag': FLAG}}
    action_conditions = {'delete': {'flag': FLAG}, 'update': OWNER}


class OwnerMixin(CRUDMixin):
    """Evaluates the conditions with the object of the page (by its pk), and
    always hides ``status``."""

    def get_condition_object(self):
        pk = self.kwargs.get('pk')
        return Product.objects.filter(pk=pk).first() if pk else None

    def get_hidden_columns(self):
        return super().get_hidden_columns() | {'status'}


class OwnerProductCRUD(ProductCRUD):
    mixin = OwnerMixin


class CountingMixin(OwnerMixin):
    """Counts the calls of the condition object hook."""

    calls = 0

    def get_condition_object(self):
        CountingMixin.calls += 1
        return super().get_condition_object()


class CountingProductCRUD(ProductCRUD):
    mixin = CountingMixin


class CrudConditionHookTests(HooksTestCase):
    def setUp(self):
        super().setUp()
        Product.objects.filter(pk=self.apple.pk).update(owner=self.user)
        self.factory = RequestFactory()

    def request(self, path='/', method='get', data=None):
        request = getattr(self.factory, method)(path, data or {})
        request.user = self.user
        return request

    def test_hidden_columns_and_refused_pages(self):
        crud = ProductCRUD()
        response = crud.list(self.request(data={'q': '30'}))
        context = response.context_data
        self.assertEqual(list(context['fields']), ['name', 'status'])
        self.assertEqual(context['search'], ['name__icontains'])
        # "30" is only in the hidden price of the hammer: not searched.
        self.assertEqual(list(context['object_list']), [])
        self.assertFalse(context['crud_perms']['delete'])
        self.assertFalse(context['crud_perms']['update'])
        self.assertTrue(context['crud_perms']['detail'])
        detail = crud.detail(self.request(), pk=self.apple.pk).context_data
        self.assertEqual(list(detail['fields']), ['name', 'status'])
        response = crud.delete(self.request(), pk=self.apple.pk)
        self.assertEqual(response.status_code, 403)
        # Without an object the owner condition does not hold either.
        self.assertEqual(crud.update(self.request(), pk=self.apple.pk).status_code,
                         403)

    def test_shown_when_the_conditions_hold(self):
        set_flag(FLAG, True)
        crud = ProductCRUD()
        context = crud.list(self.request()).context_data
        self.assertEqual(list(context['fields']), ['name', 'price', 'status'])
        self.assertTrue(context['crud_perms']['delete'])
        self.assertEqual(crud.delete(self.request(), pk=self.apple.pk).status_code,
                         200)

    def test_the_hooks_of_a_mixin(self):
        crud = OwnerProductCRUD()
        response = crud.update(self.request(), pk=self.apple.pk)
        self.assertEqual(response.status_code, 200)
        form = response.context_data['form']
        # An update neither shows nor writes a hidden column.
        self.assertNotIn('price', form.fields)
        self.assertNotIn('status', form.fields)
        self.assertIn('name', form.fields)
        self.assertEqual(crud.update(self.request(), pk=self.bread.pk).status_code,
                         403)
        context = crud.list(self.request()).context_data
        self.assertEqual(list(context['fields']), ['name'])

    def test_the_condition_object_is_loaded_once_per_request(self):
        CountingMixin.calls = 0
        crud = CountingProductCRUD()
        response = crud.update(self.request(), pk=self.apple.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CountingMixin.calls, 1)
        crud.detail(self.request(), pk=self.apple.pk)
        self.assertEqual(CountingMixin.calls, 2)

    def test_a_hidden_column_is_not_the_order(self):
        class PriceOrdered(CRUDMixin):
            ordering = ['price', 'name']

        class Ordered(ProductCRUD):
            mixin = PriceOrdered
        queryset = Ordered().list(self.request()).context_data['object_list']
        self.assertEqual(list(queryset.query.order_by), ['name'])
        set_flag(FLAG, True)
        queryset = Ordered().list(self.request()).context_data['object_list']
        self.assertEqual(list(queryset.query.order_by), ['price', 'name'])

    def test_without_conditions_nothing_changes(self):
        class Plain(CRUDView):
            model = Product
            list_fields = ['name', 'price']
        crud = Plain()
        context = crud.list(self.request()).context_data
        self.assertEqual(list(context['fields']), ['name', 'price'])
        self.assertTrue(context['crud_perms']['delete'])

    def test_an_anonymous_user_is_sent_to_log_in(self):
        request = self.request()
        request.user = AnonymousUser()
        self.assertEqual(ProductCRUD().list(request).status_code, 302)
