"""Authorization conditions on the components with data of the designs -- a
node hidden by a false
condition renders nothing and serves no endpoint, also on the page of one
object -- and the escaping of the sidebar menu."""

from django import forms
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.forms.renderers import get_default_renderer
from django.template import Context, Template
from django.test import RequestFactory, TestCase
from django.urls import reverse

from djgentelella.authorization import set_flag
from djgentelella.designs import engine
from djgentelella.forms.forms import GTForm
from djgentelella.models import MenuItem
from djgentelella.tests.Designs_Test import design, node
from djgentelella.tests.DesignsData_Test import (
    ALL_PRODUCT_PERMS, DataDesignTestCase, load, product_form, table,
)

FLAG = 'conditions_data'
CONDITION = {'flag': FLAG}


def with_condition(item, where='props'):
    """``item`` with the flag's condition in ``props`` or ``meta``."""
    item = dict(item)
    item[where] = {**(item.get(where) or {}), 'condition': CONDITION}
    return item


def find(document, node_id):
    stack = [document['root']]
    while stack:
        item = stack.pop()
        if item['id'] == node_id:
            return item
        stack.extend(item.get('children') or [])
    raise KeyError(node_id)


class ConditionalDataTestCase(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.grant(*ALL_PRODUCT_PERMS, 'demoapp.view_productcategory',
                   *['demoapp.%s_producttag' % action
                     for action in ('view', 'add', 'change', 'delete')])

    def page_content(self, path):
        response = self.client.get(reverse('gt-design-page', args=[path]))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()


class HiddenTableTests(ConditionalDataTestCase):
    """A table with a false condition: not in the page, its endpoints 404."""

    def setUp(self):
        super().setUp()
        self.page = self.publish(design(
            with_condition(table(list_fields=['name', 'price'])),
            forms=product_form()), path='hidden-table')
        self.urls = [self.api(self.page, 'products'),
                     self.api(self.page, 'products', '%d/' % self.apple.pk),
                     self.api(self.page, 'products', 'detail_template/')]

    def test_hidden_without_the_flag(self):
        content = self.page_content('hidden-table')
        self.assertNotIn('products_gtconfig', content)
        self.assertNotIn('gtdesign-table', content)
        for url in self.urls:
            self.assertIn(self.client.get(url).status_code, (403, 404), url)
        # Nor can it be written through.
        response = self.post_json(self.urls[0], {'name': 'Milk', 'price': '1.00',
                                                 'status': 'active'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.delete(self.urls[1]).status_code, 404)
        self.assertTrue(type(self.apple).objects.filter(pk=self.apple.pk).exists())

    def test_shown_with_the_flag(self):
        set_flag(FLAG, True)
        content = self.page_content('hidden-table')
        self.assertIn('products_gtconfig', content)
        self.assertEqual(self.client.get(self.urls[0]).status_code, 200)
        self.assertEqual(self.client.get(self.urls[1]).status_code, 200)

    def test_a_condition_of_an_ancestor_hides_it_too(self):
        document = design(table(), forms=product_form())
        document['root']['children'][0] = with_condition(
            document['root']['children'][0], 'meta')
        page = self.publish(document, path='hidden-row')
        self.assertNotIn('products_gtconfig', self.page_content('hidden-row'))
        self.assertEqual(self.client.get(self.api(page, 'products')).status_code, 404)
        set_flag(FLAG, True)
        self.assertIn('products_gtconfig', self.page_content('hidden-row'))
        self.assertEqual(self.client.get(self.api(page, 'products')).status_code, 200)


class EveryDataComponentTests(ConditionalDataTestCase):
    """Chart, stat, classic CRUD and facets: each one hidden by its condition
    renders nothing and its endpoint answers 404."""

    def setUp(self):
        super().setUp()
        self.page = self.publish(design(
            with_condition(node('chart', 'chart', {
                'model': 'demoapp.Product', 'group_by': 'status'})),
            with_condition(node('stat', 'stat', {
                'model': 'demoapp.Product', 'title': 'Counted products'}), 'meta'),
            with_condition(node('crud_classic', 'tags', {
                'model': 'demoapp.ProductTag', 'title': 'Tags'})),
            table('visible_table'),
            with_condition(node('facets', 'facets', {
                'target': 'visible_table', 'columns': ['status']})),
            forms=product_form()), path='every-component')
        self.endpoints = {
            'chart': self.api(self.page, 'chart'),
            'stat': self.api(self.page, 'stat'),
            'tags': self.api(self.page, 'tags'),
            'tags create': self.api(self.page, 'tags', 'create/'),
            'facets': self.api(self.page, 'facets'),
            'facets counts': self.api(self.page, 'facets', 'facets/'),
        }

    def test_hidden_without_the_flag(self):
        content = self.page_content('every-component')
        for marker in ('data-gtdesign="chart"', 'Counted products',
                       'gtdesign-crud-list', 'gtdesign-facets'):
            self.assertNotIn(marker, content)
        # The visible table is there.
        self.assertIn('visible_table_gtconfig', content)
        for name, url in self.endpoints.items():
            self.assertEqual(self.client.get(url).status_code, 404, name)
        response = self.client.post(self.endpoints['tags create'], {'name': 'x'})
        self.assertEqual(response.status_code, 404)

    def test_shown_with_the_flag(self):
        set_flag(FLAG, True)
        content = self.page_content('every-component')
        for marker in ('Counted products', 'gtdesign-crud-list', 'gtdesign-facets'):
            self.assertIn(marker, content)
        for name, url in self.endpoints.items():
            self.assertEqual(self.client.get(url).status_code, 200, name)


class FacetsOfAHiddenTableTests(ConditionalDataTestCase):
    """Facets without a condition of their own over a hidden table: they go
    with it, page and endpoint (``depends_on``)."""

    def setUp(self):
        super().setUp()
        document = load('product_admin')
        products = find(document, 'products')
        products.setdefault('props', {})['condition'] = CONDITION
        self.page = self.publish(document, path='products-hidden')
        self.url = self.api(self.page, 'product_facets')

    def test_the_facets_go_with_their_table(self):
        content = self.page_content('products-hidden')
        self.assertNotIn('gtdesign-facets', content)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.get(self.url + 'facets/').status_code, 404)
        resolved, _errors = engine.resolve_page(self.page)
        self.assertEqual(resolved.nodes['product_facets'].requires, (CONDITION,))
        set_flag(FLAG, True)
        self.assertIn('gtdesign-facets', self.page_content('products-hidden'))
        self.assertEqual(self.client.get(self.url + 'facets/').status_code, 200)


class ObjectPageConditionTests(ConditionalDataTestCase):
    """The page of one object (``designs/<path>/<parent pk>``) with a
    condition on its inline table."""

    def setUp(self):
        super().setUp()
        document = load('category_products')
        products = find(document, 'products')
        products['meta'] = {**(products.get('meta') or {}), 'condition': CONDITION}
        self.page = self.publish(document)
        self.path = 'category-products/%d' % self.food.pk
        self.url = self.api(self.page, 'products', '%d/' % self.food.pk)

    def test_hidden_without_the_flag(self):
        content = self.page_content(self.path)
        self.assertNotIn('"list_url": "%s"' % self.url, content)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        response = self.post_json(self.url, {'name': 'Milk', 'price': '1.00',
                                             'status': 'active'})
        self.assertEqual(response.status_code, 404)

    def test_shown_with_the_flag(self):
        set_flag(FLAG, True)
        content = self.page_content(self.path)
        self.assertIn('"list_url": "%s"' % self.url, content)
        names = sorted(row['name'] for row in self.client.get(self.url).json()['data'])
        self.assertEqual(names, ['Apple', 'Bread'])

    def test_the_parent_rules_still_apply(self):
        set_flag(FLAG, True)
        # An unknown parent is a 404 whatever the condition says.
        self.assertEqual(self.client.get(reverse('gt-design-page', args=[
            'category-products/999'])).status_code, 404)

    def test_a_condition_on_the_whole_object_page(self):
        document = load('category_products')
        document['root'] = with_condition(document['root'], 'meta')
        document['meta'] = {**document['meta'], 'url': 'category-items/',
                            'url_name': 'category_items'}
        page = self.publish(document, path='category-items')
        url = self.api(page, 'products', '%d/' % self.food.pk)
        content = self.page_content('category-items/%d' % self.food.pk)
        self.assertNotIn('"list_url"', content)
        self.assertEqual(self.client.get(url).status_code, 404)
        set_flag(FLAG, True)
        self.assertEqual(self.client.get(url).status_code, 200)


class MenuEscapingTests(TestCase):
    """Menu titles, links and icons come from the database: escaped."""

    XSS = '<img src=x onerror=alert(1)>'

    def render(self, tag):
        request = RequestFactory().get('/')
        request.user = AnonymousUser()
        template = Template('{% load gentelellamenu %}{% ' + tag + ' %}')
        return template.render(Context({'request': request}))

    def test_sidebar(self):
        root = MenuItem.objects.create(title=self.XSS, url_name='/root',
                                       category='sidebar', icon='fa" onclick="x')
        child = MenuItem.objects.create(title='child ' + self.XSS, parent=root,
                                        url_name='/c?a=1&b="2"', category='sidebar')
        MenuItem.objects.create(title='grandchild', parent=child, url_name='/g',
                                category='sidebar')
        html = self.render('sidebar_menu')
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', html)
        self.assertIn('child &lt;img', html)
        self.assertIn('href="/c?a=1&amp;b=&quot;2&quot;"', html)
        self.assertIn('class="fa&quot; onclick=&quot;x"', html)
        # The markup of the menu itself is not escaped.
        self.assertIn('<span class="fa fa-chevron-down"></span>', html)
        self.assertIn('aria-expanded="false"', html)

    def test_top_menu_and_footer(self):
        MenuItem.objects.create(title=self.XSS, url_name='/top', category='main')
        MenuItem.objects.create(title=self.XSS, url_name='/foot',
                                category='sidebarfooter', icon='fa fa-cog')
        for tag in ('top_menu', 'footer_sidebar_menu'):
            html = self.render(tag)
            self.assertNotIn('<img', html, tag)
            self.assertIn('&lt;img src=x onerror=alert(1)&gt;', html, tag)


class PlainForm(forms.Form):
    name = forms.CharField()


class GridForm(GTForm):
    name = forms.CharField()


class GTFormRendererTests(TestCase):
    """A GTForm picks its template per instance and leaves the renderer all
    forms share alone: set there, a design page with a grid form would make
    every plain form of the process render as an empty grid."""

    def test_the_shared_renderer_is_left_alone(self):
        renderer = get_default_renderer()
        before = renderer.form_template_name
        for render_type in ('as_grid', 'as_plain', 'as_inline', 'as_horizontal'):
            form = GridForm(render_type=render_type)
            self.assertEqual(form.template_name,
                             getattr(form, 'template_name_' + render_type[3:]))
        self.assertEqual(renderer.form_template_name, before)
        self.assertIn('name="name"', str(PlainForm()))
        self.assertEqual(GridForm().template_name, GTForm.template_name_horizontal)
        self.assertIn('name="name"', str(GridForm(render_type='as_plain')))


__all__ = ['HiddenTableTests', 'EveryDataComponentTests',
           'FacetsOfAHiddenTableTests', 'ObjectPageConditionTests',
           'MenuEscapingTests', 'GTFormRendererTests']
