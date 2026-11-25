"""W31: the proposals of wave 11 -- a ResolveContext the project configures
(``GT_DESIGNS_RESOLVE_CONTEXT``) for every way a page is published or served,
``CheckboxSelectMultiple`` drawn as one box per choice, a facets panel over a
region or a grid of an exposed model, and the ``app`` of a document.
Classes prefixed ``W31`` so the ``import *`` of ``tests/__init__.py`` never
hides another module's."""

import json
import tempfile
from decimal import Decimal
from io import StringIO
from unittest import mock
from pathlib import Path

from django import forms
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from demoapp.models import Department, PurchaseRequest
from djgentelella import geocoding
from djgentelella.datasources.base import (
    ModelDataSource, register_datasource, unregister_datasource,
)
from djgentelella.designs import engine, format, publishing
from djgentelella.designs.components import ResolveContext, default_context_class
from djgentelella.designs.exposure import expose
from djgentelella.designs.models import Page
from djgentelella.designs.pipeline import (
    build_pipeline, param_defaults, process, step_build,
)
from djgentelella.locking import object_version
from djgentelella.designs.regions import facets_state, region_page_context
from djgentelella.forms.forms import GTForm
from djgentelella.tests.Designs_Test import DesignState, design, node
from djgentelella.tests.DesignsData_Test import DataDesignTestCase
from djgentelella.tests.DesignsHooks_Test import gtconfig
from djgentelella.tests.TreeTimelineMetrics_Test import TTMBase, metrics
from djgentelella.widgets import core as genwidgets

__all__ = ['W31ResolveContextTests', 'W31CheckboxSelectMultipleTests',
           'W31FacetsOverModelTests', 'W31AppNameTests', 'W31GridSiteFieldTests',
           'W31SmallTests']

FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
CONTEXT = 'djgentelella.tests.ProposalsW31_Test.AppStepsContext'


# -- a ResolveContext with the rule of djodo: the steps of the page's app -------------

@process('demoapp.w31_own', kind='validation')
def own_step(ctx):
    return None


@process('shop.w31_step', kind='validation')
def shop_step(ctx):
    return None


class AppStepsContext(ResolveContext):
    """A pipeline step must belong to the app of the page: the first label
    of the Site's domain, or the document's ``app`` without a Site."""

    def page_app(self):
        if self.site is not None:
            return self.site.domain.split('.')[0]
        return (self.design or {}).get('app')

    def pipeline_step(self, name, path=None):
        found = super().pipeline_step(name, path)
        if found is not None and name.split('.')[0] != self.page_app():
            if path is not None:
                self.error(path, 'the step %s belongs to another app' % name)
            return None
        return found


class NotAContext:
    pass


