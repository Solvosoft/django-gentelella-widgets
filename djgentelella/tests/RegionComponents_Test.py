"""The region components (djgentelella.designs.regions): ``cards``,
``calendar`` and ``map`` over a data source or an exposed model (C15)."""

import json
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.template import Engine
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory

import demoapp
from demoapp.models import Meetup
from djgentelella.datasources.base import (
    ModelDataSource, register_datasource, unregister_datasource,
)
from djgentelella.designs import engine, publishing, registry, regions
from djgentelella.designs.exposure import expose
from djgentelella.tests.DesignsPages_Test import grant
from djgentelella.tests.Designs_Test import DesignState, design, node
from djgentelella.views.listAreaViewset import ListAreaViewset

FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
SOURCE = 'tests.regions.meetups'
#: The same rows with a relation shown (``site``): what an N+1 would hit.
FK_SOURCE = 'tests.regions.meetups_fk'
LINK = {'url_name': 'admin:demoapp_meetup_change', 'title': 'Open'}


def cards(**props):
    return node('cards', 'list', {'datasource': SOURCE, 'title_field': 'title',
                                  **props})


def calendar(**props):
    return node('calendar', 'agenda', {'datasource': SOURCE, 'title_field': 'title',
                                       'start_field': 'starts_at', **props})


def region_map(**props):
    return node('map', 'places', {'datasource': SOURCE, 'title_field': 'title',
                                  'point_field': 'location', **props})


def facets(target='list', columns=('kind',)):
    return node('facets', 'filters', {'target': target, 'columns': list(columns)})


@override_settings(LANGUAGE_CODE='en', ALLOWED_HOSTS=['*'],
                   PASSWORD_HASHERS=FAST_HASHERS, TIME_ZONE='UTC')
class RegionBase(DesignState, TestCase):
    def setUp(self):
        super().setUp()
        registry.get_components()
        expose(Meetup)
        Site.objects.clear_cache()
        self.site_a = Site.objects.create(domain='a.example', name='A')
        self.site_b = Site.objects.create(domain='b.example', name='B')
        register_datasource(ModelDataSource(
            Meetup, name=SOURCE, site_field='site',
            fields=['id', 'title', 'kind', 'city', 'starts_at', 'ends_at',
                    'location', 'picture']))
        self.addCleanup(unregister_datasource, SOURCE)
        register_datasource(ModelDataSource(
            Meetup, name=FK_SOURCE, site_field='site',
            fields=['id', 'title', 'kind', 'starts_at', 'ends_at', 'location',
                    'site']))
        self.addCleanup(unregister_datasource, FK_SOURCE)
        self.user = grant(User.objects.create_user('ana', password='pw'),
                          'demoapp.view_meetup')
        self.client.force_login(self.user)
        self.now = timezone.now().replace(microsecond=0)

    def meetup(self, title, days=0, kind='talk', location='9.93,-84.09', site=None,
               **kwargs):
        return Meetup.objects.create(
            title=title, kind=kind, starts_at=self.now + timedelta(days=days),
            location=location, site=site, **kwargs)

    def publish(self, *nodes, path='regions', **meta):
        page, errors = publishing.publish(design(*nodes, **meta), path=path)
        self.assertEqual(errors, [])
        return page

    def resolve_errors(self, document):
        _resolved, errors = engine.resolve(document)
        return [(error.path, error.message) for error in errors]

    def url(self, design_page, node_id, **params):
        url = reverse('gt-design-endpoint', kwargs={
            'page_id': design_page.pk, 'node_id': node_id, 'rest': ''})
        if 'params' in params and not isinstance(params['params'], str):
            params['params'] = json.dumps(params['params'])
        return url, params

    def get(self, design_page, node_id, host='a.example', **params):
        url, params = self.url(design_page, node_id, **params)
        return self.client.get(url, params, HTTP_HOST=host)

    def month(self):
        return {'start': (self.now - timedelta(days=15)).isoformat(),
                'end': (self.now + timedelta(days=15)).isoformat()}

    def titles(self, response, node_type):
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        if node_type == 'cards':
            return sorted(card['title'] for card in body['data'])
        if node_type == 'calendar':
            return sorted(event['title'] for event in body['events'])
        return sorted(point['title'] for point in body['layers'][0]['points'])


