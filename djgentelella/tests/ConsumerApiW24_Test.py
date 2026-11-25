"""API for the consumers (W24): region and read-only table viewsets with a
build of their own (``region_build``), the page context of a region and of a
facets panel without a published page, columns for a Site without a request,
the point columns, the default settings after a flush, the page attribute of
a design and the mouse click of the browser tests."""

import json

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from demoapp.models import Meetup
from djgentelella import testing
from djgentelella.datasources.base import (
    Column, DataSource, ModelDataSource, register_datasource, source_column_map,
    unregister_datasource,
)
from djgentelella.designs import (
    data_components, engine, publishing, regions, source_tables,
)
from djgentelella.designs.components import ResolveContext
from djgentelella.models import GentelellaSettings
from djgentelella.sites import get_current_site
from djgentelella.tests.Designs_Test import DesignState, design, node
from djgentelella.tests.RegionComponents_Test import (
    SOURCE, RegionBase, calendar, cards, facets, region_map,
)
from djgentelella.utils import DEFAULT_SETTINGS, get_settings, load_default_settings

SITE_SOURCE = 'tests.w24.by_site'


def build_of(document, node_id):
    resolved, errors = engine.resolve(document)
    assert errors == [], errors
    return resolved.nodes[node_id].build


class RegionBuildTests(RegionBase):
    """``region_build`` and ``get_build()``: a viewset outside the engine."""

    def setUp(self):
        super().setUp()
        self.meetup('Global')
        self.meetup('Of A', site=self.site_a)
        self.meetup('Of B', site=self.site_b)
        document = design(cards(), calendar(), region_map())
        self.builds = {node_id: build_of(document, node_id)
                       for node_id in ('list', 'agenda', 'places')}

    def call(self, viewset, user=None, host='a.example', build=None, **params):
        request = APIRequestFactory().get('/region/', params, HTTP_HOST=host)
        if build is not None:
            request.gtdesign_build = build
        force_authenticate(request, user=user or self.user)
        return viewset.as_view({'get': 'list'})(request)

    def generated(self, base, node_id):
        return type('Generated', (base,), {'region_build': self.builds[node_id]})

    def test_it_answers_without_gtdesign_build(self):
        cases = ((regions.CardsViewSet, 'list', {}, 'data'),
                 (regions.CalendarViewSet, 'agenda', self.month(), 'events'),
                 (regions.MapViewSet, 'places', {}, 'layers'))
        for base, node_id, params, key in cases:
            response = self.call(self.generated(base, node_id), **params)
            self.assertEqual(response.status_code, 200, (node_id, response.data))
            self.assertIn(key, response.data)
        response = self.call(self.generated(regions.CardsViewSet, 'list'),
                             host='b.example')
        self.assertEqual(sorted(card['title'] for card in response.data['data']),
                         ['Global', 'Of B'])

    def test_the_class_attribute_wins(self):
        other = build_of(design(cards(perms=['demoapp.delete_meetup'])), 'list')
        response = self.call(self.generated(regions.CardsViewSet, 'list'),
                             build=other)
        self.assertEqual(response.status_code, 200)

    def test_without_a_build_it_is_404(self):
        self.assertEqual(self.call(regions.CardsViewSet).status_code, 404)
        self.assertEqual(self.call(regions.CardsViewSet,
                                   build=self.builds['list']).status_code, 200)

    def test_the_403_is_the_same(self):
        beto = User.objects.create_user('beto', password='pw')
        for base, node_id in ((regions.CardsViewSet, 'list'),
                              (regions.MapViewSet, 'places')):
            self.assertEqual(self.call(self.generated(base, node_id),
                                       user=beto).status_code, 403)

    def test_the_contract_of_the_403_is_public(self):
        for name in ('check_access', 'read_rows', 'region_source',
                     'region_page_context', 'request_params', 'RegionMixin'):
            self.assertIn(name, regions.__all__)
        self.assertIn('SourceRowsMixin', source_tables.__all__)
        self.assertIn('facets_page_context', data_components.__all__)