def with_step(name):
    document = design(node('html', 'hello', {'html': '<p>Hi</p>'}))
    document['root']['props'] = {'pipeline': {'before_render': {
        'steps': [{'name': name}]}}}
    return document


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS)
class W31ResolveContextTests(DesignState, TestCase):
    def setUp(self):
        super().setUp()
        self.shop = Site.objects.create(domain='shop.example', name='Shop')
        self.admin = User.objects.create_superuser('w31admin', 'a@example.com', 'pw')

    def messages(self, errors):
        return ' '.join(str(error) for error in errors)

    def test_without_the_setting_nothing_changes(self):
        self.assertIs(default_context_class(), ResolveContext)
        _page, errors = publishing.publish(with_step('shop.w31_step'), path='w31a')
        self.assertEqual(errors, [])

    def test_the_setting_takes_a_class_or_its_path(self):
        for value in (CONTEXT, AppStepsContext):
            with override_settings(GT_DESIGNS_RESOLVE_CONTEXT=value):
                self.assertIs(default_context_class(), AppStepsContext)
        with override_settings(GT_DESIGNS_RESOLVE_CONTEXT=NotAContext):
            with self.assertRaises(ImproperlyConfigured):
                default_context_class()

    @override_settings(GT_DESIGNS_RESOLVE_CONTEXT=CONTEXT)
    def test_publish_uses_it(self):
        page, errors = publishing.publish(with_step('shop.w31_step'), path='w31b')
        self.assertIsNone(page)
        self.assertIn('the step shop.w31_step belongs to another app',
                      self.messages(errors))
        self.assertFalse(Page.objects.filter(path='w31b').exists())
        _page, errors = publishing.publish(with_step('demoapp.w31_own'), path='w31b')
        self.assertEqual(errors, [])
        # For a Site, the rule is that Site's: its app is "shop".
        _page, errors = publishing.publish(with_step('shop.w31_step'), path='w31b',
                                           site=self.shop)
        self.assertEqual(errors, [])
        _page, errors = publishing.publish(with_step('demoapp.w31_own'),
                                           path='w31b', site=self.shop)
        self.assertIn('belongs to another app', self.messages(errors))
        # import_page goes through publish.
        _page, errors = publishing.import_page(
            {'path': 'w31c', 'document': with_step('shop.w31_step')})
        self.assertIn('belongs to another app', self.messages(errors))

    @override_settings(GT_DESIGNS_RESOLVE_CONTEXT=CONTEXT)
    def test_a_context_given_wins(self):
        _page, errors = publishing.publish(with_step('shop.w31_step'), path='w31d',
                                           context=ResolveContext)
        self.assertEqual(errors, [])
        self.assertEqual(publishing.validate(with_step('shop.w31_step'),
                                             context=ResolveContext), [])

    @override_settings(GT_DESIGNS_RESOLVE_CONTEXT=CONTEXT)
    def test_the_command_uses_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'page.json'
            path.write_text(json.dumps(with_step('shop.w31_step')), encoding='utf-8')
            with self.assertRaisesMessage(CommandError, 'belongs to another app'):
                call_command('gtdesigns_publish', str(path), '--path', 'w31e')
            self.assertFalse(Page.objects.filter(path='w31e').exists())
            call_command('gtdesigns_publish', str(path), '--path', 'w31e',
                         '--site', 'shop.example', stdout=StringIO())
        self.assertTrue(Page.objects.filter(path='w31e', site=self.shop).exists())

    @override_settings(GT_DESIGNS_RESOLVE_CONTEXT=CONTEXT)
    def test_the_admin_uses_it(self):
        self.client.force_login(self.admin)
        url = reverse('admin:gtdesigns_page_add')

        def add(document, site=''):
            return self.client.post(url, {
                'site': site, 'path': 'w31f', 'is_published': 'on',
                'document': json.dumps(document)})

        response = add(with_step('shop.w31_step'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'belongs to another app')
        self.assertFalse(Page.objects.filter(path='w31f').exists())
        # The Site of the form is the one the document is validated for.
        response = add(with_step('shop.w31_step'), site=self.shop.pk)
        self.assertEqual(response.status_code, 302, response.content[:2000])
        page = Page.objects.get(path='w31f')
        self.assertEqual((page.site, page.updated_by), (self.shop, self.admin))
        # "Validate" of a page saved some other way.
        bad = Page.objects.create(path='w31g', document=with_step('shop.w31_step'))
        response = self.client.get(reverse('admin:gtdesigns_page_validate',
                                           args=[bad.pk]), follow=True)
        self.assertContains(response, 'belongs to another app')
        response = self.client.get(reverse('admin:gtdesigns_page_validate',
                                           args=[page.pk]), follow=True)
        self.assertContains(response, 'The design is valid.')

    def test_serving_a_page_uses_it(self):
        page = Page.objects.create(path='w31h', document=with_step('shop.w31_step'))
        self.assertEqual(engine.resolve_page(page)[1], [])
        # The class is part of the cache key: the setting is not missed.
        with override_settings(GT_DESIGNS_RESOLVE_CONTEXT=CONTEXT):
            with self.assertLogs('djgentelella.designs.engine', 'WARNING'):
                resolved, errors = engine.resolve_page(page)
            self.assertIsNone(resolved)
            self.assertIn('belongs to another app', self.messages(errors))
            resolved, errors = engine.resolve(with_step('demoapp.w31_own'))
            self.assertIs(resolved.context_class, AppStepsContext)

    def test_build_pipeline_uses_it(self):
        stage = {'steps': [{'name': 'shop.w31_step'}]}
        self.assertIsNotNone(build_pipeline(stage))
        with override_settings(GT_DESIGNS_RESOLVE_CONTEXT=CONTEXT):
            with self.assertRaisesMessage(ImproperlyConfigured,
                                          'belongs to another app'):
                build_pipeline(stage)
            self.assertIsNotNone(build_pipeline(stage, site=self.shop))
            self.assertIsNotNone(build_pipeline(stage, context=ResolveContext))
            with self.assertRaises(TypeError):
                build_pipeline(stage, context=NotAContext)


# -- CheckboxSelectMultiple ---------------------------------------------------------

COLORS = [('red', 'Red'), ('green', 'Green'), ('blue', 'Blue')]


class W31CheckboxForm(GTForm, forms.Form):
    colors = forms.MultipleChoiceField(
        choices=COLORS, required=False,
        widget=genwidgets.CheckboxSelectMultiple(attrs={'class': 'extra'}))


@override_settings(LANGUAGE_CODE='en')
class W31CheckboxSelectMultipleTests(SimpleTestCase):
    def widget_html(self, widget, value=('green',)):
        widget.choices = COLORS
        return widget.render('colors', list(value), attrs={'id': 'id_colors'})

    def test_the_class_goes_on_each_box_not_on_the_list(self):
        html = self.widget_html(genwidgets.CheckboxSelectMultiple())
        self.assertIn('<ul id="id_colors" class="gt-check-list">', html)
        self.assertEqual(html.count('type="checkbox"'), 3)
        self.assertEqual(html.count('class="gt-check "'), 3)
        self.assertNotIn('<ul id="id_colors" class="gt-check', html.replace(
            'gt-check-list', ''))
        self.assertEqual(html.count(' checked'), 1)
        for index in range(3):
            self.assertIn('id="id_colors_%d"' % index, html)

    def test_other_classes_go_on_both(self):
        html = self.widget_html(genwidgets.CheckboxSelectMultiple(
            attrs={'class': 'extra'}))
        self.assertIn('<ul id="id_colors" class="gt-check-list extra">', html)
        self.assertEqual(html.count('class="gt-check extra"'), 3)

    def test_groups(self):
        widget = genwidgets.CheckboxSelectMultiple()
        widget.choices = [('Warm', [('red', 'Red')]), ('Cold', [('blue', 'Blue')])]
        html = widget.render('colors', [], attrs={'id': 'id_colors'})
        self.assertIn('<ul id="id_colors" class="gt-check-list">', html)
        self.assertIn('<ul id="id_colors_0">', html)
        self.assertEqual(html.count('class="gt-check "'), 2)

    def test_in_every_layout(self):
        for layout in ('as_plain', 'as_horizontal', 'as_inline'):
            html = str(getattr(W31CheckboxForm(render_type=layout), layout)())
            self.assertIn('class="gt-check-list extra"', html, layout)
            self.assertEqual(html.count('class="gt-check extra"'), 3, layout)


# -- a facets panel over a node of a model -------------------------------------------

UNIT_PERMS = ['demoapp.%s_department' % action
              for action in ('view', 'add', 'change', 'delete')]


def cards(id_='units', **props):
    return node('cards', id_, {'model': 'demoapp.Department', 'title_field': 'name',
                               'site_field': 'site', 'fields': ['head'], **props})


def facets(target, columns=('head',), id_='f'):
    return node('facets', id_, {'target': target, 'columns': list(columns)})


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS,
                   ALLOWED_HOSTS=['*'])