class RegionSchemaTests(RegionBase):
    def assertError(self, document_node, path, text):
        errors = self.resolve_errors(design(document_node))
        self.assertTrue(any(where.startswith(path) and text in message
                            for where, message in errors), errors)

    def test_the_three_are_registered_after_the_others(self):
        types = list(registry.get_components())
        # Together, after the built-in ones (W25 adds its own after them).
        first = types.index('cards')
        self.assertEqual(types[first:first + 3], ['cards', 'calendar', 'map'])
        self.assertGreater(first, types.index('flow_kanban'))
        for name in ('cards', 'calendar', 'map'):
            component = registry.get_component(name)
            self.assertTrue(component.facets_target)
            props = component.props_schema['properties']
            self.assertEqual(props['datasource']['x-widget'], 'datasource')
            self.assertEqual(props['model']['x-widget'], 'model')
            self.assertEqual(props['row_links']['x-widget'], 'links')

    def test_model_or_datasource(self):
        self.assertError(node('cards', 'x', {'title_field': 'title'}),
                         '$.root', 'give a "model" or a "datasource"')
        self.assertError(node('cards', 'x', {'title_field': 'title', 'model':
                                             'demoapp.Meetup', 'datasource': SOURCE}),
                         '$.root', 'not both')

    def test_columns_by_role(self):
        self.assertError(cards(title_field='nope'), '$.root', "'nope' is not a column")
        self.assertError(calendar(start_field='city'), '$.root',
                         "'city' is not a date / datetime column")
        self.assertError(node('map', 'm', {'model': 'demoapp.Meetup',
                                           'point_field': 'city'}),
                         '$.root', 'is not a GTPointField')
        self.assertError(calendar(colors={'talk': '#fff'}), '$.root',
                         'colors needs a color_field')
        self.assertError(calendar(color_rules=[{'filter': {'column': 'x', 'op': 'eq',
                                                           'value': 1},
                                                'color': 'red'}]),
                         '$.root', "unknown column 'x'")
        self.assertError(calendar(colors={'talk': 'red;x'}, color_field='kind'),
                         '$.root', 'does not match')

    def test_site_field_and_its_model(self):
        self.assertError(node('cards', 'x', {'model': 'demoapp.Meetup',
                                             'title_field': 'title',
                                             'site_field': 'city'}),
                         '$.root', 'is not a foreign key of demoapp.Meetup to sites')
        self.assertError(cards(site_field='site'), '$.root',
                         'site_field goes with a model')

    def test_facets_need_a_datasource(self):
        self.assertError(node('facets', 'f', {'target': 'x', 'columns': ['kind']}),
                         '$.root', '')
        # Over a model too since W31: the panel counts through its own
        # endpoint (ProposalsW31_Test.W31FacetsOverModelTests).
        errors = self.resolve_errors(design(
            node('cards', 'list', {'model': 'demoapp.Meetup', 'title_field': 'title'}),
            facets()))
        self.assertFalse(any('datasource' in message for _where, message in errors),
                         errors)
        self.assertEqual(self.resolve_errors(design(cards(), facets())), [])

    def test_filtered_by(self):
        self.assertEqual(self.resolve_errors(design(
            cards(), facets(), calendar(filtered_by='filters'))), [])
        errors = self.resolve_errors(design(cards(), calendar(filtered_by='list')))
        self.assertIn('is not the id of a facets panel', str(errors))

    def test_a_row_link_is_checked(self):
        self.assertError(cards(row_links=[{'url_name': 'nothing_here', 'title': 'x'}]),
                         '$.root', 'is neither a URL name')
        self.assertEqual(self.resolve_errors(design(cards(row_links=[LINK]))), [])

    def test_the_demo_page_publishes(self):
        register_datasource(ModelDataSource(
            Meetup, name='demoapp.meetups', site_field='site',
            fields=['id', 'title', 'kind', 'city', 'starts_at', 'ends_at',
                    'location', 'picture']))
        path = Path(demoapp.__file__).resolve().parent / 'gtdesign' / 'meetups.json'
        document = json.loads(path.read_text())
        _page, errors = publishing.publish(document, path='meetups')
        self.assertEqual(errors, [])