class RemoteMeetups(DataSource):
    """Rows that are not of a model of the project, as djgentelella sees them."""

    name = SOURCE
    perms = []
    project_model = None

    def columns(self, request):
        return [Column('title', 'Title', 'string'), Column('kind', 'Kind', 'string')]

    def get_queryset(self, request):
        return Meetup.objects.all()


class SourceTableBuildTests(DesignState, TestCase):
    """The same for the read-only tables of W23."""

    def setUp(self):
        super().setUp()
        register_datasource(RemoteMeetups())
        self.addCleanup(unregister_datasource, SOURCE)
        Meetup.objects.create(title='One', kind='talk', starts_at='2026-01-01T10:00Z')
        self.user = User.objects.create_user('ana')
        self.listing = build_of(design(node('object_management', 'list', {
            'datasource': SOURCE, 'list_fields': ['title', 'kind']})), 'list')
        self.grid = build_of(design(node('interactive_grid', 'grid', {
            'datasource': SOURCE, 'columns': ['title']})), 'grid')

    def call(self, viewset):
        request = APIRequestFactory().get('/rows/')
        force_authenticate(request, user=self.user)
        return viewset.as_view({'get': 'list'})(request)

    def test_region_build(self):
        table = type('Table', (source_tables.SourceTableViewSet,),
                     {'region_build': self.listing})
        response = self.call(table)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['title'] for row in response.data['data']], ['One'])
        grid = type('Grid', (source_tables.SourceGridViewSet,),
                    {'region_build': self.grid})
        self.assertEqual(self.call(grid).data['count'], 1)

    def test_without_a_build_it_is_404(self):
        self.assertEqual(self.call(source_tables.SourceTableViewSet).status_code, 404)


class RegionPageContextTests(RegionBase):

    def setUp(self):
        super().setUp()
        self.document = design(cards(), facets(), calendar(filtered_by='filters'),
                               region_map(cluster=True))
        self.request = RequestFactory().get('/page/', HTTP_HOST='a.example')
        self.request.user = self.user

    def config(self, context):
        text = str(context['config'])
        return json.loads(text[text.index('>') + 1:text.rindex('</script>')])

    def test_the_context_of_each_region(self):
        for node_id, node_type, group in (('list', 'cards', 'list'),
                                          ('agenda', 'calendar', 'list'),
                                          ('places', 'map', 'places')):
            build = build_of(self.document, node_id)
            context = regions.region_page_context(build, self.request, '/x/')
            self.assertEqual(set(context), {'b', 'preview', 'template', 'config'})
            self.assertIs(context['b'], build)
            self.assertFalse(context['preview'])
            self.assertEqual(context['template'],
                             'gtdesigns/components/%s.html' % node_type)
            config = self.config(context)
            self.assertEqual((config['id'], config['type'], config['url']),
                             (node_id, node_type, '/x/'))
            self.assertEqual(config['datasource_url'],
                             reverse('gtdatasource', kwargs={'name': SOURCE}))
            self.assertEqual(config['group'], 'gtdesign:' + group)
        agenda = self.config(regions.region_page_context(
            build_of(self.document, 'agenda'), self.request, '/x/'))
        self.assertIn('fullcalendar', agenda)
        self.assertEqual(agenda['locale'], 'en')
        places = self.config(regions.region_page_context(
            build_of(self.document, 'places'), self.request, '/x/'))
        self.assertTrue(places['cluster'])
        self.assertIn('markercluster', places)

    def test_the_same_config_as_the_published_page(self):
        page, errors = publishing.publish(self.document, path='regions')
        self.assertEqual(errors, [])
        content = self.client.get(reverse('gt-design-page', args=['regions']),
                                  HTTP_HOST='a.example').content.decode()
        url = reverse('gt-design-endpoint', kwargs={
            'page_id': page.pk, 'node_id': 'agenda', 'rest': ''})
        context = regions.region_page_context(build_of(self.document, 'agenda'),
                                              self.request, url)
        self.assertIn(str(context['config']), content)

    def test_it_renders(self):
        context = regions.region_page_context(build_of(self.document, 'list'),
                                              self.request, '/x/')
        html = render_to_string(context['template'], context)
        self.assertIn('data-gtconfig="list_gtconfig"', html)

    def test_none_without_permission(self):
        build = build_of(self.document, 'list')
        self.assertIsNone(regions.region_page_context(build, self.request, ''))
        self.assertIsNone(regions.region_page_context(build, None, '/x/'))
        self.request.user = User.objects.create_user('beto')
        self.assertIsNone(regions.region_page_context(build, self.request, '/x/'))
        guarded = build_of(design(cards(perms=['demoapp.change_meetup'])), 'list')
        self.request.user = self.user
        self.assertIsNone(regions.region_page_context(guarded, self.request, '/x/'))
        self.request.user = User.objects.get(pk=self.user.pk)
        unregister_datasource(SOURCE)
        self.assertIsNone(regions.region_page_context(build, self.request, '/x/'))