class W31FacetsOverModelTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        expose(Department)
        self.site_a = Site.objects.create(domain='a.example', name='A')
        self.site_b = Site.objects.create(domain='b.example', name='B')
        self.grant(*UNIT_PERMS)
        Department.objects.create(name='Mine', head='Eva', site=self.site_a)
        Department.objects.create(name='Also mine', head='Leo', site=self.site_a)
        Department.objects.create(name='Theirs', head='Eva', site=self.site_b)
        Department.objects.create(name='Shared', head='Eva')

    def get(self, url, **params):
        return self.client.get(url, params, HTTP_HOST='a.example')

    def counts(self, page, node_id='f', **params):
        response = self.get(self.api(page, node_id) + 'facets/',
                            params=json.dumps(params))
        self.assertEqual(response.status_code, 200, response.content)
        return {item['label']: item['count'] for item in response.json()['head']}

    def test_a_panel_over_cards_of_a_model(self):
        resolved, errors = engine.resolve(design(facets('units'), cards()))
        self.assertEqual(errors, [])
        panel = resolved.nodes['f'].build
        self.assertEqual((panel.model, panel.columns, panel.datasource),
                         (Department, ['head'], ''))
        page = self.publish(design(facets('units'), cards()), path='w31-cards')
        # The counts are those of the rows of the cards: this Site and global.
        self.assertEqual(self.counts(page), {'Eva': 2, 'Leo': 1})
        description = self.get(self.api(page, 'f')).json()
        self.assertEqual([column['name'] for column in description['columns']],
                         ['head'])
        # The cards take the filters of the panel as their parameter document.
        params = {'filters': [{'column': 'head', 'op': 'in', 'value': ['Leo']}]}
        rows = self.get(self.api(page, 'units'), params=json.dumps(params)).json()
        self.assertEqual([row['title'] for row in rows['data']], ['Also mine'])
        # The page: the panel and the cards share the group, and the cards
        # have no data source URL (the browser takes the panel's).
        content = self.get(reverse('gt-design-page', args=['w31-cards'])).content
        content = content.decode()
        self.assertIn('data-group="gtdesign:units"', content)
        self.assertIn('data-url="%s"' % self.api(page, 'f'), content)
        config = gtconfig(content, 'units')
        self.assertEqual(config['group'], 'gtdesign:units')
        self.assertNotIn('datasource_url', config)

    def test_the_panel_needs_what_the_region_needs(self):
        page = self.publish(design(facets('units'), cards(perms=[
            'demoapp.view_department', 'demoapp.delete_department'])),
            path='w31-perms')
        self.assertEqual(self.counts(page), {'Eva': 2, 'Leo': 1})
        self.user.user_permissions.remove(
            *self.user.user_permissions.filter(codename='delete_department'))
        self.grant()
        response = self.get(self.api(page, 'f') + 'facets/', params='{}')
        self.assertEqual(response.status_code, 403)

    def test_the_columns_are_checked(self):
        errors = self.errors(design(facets('units', ['nope']), cards()))
        self.assertIn("'nope' cannot have a facet", ' '.join(errors))

    def test_filtered_by_over_the_same_model(self):
        document = design(facets('units'), cards(),
                          cards('more', filtered_by='f'),
                          node('metrics', 'kpis', {
                              'model': 'demoapp.Department', 'site_field': 'site',
                              'filtered_by': 'f',
                              'metrics': [{'label': 'Units', 'fn': 'count'}]}))
        resolved, errors = engine.resolve(document)
        self.assertEqual(errors, [])
        self.assertEqual(resolved.nodes['more'].build.group, 'gtdesign:units')
        self.assertEqual(facets_state(resolved.nodes['kpis'].build),
                         {'group': 'gtdesign:units'})
        page = self.publish(document, path='w31-kpis')
        params = {'filters': [{'column': 'head', 'op': 'in', 'value': ['Eva']}]}
        cards_html = self.get(self.api(page, 'kpis'),
                              params=json.dumps(params)).json()['html']
        self.assertIn('>2<', cards_html.replace(' ', '').replace('\n', ''))
        # Another model, or another Site rule: other rows.
        errors = ' '.join(self.errors(design(facets('units'), cards(), node(
            'cards', 'other', {'model': 'demoapp.Product', 'title_field': 'name',
                               'filtered_by': 'f'}))))
        self.assertIn("facets panel 'f' filters other rows", errors)
        errors = ' '.join(self.errors(design(facets('units'), cards(),
                                             cards('global', site_field='',
                                                   filtered_by='f'))))
        self.assertIn("facets panel 'f' filters other rows", errors)

    def test_a_panel_over_a_grid_of_a_model(self):
        grid = node('interactive_grid', 'grid', {
            'model': 'demoapp.Department', 'columns': ['name', 'head']})
        page = self.publish(design(facets('grid'), grid), path='w31-grid')
        self.assertEqual(self.counts(page), {'Eva': 3, 'Leo': 1})
        filters = [{'column': 'head', 'op': 'in', 'value': ['Leo']}]
        rows = self.get(self.api(page, 'grid'), gtfilters=json.dumps(filters)).json()
        self.assertEqual([row['name'] for row in rows['data']], ['Also mine'])
        content = self.get(reverse('gt-design-page', args=['w31-grid'])).content
        self.assertEqual(gtconfig(content.decode(), 'grid')['group'], 'gtdesign:grid')

    def test_a_tree_of_a_model_too(self):
        errors = ' '.join(self.errors(design(facets('t'), node('tree', 't', {
            'model': 'demoapp.Department', 'title_field': 'name',
            'parent_field': 'parent'}))))
        self.assertEqual(errors, '')

    def test_region_page_context_for_generated_code(self):
        resolved, errors = engine.resolve(design(facets('units'), cards()))
        self.assertEqual(errors, [])
        request = RequestFactory().get('/', HTTP_HOST='a.example')
        request.user = self.user
        context = region_page_context(resolved.nodes['units'].build, request,
                                      '/gen/units/')
        self.assertIn('"group": "gtdesign:units"', str(context['config']))