class AccessTests(RegionBase):
    """Only ``get_queryset(request)`` of the data source: Site and perms."""

    def setUp(self):
        super().setUp()
        self.meetup('Global')
        self.meetup('Of A', site=self.site_a)
        self.meetup('Of B', site=self.site_b)
        self.page = self.publish(cards(), calendar(), region_map())

    def test_a_row_of_another_site_does_not_appear(self):
        for node_id, kind, extra in (('list', 'cards', {}),
                                     ('agenda', 'calendar', self.month()),
                                     ('places', 'map', {})):
            self.assertEqual(self.titles(self.get(self.page, node_id, **extra), kind),
                             ['Global', 'Of A'], kind)
            self.assertEqual(self.titles(self.get(self.page, node_id, host='b.example',
                                                  **extra), kind),
                             ['Global', 'Of B'], kind)

    def test_a_model_with_site_field(self):
        page = self.publish(node('cards', 'list', {
            'model': 'demoapp.Meetup', 'title_field': 'title', 'site_field': 'site'}),
            node('map', 'places', {'model': 'demoapp.Meetup', 'point_field': 'location',
                                   'title_field': 'title', 'site_field': 'site'}),
            path='model')
        self.assertEqual(self.titles(self.get(page, 'list'), 'cards'),
                         ['Global', 'Of A'])
        self.assertEqual(self.titles(self.get(page, 'places'), 'map'),
                         ['Global', 'Of A'])
        without = self.publish(node('cards', 'list', {
            'model': 'demoapp.Meetup', 'title_field': 'title'}), path='all')
        self.assertEqual(self.titles(self.get(without, 'list'), 'cards'),
                         ['Global', 'Of A', 'Of B'])

    def test_without_permission_it_is_403(self):
        self.client.force_login(User.objects.create_user('beto', password='pw'))
        for node_id, extra in (('list', {}), ('agenda', self.month()), ('places', {})):
            self.assertEqual(self.get(self.page, node_id, **extra).status_code, 403)
        page = self.publish(node('cards', 'list', {
            'model': 'demoapp.Meetup', 'title_field': 'title'}), path='model')
        self.assertEqual(self.get(page, 'list').status_code, 403)
        response = self.client.get(reverse('gt-design-page', args=['regions']),
                                   HTTP_HOST='a.example')
        self.assertContains(response, 'You do not have permission to see this.',
                            count=3)

    def test_the_build_perms_and_the_source(self):
        page = self.publish(cards(perms=['demoapp.change_meetup']), path='perms')
        self.assertEqual(self.get(page, 'list').status_code, 403)
        self.user = grant(self.user, 'demoapp.change_meetup')
        self.client.force_login(self.user)
        self.assertEqual(self.get(page, 'list').status_code, 200)

    def test_anonymous(self):
        self.client.logout()
        self.assertEqual(self.get(self.page, 'list').status_code, 403)

    def test_a_node_condition_hides_the_endpoint(self):
        page = self.publish(cards(condition={'perm': 'demoapp.delete_meetup'}),
                            path='cond')
        self.assertEqual(self.get(page, 'list').status_code, 404)

    def test_the_page_renders_each_component(self):
        response = self.client.get(reverse('gt-design-page', args=['regions']),
                                   HTTP_HOST='a.example')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for node_id in ('list', 'agenda', 'places'):
            self.assertIn('id="%s_gtconfig"' % node_id, content)
        self.assertIn('gentelella/js/designs/regions.js', content)
        self.assertIn(reverse('gtdatasource', kwargs={'name': SOURCE}), content)