class FacetsPageContextTests(RegionBase):

    def setUp(self):
        super().setUp()
        self.panel = build_of(design(cards(), facets()), 'filters')
        self.request = RequestFactory().get('/page/', HTTP_HOST='a.example')
        self.request.user = self.user

    def test_the_context(self):
        context = data_components.facets_page_context(self.panel, self.request)
        self.assertEqual(context['url'], reverse('gtdatasource',
                                                 kwargs={'name': SOURCE}))
        self.assertEqual(context['group'], 'gtdesign:list')
        self.assertEqual(context['columns'], 'kind')
        self.assertEqual(context['template'], data_components.FACETS_TEMPLATE)
        own = data_components.facets_page_context(self.panel, self.request, '/api/')
        self.assertEqual(own['url'], '/api/')

    def test_none_without_permission(self):
        self.request.user = User.objects.create_user('beto')
        self.assertIsNone(data_components.facets_page_context(self.panel,
                                                              self.request))
        self.assertIsNone(data_components.facets_page_context(self.panel, None))
        guarded = build_of(design(cards(), node('facets', 'filters', {
            'target': 'list', 'columns': ['kind'],
            'perms': ['demoapp.change_meetup']})), 'filters')
        self.request.user = self.user
        self.assertIsNone(data_components.facets_page_context(guarded,
                                                              self.request))

    def test_a_panel_over_a_model_table(self):
        panel = data_components.FacetsBuild('filters', 'facets', {}, target='table',
                                            model=Meetup)
        with self.assertRaises(ValueError):
            data_components.facets_page_context(panel, self.request)


class BySiteSource(DataSource):
    """Columns that depend on the Site of the request: none without one."""

    name = SITE_SOURCE
    perms = []
    project_model = Meetup

    def columns(self, request):
        if request is None:
            return []
        site = get_current_site(request)
        result = [Column('title', 'Title', 'string')]
        if site is not None and site.domain == 'a.example':
            result.append(Column('city', 'City', 'string'))
        return result

    def get_queryset(self, request):
        return Meetup.objects.all()


@override_settings(ALLOWED_HOSTS=['*'])
class ColumnsForSiteTests(DesignState, TestCase):

    def setUp(self):
        super().setUp()
        self.site_a = Site.objects.create(domain='a.example', name='A')
        register_datasource(BySiteSource())
        self.addCleanup(unregister_datasource, SITE_SOURCE)

    def document(self, field='city'):
        return design(node('cards', 'list', {'datasource': SITE_SOURCE,
                                             'title_field': 'title',
                                             'fields': [field]}))

    def test_a_page_of_a_site_validates_without_a_request(self):
        self.assertEqual(publishing.validate(self.document(), site=self.site_a), [])
        page, errors = publishing.publish(self.document(), site=self.site_a,
                                          path='by-site')
        self.assertEqual(errors, [])
        self.assertIsNotNone(page)

    def test_without_a_site_the_columns_are_still_unknown(self):
        self.assertTrue(publishing.validate(self.document()))

    def test_a_site_without_the_column(self):
        other = Site.objects.create(domain='b.example', name='B')
        errors = publishing.validate(self.document(), site=other)
        self.assertTrue(any('city' in error.message for error in errors), errors)

    def test_the_hook(self):
        source = BySiteSource()
        self.assertEqual(sorted(source.columns_for_site(self.site_a)[i].name
                                for i in range(2)), ['city', 'title'])
        self.assertEqual(sorted(source_column_map(source, site=self.site_a)),
                         ['city', 'title'])
        self.assertEqual(source_column_map(source), {})
        request = RequestFactory().get('/', HTTP_HOST='a.example')
        self.assertEqual(sorted(source_column_map(source, request, site=None)),
                         ['city', 'title'])

    def test_a_source_may_override_it(self):
        class Fixed(BySiteSource):
            def columns_for_site(self, site):
                return [Column('title', 'Title', 'string'),
                        Column('city', 'City', 'string')]

        unregister_datasource(SITE_SOURCE)
        register_datasource(Fixed())
        other = Site.objects.create(domain='b.example', name='B')
        self.assertEqual(publishing.validate(self.document(), site=other), [])

    def test_the_resolve_context(self):
        rctx = ResolveContext({}, None, site=self.site_a)
        self.assertEqual(sorted(rctx.source_columns(BySiteSource())),
                         ['city', 'title'])

        class Broken(BySiteSource):
            def columns(self, request):
                raise RuntimeError('no')

        self.assertIsNone(rctx.source_columns(Broken()))