# -- the app of a document -----------------------------------------------------------

@override_settings(LANGUAGE_CODE='en')
class W31AppNameTests(SimpleTestCase):
    def test_the_pattern_is_the_schema_s(self):
        schema = format.load_schema()
        self.assertEqual(schema['properties']['app']['pattern'], format.APP_PATTERN)

    def test_a_slug_as_an_app(self):
        self.assertEqual(format.app_name('mi-tienda'), 'mi_tienda')
        self.assertEqual(format.app_name(' Ventas Norte '), 'ventas_norte')
        self.assertEqual(format.app_name('2024-ventas'), '_2024_ventas')
        self.assertEqual(format.app_name('rrhh'), 'rrhh')
        for bad in ('', 'a.b', 'ñandú', None):
            with self.assertRaises(ValueError):
                format.app_name(bad)

    def test_a_slug_with_a_dash_is_not_an_app(self):
        document = design(node('html', 'x', {'html': 'x'}))
        document['app'] = 'mi-tienda'
        errors = format.validate_envelope(document)
        self.assertEqual([error.path for error in errors], ['$.app'])
        document['app'] = format.app_name('mi-tienda')
        self.assertEqual(format.validate_envelope(document), [])


# -- proposals of D18 ----------------------------------------------------------------

@process('demoapp.w31_limit', kind='validation', schema={
    'type': 'object', 'additionalProperties': False, 'required': ['limit'],
    'properties': {'limit': {'type': 'integer', 'minimum': 1, 'default': 10},
                   'unit': {'type': 'string', 'default': 'kg'}}})