class FacetTests(RegionBase):
    """The facets (the parameter document) filter the three components."""

    def setUp(self):
        super().setUp()
        self.meetup('Talk', kind='talk')
        self.meetup('Workshop', kind='workshop')
        self.meetup('Social', kind='social', city='Heredia')
        self.page = self.publish(cards(), facets(), calendar(filtered_by='filters'),
                                 region_map(filtered_by='filters'))

    def test_the_three_follow_the_filters(self):
        params = {'filters': [{'column': 'kind', 'op': 'in',
                               'value': ['talk', 'social']}]}
        for node_id, kind, extra in (('list', 'cards', {}),
                                     ('agenda', 'calendar', self.month()),
                                     ('places', 'map', {})):
            self.assertEqual(self.titles(self.get(self.page, node_id, params=params,
                                                  **extra), kind),
                             ['Social', 'Talk'], kind)

    def test_search(self):
        self.assertEqual(self.titles(self.get(self.page, 'list',
                                              params={'search': 'heredia'}), 'cards'),
                         ['Social'])

    def test_they_share_the_group_of_the_panel(self):
        response = self.client.get(reverse('gt-design-page', args=['regions']),
                                   HTTP_HOST='a.example')
        content = response.content.decode()
        self.assertEqual(content.count('"group": "gtdesign:list"'), 3)
        self.assertIn('data-group="gtdesign:list"', content)

    def test_bad_parameters_are_400(self):
        self.assertEqual(self.get(self.page, 'list', params='{').status_code, 400)
        self.assertEqual(self.get(self.page, 'list', params={'filters': [
            {'column': 'nope', 'op': 'eq', 'value': 1}]}).status_code, 400)

    def test_a_hidden_field_cannot_be_filtered(self):
        page = self.publish(cards(fields=['city', 'kind'], column_conditions={
            'city': {'perm': 'demoapp.delete_meetup'}}), path='hidden')
        response = self.get(page, 'list')
        fields = response.json()['data'][0]['fields']
        self.assertEqual([item['label'] for item in fields],
                         ['Kind'])
        self.assertEqual(self.get(page, 'list', params={'filters': [
            {'column': 'city', 'op': 'eq', 'value': 'Heredia'}]}).status_code, 400)

    def test_a_hidden_field_is_not_searched(self):
        page = self.publish(cards(fields=['city', 'kind'], column_conditions={
            'city': {'perm': 'demoapp.delete_meetup'}}), path='hidden')
        # Only Social has "Heredia", in its hidden city: no row tells it.
        self.assertEqual(self.titles(self.get(page, 'list', params={
            'search': 'heredia'}), 'cards'), [])
        self.assertEqual(self.titles(self.get(page, 'list', search='heredia'),
                                     'cards'), [])
        self.assertEqual(self.titles(self.get(page, 'list', params={
            'search': 'social'}), 'cards'), ['Social'])
        # Where the condition holds, the city is searched again.
        self.user = grant(self.user, 'demoapp.delete_meetup')
        self.client.force_login(self.user)
        self.assertEqual(self.titles(self.get(page, 'list', params={
            'search': 'heredia'}), 'cards'), ['Social'])

    def test_the_default_ordering_skips_a_hidden_field(self):
        def order(page):
            return [card['title'] for card in self.get(page, 'list').json()['data']]

        shown = self.publish(cards(fields=['city'], ordering=['-city']), path='shown')
        self.assertEqual(order(shown)[0], 'Social')
        hidden = self.publish(cards(fields=['city'], ordering=['-city'],
                                    column_conditions={
                                        'city': {'perm': 'demoapp.delete_meetup'}}),
                              path='hidden')
        # By pk, as without an ordering: the order does not tell the cities.
        self.assertEqual(order(hidden), ['Talk', 'Workshop', 'Social'])