class PointColumnTests(TestCase):

    def test_a_point_field_is_marked(self):
        columns = ModelDataSource(Meetup, perms=[]).column_map(None)
        self.assertEqual(columns['location'].extra, {'point': True})
        self.assertEqual(columns['title'].extra, {})
        self.assertEqual(columns['location'].as_dict()['extra'], {'point': True})
        self.assertEqual(columns['location'].kind, 'string')


@override_settings(ALLOWED_HOSTS=['*'])
class DefaultSettingsTests(DesignState, TestCase):

    def setUp(self):
        super().setUp()
        GentelellaSettings.objects.all().delete()

    def test_it_loads_what_the_migrations_load(self):
        self.assertEqual(get_settings('site_theme'), '')
        self.assertEqual(sorted(load_default_settings()), sorted(DEFAULT_SETTINGS))
        for key, value in DEFAULT_SETTINGS.items():
            self.assertEqual(get_settings(key), value)
        self.assertEqual(load_default_settings(), [])

    def test_overwrite_and_values(self):
        GentelellaSettings.objects.create(key='site_title', value='Mine')
        self.assertNotIn('site_title', load_default_settings(use_compress_static=None,
                                                             extra_key='x'))
        self.assertEqual(get_settings('site_title'), 'Mine')
        self.assertEqual(get_settings('use_compress_static'), '')
        self.assertEqual(get_settings('extra_key'), 'x')
        load_default_settings(overwrite=True)
        self.assertEqual(get_settings('site_title'), DEFAULT_SETTINGS['site_title'])

    def test_a_page_without_settings_has_no_empty_link(self):
        User.objects.create_user('ana', password='pw')
        self.client.login(username='ana', password='pw')
        publishing.publish(design(node('html', 'hello', {'html': '<p>hi</p>'})),
                           path='plain')
        content = self.client.get(reverse('gt-design-page',
                                          args=['plain'])).content.decode()
        self.assertNotIn('href="/static/?v=', content)
        self.assertIn('gentelella/css/custom.css', content)


class PageAttributeTests(DesignState, TestCase):

    def test_a_node_may_have_the_id_of_the_slug(self):
        document = design(node('html', 'sample', {'html': '<p>x</p>'}))
        resolved, errors = engine.resolve(document)
        self.assertEqual(errors, [])
        request = RequestFactory().get('/')
        request.user = User.objects.create_user('viewer')
        content = engine.render(resolved, request).content.decode()
        self.assertIn('data-gtdesign="page" data-gtdesign-page="sample"', content)
        self.assertEqual(content.count('data-gtdesign="sample"'), 1)


class MouseClickTests(TestCase):

    def test_it_scrolls_without_animation_then_clicks(self):
        calls = []

        class Element:
            def click(self):
                calls.append('click')

        class Driver:
            def execute_script(self, script, *args):
                calls.append((script, args))

        element = Element()
        self.assertIs(testing.mouse_click(Driver(), element), element)
        (script, args), click = calls
        self.assertEqual(click, 'click')
        self.assertEqual(args, (element,))
        self.assertIn("scrollBehavior = 'auto'", script)
        self.assertIn("behavior: 'instant'", script)