def limited(ctx, limit, unit):
    return None


@override_settings(LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST_HASHERS,
                   ALLOWED_HOSTS=['*'])
class W31GridSiteFieldTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        expose(Department)
        self.site_a = Site.objects.create(domain='a.example', name='A')
        self.site_b = Site.objects.create(domain='b.example', name='B')
        self.grant(*UNIT_PERMS)
        self.mine = Department.objects.create(name='Mine', site=self.site_a)
        self.theirs = Department.objects.create(name='Theirs', site=self.site_b)
        self.shared = Department.objects.create(name='Shared')

    def grid(self, **props):
        return design(node('interactive_grid', 'grid', {
            'model': 'demoapp.Department', 'columns': ['name', 'head'],
            'site_field': 'site', **props}))

    def save(self, url, *rows):
        return self.client.post(url + 'save/', json.dumps({'rows': list(rows)}),
                                content_type='application/json',
                                HTTP_HOST='a.example')

    def test_what_resolve_checks(self):
        errors = ' '.join(self.errors(self.grid(site_field='name')))
        self.assertIn("'name' is not a foreign key of demoapp.Department to "
                      "sites.Site", errors)
        expose(Site)
        errors = ' '.join(self.errors(self.grid(columns=['name', 'site'],
                                                editable=['name', 'site'])))
        self.assertIn("'site' is the site_field", errors)
        resolved, errors = engine.resolve(self.grid())
        self.assertEqual(errors, [])
        self.assertEqual(resolved.nodes['grid'].build.site_field, 'site')

    def test_rows_of_the_site(self):
        page = self.publish(self.grid(), path='w31-grid-site')
        url = self.api(page, 'grid')
        rows = self.client.get(url, {'limit': 100}, HTTP_HOST='a.example').json()
        self.assertEqual(sorted(row['name'] for row in rows['data']),
                         ['Mine', 'Shared'])
        self.assertEqual(self.client.get(url + '%d/' % self.theirs.pk,
                                         HTTP_HOST='a.example').status_code, 404)
        response = self.save(url, {'key': 'n1', 'op': 'create',
                                   'data': {'name': 'New', 'head': 'Ana'}})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Department.objects.get(name='New').site, self.site_a)
        # Another Site's row cannot be changed nor deleted.
        response = self.save(url, {'key': 'u', 'op': 'update', 'id': self.theirs.pk,
                                   '_version': object_version(self.theirs),
                                   'data': {'name': 'Taken'}})
        self.assertEqual(response.status_code, 404, response.content)
        response = self.save(url, {'key': 'd', 'op': 'delete', 'id': self.theirs.pk,
                                   '_version': object_version(self.theirs)})
        self.assertEqual(response.status_code, 404, response.content)
        self.theirs.refresh_from_db()
        self.assertEqual(self.theirs.name, 'Theirs')

    def test_not_over_a_data_source(self):
        name = 'tests.w31.units'
        register_datasource(ModelDataSource(Department, name=name, perms=[]))
        self.addCleanup(unregister_datasource, name)
        errors = ' '.join(self.errors(design(node('interactive_grid', 'grid', {
            'datasource': name, 'columns': ['name'], 'site_field': 'site'}))))
        self.assertIn('a data source applies its own Site rule', errors)