class CardsTests(RegionBase):
    def test_a_page_of_cards(self):
        for index in range(5):
            self.meetup('M%d' % index, days=index, picture='https://img.example/%d.png'
                        % index, city='City %d' % index)
        page = self.publish(cards(subtitle_field='city', image_field='picture',
                                  fields=['kind', 'starts_at'], page_size=2,
                                  ordering=['starts_at'], row_links=[LINK]))
        body = self.get(page, 'list').json()
        self.assertEqual(
            (body['recordsTotal'], body['totalPages'], body['currentPage']), (5, 3, 1))
        first = body['data'][0]
        self.assertEqual((first['title'], first['subtitle'], first['image']),
                         ('M0', 'City 0', 'https://img.example/0.png'))
        self.assertEqual(first['fields'][0], {'label': 'Kind', 'value': 'Talk'})
        meetup = Meetup.objects.get(title='M0')
        self.assertEqual(first['url'], reverse('admin:demoapp_meetup_change',
                                               args=[meetup.pk]))
        self.assertEqual(first['links'][0]['title'], 'Open')
        # The ListAreaViewset answer: a Squirrelly template CardList renders.
        self.assertIn('<% @each(it.data) => card %>', body['template'])
        self.assertEqual(body['actions'], [])
        self.assertEqual([card['title'] for card in self.get(page, 'list', page=3)
                          .json()['data']], ['M4'])

    def test_unsafe_images_are_dropped(self):
        self.meetup('Bad', picture='javascript:alert(1)')
        page = self.publish(cards(image_field='picture'))
        self.assertEqual(self.get(page, 'list').json()['data'][0]['image'], '')

    def test_an_ordering_by_pk(self):
        for title in ('First', 'Second', 'Third'):
            self.meetup(title)
        # The resolver accepts "pk" (it is no column of the source).
        page = self.publish(cards(ordering=['-pk']))
        response = self.get(page, 'list')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([card['title'] for card in response.json()['data']],
                         ['Third', 'Second', 'First'])

    def test_safe_url(self):
        for value in ('javascript:alert(1)', '//evil.example/x.png',
                      '/\\evil.example/x.png', '\\\\evil.example', 'data:x'):
            self.assertEqual(regions.safe_url(value), '', value)
        for value in ('/media/x.png', 'https://img.example/x.png',
                      'HTTP://img.example/x.png'):
            self.assertEqual(regions.safe_url(value), value)

    def test_queries_do_not_grow_with_the_cards(self):
        # A relation among the fields: its labels are read once per page.
        page = self.publish(cards(datasource=FK_SOURCE, fields=['kind', 'site'],
                                  page_size=50))
        self.meetup('One', site=self.site_a)
        self.get(page, 'list')  # warm the caches (page, registry)

        def count():
            with CaptureQueriesContext(connection) as queries:
                response = self.get(page, 'list')
            self.assertEqual(response.status_code, 200)
            return len(queries), response.json()['data']

        one, _cards = count()
        for index in range(30):
            self.meetup('More %d' % index, site=self.site_a)
        many, data = count()
        self.assertEqual((many, len(data)), (one, 31))
        self.assertEqual(data[0]['fields'][1], {'label': 'Site', 'value': 'a.example'})

    def test_the_rows_of_a_page_are_not_searched_again(self):
        for title in ('Alpha', 'Beta', 'Alphabet'):
            self.meetup(title)
        page = self.publish(cards())
        with CaptureQueriesContext(connection) as queries:
            titles = self.titles(self.get(page, 'list', params={'search': 'alpha'}),
                                 'cards')
        self.assertEqual(titles, ['Alpha', 'Alphabet'])
        searched = [item['sql'] for item in queries.captured_queries
                    if 'demoapp_meetup' in item['sql'] and 'LIKE' in item['sql']]
        # The count and the page of pks; the rows of that page by pk only.
        self.assertEqual(len(searched), 2, searched)

    def test_list_area_viewset_without_a_filter_form(self):
        class Plain(ListAreaViewset):
            pass

        view = Plain()
        self.assertIsNone(view.get_filter_form(RequestFactory().get('/')))


class CalendarTests(RegionBase):
    def setUp(self):
        super().setUp()
        self.meetup('Today', ends_at=self.now + timedelta(hours=2), kind='workshop')
        self.meetup('Next month', days=45)
        self.meetup('Last month', days=-45)
        self.meetup('Long one', days=-30, ends_at=self.now + timedelta(days=1))

    def test_only_the_visible_range(self):
        page = self.publish(calendar(end_field='ends_at'))
        self.assertEqual(
            self.titles(self.get(page, 'agenda', **self.month()), 'calendar'),
            ['Long one', 'Today'])
        later = {'start': (self.now + timedelta(days=30)).isoformat(),
                 'end': (self.now + timedelta(days=60)).isoformat()}
        self.assertEqual(self.titles(self.get(page, 'agenda', **later), 'calendar'),
                         ['Next month'])
        without_end = self.publish(calendar(), path='noend')
        self.assertEqual(self.titles(self.get(without_end, 'agenda', **self.month()),
                                     'calendar'), ['Today'])

    def test_the_range_is_in_the_query(self):
        page = self.publish(calendar(end_field='ends_at'))
        self.get(page, 'agenda', **self.month())
        with CaptureQueriesContext(connection) as queries:
            self.get(page, 'agenda', **self.month())
        sql = [item['sql'] for item in queries.captured_queries
               if 'demoapp_meetup' in item['sql']]
        self.assertEqual(len(sql), 1, sql)
        self.assertIn('"starts_at" <', sql[0])
        self.assertIn('LIMIT', sql[0])

    def test_a_range_is_required(self):
        page = self.publish(calendar())
        self.assertEqual(self.get(page, 'agenda').status_code, 400)
        self.assertEqual(self.get(page, 'agenda', start='2026-01-01',
                                  end='2028-01-01').status_code, 400)
        self.assertEqual(self.get(page, 'agenda', start='2026-02-01',
                                  end='2026-01-01').status_code, 400)
        self.assertEqual(self.get(page, 'agenda', start='2026-01-01',
                                  end='2026-02-01').status_code, 200)

    def test_events(self):
        page = self.publish(calendar(end_field='ends_at', color_field='kind',
                                     colors={'workshop': '#e67e22'},
                                     row_links=[LINK]))
        events = {event['title']: event for event in
                  self.get(page, 'agenda', **self.month()).json()['events']}
        today = events['Today']
        self.assertEqual(today['color'], '#e67e22')
        self.assertFalse(today['allDay'])
        self.assertIn('end', today)
        self.assertNotIn('color', events['Long one'])
        self.assertEqual(today['url'], reverse(
            'admin:demoapp_meetup_change', args=[Meetup.objects.get(title='Today').pk]))

    def test_color_rules_win(self):
        page = self.publish(calendar(color_field='kind', color_rules=[
            {'filter': {'column': 'kind', 'op': 'eq', 'value': 'workshop'},
             'color': 'red'}]))
        events = self.get(page, 'agenda', **self.month()).json()['events']
        self.assertEqual({event['title']: event.get('color') for event in events},
                         {'Today': 'red'})

    def test_the_limit(self):
        page = self.publish(calendar(end_field='ends_at', limit=1))
        body = self.get(page, 'agenda', **self.month()).json()
        self.assertEqual((len(body['events']), body['truncated']), (1, True))

    def test_queries_do_not_grow_with_the_rows(self):
        page = self.publish(calendar(datasource=FK_SOURCE, end_field='ends_at',
                                     fields=['site']))
        # A relation with a value from the start: its labels are one query.
        self.meetup('Here', site=self.site_a)
        self.get(page, 'agenda', **self.month())

        def count():
            with CaptureQueriesContext(connection) as queries:
                events = self.get(page, 'agenda', **self.month()).json()['events']
            return len(queries), len(events)

        before, shown = count()
        for index in range(20):
            # Inside the range, with a relation shown, and far outside it.
            self.meetup('Near %d' % index, days=index % 10, site=self.site_a)
            self.meetup('Far %d' % index, days=200 + index)
        self.assertEqual(count(), (before, shown + 20))