@override_settings(LANGUAGE_CODE='en', ALLOWED_HOSTS=['*'])
class W31SmallTests(TTMBase):
    def test_a_card_over_every_row_says_all(self):
        requester = User.objects.create_user('w31req')
        PurchaseRequest.objects.create(title='P', amount=Decimal('5.00'),
                                       requester=requester)
        page = self.publish(metrics(
            {'label': 'Month', 'fn': 'count'},
            {'label': 'Total', 'fn': 'count', 'period': 'all'},
            date_field='created_at', period='month'), path='w31-kpis')
        cards = {card['key']: card for card in self.json(page, 'kpis')['metrics']}
        self.assertEqual((cards['m0']['period'], cards['m1']['period']),
                         ('month', 'all'))
        self.assertEqual(cards['m1']['period_label'], '')

    def test_the_defaults_of_the_params_of_a_step(self):
        schema = {'properties': {'limit': {'default': 10}, 'unit': {'default': 'kg'},
                                 'other': {'type': 'string'}}}
        self.assertEqual(param_defaults(schema), {'limit': 10, 'unit': 'kg'})
        found = build_pipeline({'steps': [{'name': 'demoapp.w31_limit'}]})
        self.assertEqual(found.steps[0].params, {'limit': 10, 'unit': 'kg'})
        found = build_pipeline({'steps': [{'name': 'demoapp.w31_limit',
                                           'params': {'limit': 3}}]})
        self.assertEqual(found.steps[0].params, {'limit': 3, 'unit': 'kg'})
        with self.assertRaises(ImproperlyConfigured):
            build_pipeline({'steps': [{'name': 'demoapp.w31_limit',
                                       'params': {'limit': 0}}]})
        built = step_build('gen.x', 'validation', limited, schema={
            'properties': {'limit': {'type': 'integer', 'default': 2}}})
        self.assertEqual(built.params, {'limit': 2})

    def test_extra_params_of_nominatim(self):
        response = mock.MagicMock()
        response.read.return_value = b'[]'
        response.__enter__.return_value = response
        with mock.patch('djgentelella.geocoding.urlopen',
                        return_value=response) as urlopen:
            geocoding.NominatimGeocoder(
                url='https://geo.invalid/search',
                extra_params={'key': 'k1', 'q': 'hijacked'},
                extra_headers={'X-Api-Key': 'h1'}).search('San José')
        request = urlopen.call_args[0][0]
        self.assertIn('key=k1', request.full_url)
        self.assertIn('q=San+Jos', request.full_url)
        self.assertNotIn('hijacked', request.full_url)
        self.assertEqual(request.get_header('X-api-key'), 'h1')
        self.assertEqual(request.get_header('User-agent'), 'djgentelella')