class MapTests(RegionBase):
    def setUp(self):
        super().setUp()
        self.meetup('San Jose', location='9.928100,-84.090700', city='San Jose')
        self.meetup('Limon', location='9.990700, -83.035900')
        self.meetup('Madrid', location='40.4168,-3.7038')
        self.meetup('Nowhere', location='')
        self.meetup('Broken', location='not a point')

    def test_points_and_popups(self):
        page = self.publish(region_map(fields=['city'], row_links=[LINK], cluster=True))
        body = self.get(page, 'places').json()
        self.assertTrue(body['cluster'])
        self.assertTrue(body['fit_bounds'])
        points = {point['title']: point for point in body['layers'][0]['points']}
        self.assertEqual(sorted(points), ['Limon', 'Madrid', 'San Jose'])
        self.assertEqual((points['Limon']['lat'], points['Limon']['lng']),
                         (9.9907, -83.0359))
        popup = points['San Jose']['popup']
        self.assertIn('<dt>City</dt>', popup)
        self.assertIn(reverse('admin:demoapp_meetup_change', args=[
            Meetup.objects.get(title='San Jose').pk]), popup)

    def test_the_popup_is_escaped(self):
        self.meetup('<script>x</script>', location='1,1')
        page = self.publish(region_map())
        popups = [point['popup'] for point in
                  self.get(page, 'places').json()['layers'][0]['points']]
        self.assertTrue(any('&lt;script&gt;' in popup for popup in popups))
        self.assertFalse(any('<script>' in popup for popup in popups))

    def test_the_bounding_box(self):
        page = self.publish(region_map())
        costa_rica = self.get(page, 'places', bbox='-86,8,-82,11.5')
        self.assertEqual(self.titles(costa_rica, 'map'), ['Limon', 'San Jose'])
        self.assertFalse(costa_rica.json()['fit_bounds'])
        spain = self.get(page, 'places', bbox='-10,35,5,45')
        self.assertEqual(self.titles(spain, 'map'), ['Madrid'])
        # Across the antimeridian: from 170 E to 2 W, the long way round.
        self.assertEqual(self.titles(self.get(page, 'places', bbox='170,-90,358,90'),
                                     'map'), ['Limon', 'Madrid', 'San Jose'])
        self.assertEqual(self.get(page, 'places', bbox='1,2,3').status_code, 400)

    def test_the_limit(self):
        page = self.publish(region_map(limit=2))
        body = self.get(page, 'places').json()
        self.assertEqual((len(body['layers'][0]['points']), body['truncated'],
                          body['limit']), (2, True, 2))

    def test_queries_do_not_grow_with_the_points(self):
        page = self.publish(region_map(datasource=FK_SOURCE, limit=10,
                                       fields=['kind', 'site']))
        self.meetup('Here', site=self.site_a)
        self.get(page, 'places', bbox='-180,-90,180,90')

        def count():
            with CaptureQueriesContext(connection) as queries:
                body = self.get(page, 'places', bbox='-180,-90,180,90').json()
            return len(queries), len(body['layers'][0]['points'])

        before, _points = count()
        for index in range(40):
            self.meetup('More %d' % index, location='%d,%d' % (index, index),
                        site=self.site_a)
        after, points = count()
        self.assertEqual((after, points), (before, 10))

    def test_the_popup_template_is_read_once(self):
        for index in range(5):
            self.meetup('P%d' % index, location='%d,%d' % (index, index))
        page = self.publish(region_map(fields=['kind']))
        self.get(page, 'places')
        original = Engine.get_template
        names = []

        def get_template(engine_self, name):
            names.append(name)
            return original(engine_self, name)

        with mock.patch.object(Engine, 'get_template', get_template):
            points = self.get(page, 'places').json()['layers'][0]['points']
        self.assertGreaterEqual(len(points), 5)
        self.assertEqual(names.count('gtdesigns/components/map_popup.html'), 1)


class RegionPreviewTests(RegionBase):
    def test_preview_reads_no_rows(self):
        self.meetup('Hidden')
        document = design(cards(fields=['kind']), calendar(), region_map())
        resolved, errors = engine.resolve(document, preview=True)
        self.assertEqual(errors, [])
        request = APIRequestFactory().get('/')
        request.user = self.user
        with CaptureQueriesContext(connection) as queries:
            html = engine.render(resolved, request).content.decode()
        self.assertNotIn('Hidden', html)
        self.assertFalse([item for item in queries.captured_queries
                          if 'demoapp_meetup' in item['sql']])
        self.assertIn('Title 1', html)

    def test_builds_hold_data(self):
        resolved, errors = engine.resolve(design(calendar(end_field='ends_at')))
        self.assertEqual(errors, [])
        build = resolved.nodes['agenda'].build
        self.assertIsInstance(build, regions.CalendarBuild)
        self.assertEqual((build.start_field, build.end_field, build.datasource),
                         ('starts_at', 'ends_at', SOURCE))
