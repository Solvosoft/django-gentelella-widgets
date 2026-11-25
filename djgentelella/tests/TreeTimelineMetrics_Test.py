"""The ``tree``, ``timeline`` and ``metrics`` region components
(djgentelella.designs.tree_timeline_metrics, C17): their data source, the
Site, the permissions, the facets and ``filtered_by``; a tree with a cycle and
with an absent parent, a timeline by range and pages, and the metric cards
with every aggregate and the comparison against the previous period."""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory

import demoapp
from demoapp.models import Department, Meetup, PurchaseRequest
from djgentelella.datasources import query
from djgentelella.datasources.base import (
    Column, DataSourceUnavailable, ModelDataSource, register_datasource,
    unregister_datasource,
)
from djgentelella.designs import engine, publishing, registry
from djgentelella.designs.models import Page
from djgentelella.designs import tree_timeline_metrics as ttm
from djgentelella.designs.exposure import expose
from djgentelella.tests.Designs_Test import DesignState, design, node
from djgentelella.tests.DesignsPages_Test import grant

FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
UNITS = 'tests.ttm.departments'
MEETUPS = 'tests.ttm.meetups'
PURCHASES = 'tests.ttm.purchases'
DOWN = 'tests.ttm.down'
UNIT_LINK = {'url_name': 'admin:demoapp_department_change', 'title': 'Open'}
MEETUP_LINK = {'url_name': 'admin:demoapp_meetup_change', 'title': 'Open'}


class DownSource(ModelDataSource):
    def get_queryset(self, request):
        raise DataSourceUnavailable('The provider API is down.')


def tree(**props):
    return node('tree', 'org', {'datasource': UNITS, 'title_field': 'name',
                                'parent_field': 'parent', **props})


def timeline(**props):
    return node('timeline', 'history', {'datasource': MEETUPS, 'title_field': 'title',
                                        'start_field': 'starts_at', **props})


def metrics(*cards, **props):
    return node('metrics', 'kpis', {'datasource': PURCHASES,
                                    'metrics': list(cards) or [{'label': 'Rows',
                                                                'fn': 'count'}],
                                    **props})


def facets(target, columns, node_id='filters'):
    return node('facets', node_id, {'target': target, 'columns': list(columns)})


@override_settings(LANGUAGE_CODE='en', ALLOWED_HOSTS=['*'],
                   PASSWORD_HASHERS=FAST_HASHERS, TIME_ZONE='UTC')
class Base(DesignState, TestCase):
    def setUp(self):
        super().setUp()
        registry.get_components()
        expose(Department)
        expose(Meetup)
        Site.objects.clear_cache()
        self.site_a = Site.objects.create(domain='a.example', name='A')
        self.site_b = Site.objects.create(domain='b.example', name='B')
        for source in (
                ModelDataSource(Department, name=UNITS, site_field='site',
                                fields=['id', 'name', 'parent', 'icon', 'head']),
                ModelDataSource(Meetup, name=MEETUPS, site_field='site',
                                fields=['id', 'title', 'kind', 'city', 'starts_at',
                                        'ends_at']),
                ModelDataSource(PurchaseRequest, name=PURCHASES,
                                fields=['id', 'title', 'amount', 'supplier',
                                        'created_at']),
                DownSource(PurchaseRequest, name=DOWN,
                           fields=['id', 'amount', 'created_at'])):
            register_datasource(source)
            self.addCleanup(unregister_datasource, source.name)
        self.user = grant(User.objects.create_user('ana', password='pw'),
                          'demoapp.view_department', 'demoapp.view_meetup',
                          'demoapp.view_purchaserequest')
        self.client.force_login(self.user)
        self.now = timezone.now().replace(microsecond=0)

    def unit(self, name, parent=None, **kwargs):
        return Department.objects.create(name=name, parent=parent, **kwargs)

    def meetup(self, title, days=0, kind='talk', **kwargs):
        return Meetup.objects.create(title=title, kind=kind,
                                     starts_at=self.now + timedelta(days=days),
                                     **kwargs)

    def publish(self, *nodes, path='ttm', **meta):
        page, errors = publishing.publish(design(*nodes, **meta), path=path)
        self.assertEqual(errors, [])
        return page

    def errors(self, *nodes):
        _resolved, errors = engine.resolve(design(*nodes))
        return [(error.path, error.message) for error in errors]

    def assertError(self, document_node, text):
        errors = self.errors(document_node)
        self.assertTrue(any(text in message for _where, message in errors), errors)

    def get(self, page, node_id, host='a.example', **params):
        url = reverse('gt-design-endpoint', kwargs={
            'page_id': page.pk, 'node_id': node_id, 'rest': ''})
        if 'params' in params and not isinstance(params['params'], str):
            params['params'] = json.dumps(params['params'])
        return self.client.get(url, params, HTTP_HOST=host)

    def json(self, page, node_id, **params):
        response = self.get(page, node_id, **params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def page_html(self, path='ttm', host='a.example'):
        response = self.client.get(reverse('gt-design-page', args=[path]),
                                   HTTP_HOST=host)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()


# -- the documents -------------------------------------------------------------------

class SchemaTests(Base):
    def test_registered_after_the_others(self):
        types = list(registry.get_components())
        self.assertEqual(types[-6:], ['cards', 'calendar', 'map', 'tree', 'timeline',
                                      'metrics'])
        for name in ('tree', 'timeline', 'metrics'):
            component = registry.get_component(name)
            self.assertTrue(component.facets_target)
            props = component.props_schema['properties']
            self.assertEqual(props['datasource']['x-widget'], 'datasource')
            self.assertEqual(props['filtered_by']['x-widget'], 'node')
        tree_props = registry.get_component('tree').props_schema['properties']
        self.assertEqual(tree_props['parent_field']['x-filter'], 'parent')
        timeline_props = registry.get_component('timeline').props_schema['properties']
        self.assertEqual(timeline_props['colors']['x-widget'], 'value-colors')
        self.assertEqual(timeline_props['color_rules']['x-widget'], 'color-rules')
        metric_props = registry.get_component('metrics').props_schema['properties']
        self.assertEqual(metric_props['metrics']['x-widget'], 'metrics')
        self.assertEqual(metric_props['metrics']['items']['properties']['column']
                         ['x-filter'], 'numeric')

    def test_tree_roles(self):
        self.assertError(node('tree', 't', {'datasource': UNITS,
                                            'title_field': 'name'}),
                         'parent_field')
        self.assertError(tree(parent_field='nope'), "'nope' is not a column")
        self.assertError(tree(parent_field='name', id_field='id'),
                         'are not of the same kind')
        self.assertError(tree(id_field='name'), 'leave id_field empty')
        self.assertError(tree(icon_field='parent'), "'parent' is not a string")
        self.assertEqual(self.errors(tree(icon_field='icon', row_links=[UNIT_LINK])),
                         [])

    def test_a_parent_of_another_model(self):
        self.assertError(node('tree', 't', {'model': 'demoapp.Meetup',
                                            'title_field': 'title',
                                            'parent_field': 'site'}),
                         'is not a foreign key to demoapp.Meetup')

    def test_timeline_roles(self):
        self.assertError(timeline(start_field='city'), 'is not a date / datetime')
        self.assertError(timeline(colors={'talk': '#fff'}),
                         'colors needs a color_field')
        self.assertError(timeline(color_rules=[{'filter': {'column': 'x'},
                                                'color': 'red'}]),
                         "unknown column 'x'")
        self.assertEqual(self.errors(timeline(description_field='city',
                                              color_field='kind',
                                              colors={'talk': '#fff'})), [])

    def test_metric_cards(self):
        self.assertError(metrics({'label': 'x', 'fn': 'sum'}), 'sum needs a column')
        self.assertError(metrics({'label': 'x', 'fn': 'avg', 'column': 'title'}),
                         'avg needs a numeric column')
        self.assertError(metrics({'label': 'x', 'fn': 'count', 'column': 'nope'}),
                         "unknown column 'nope'")
        self.assertError(metrics({'label': 'x', 'fn': 'count', 'filters': [
            {'column': 'nope', 'op': 'eq', 'value': 1}]}), 'nope')
        self.assertError(metrics({'label': 'x', 'fn': 'count',
                                  'condition': {'nope': 1}}), '')
        self.assertError(metrics(date_field='title'), 'is not a date / datetime')
        self.assertError(metrics({'label': 'x', 'fn': 'median'}), 'median')
        self.assertError(metrics(metrics=[]), '')
        self.assertEqual(self.errors(metrics(
            {'label': 'x', 'fn': 'sum', 'column': 'amount', 'format': 'currency',
             'prefix': '$', 'filters': [{'column': 'supplier', 'op': 'eq',
                                         'value': 'ACME'}]},
            date_field='created_at', period='quarter')), [])

    def test_the_demo_page_publishes(self):
        for name, model, fields in (
                ('demoapp.meetups', Meetup, ['id', 'title', 'kind', 'city',
                                             'starts_at', 'ends_at', 'location',
                                             'picture']),
                ('demoapp.departments', Department, ['id', 'name', 'parent', 'icon',
                                                     'head']),
                ('demoapp.purchases', PurchaseRequest, ['id', 'title', 'amount',
                                                        'supplier', 'created_at'])):
            register_datasource(ModelDataSource(model, name=name, fields=fields))
        path = Path(demoapp.__file__).resolve().parent / 'gtdesign' / 'insights.json'
        _page, errors = publishing.publish(json.loads(path.read_text()),
                                           path='insights')
        self.assertEqual(errors, [])

    def test_builds_hold_data(self):
        resolved, errors = engine.resolve(design(tree(), timeline(), metrics()))
        self.assertEqual(errors, [])
        for node_id, build_class in (('org', ttm.TreeBuild),
                                     ('history', ttm.TimelineBuild),
                                     ('kpis', ttm.MetricsBuild)):
            self.assertIsInstance(resolved.nodes[node_id].build, build_class)

    def test_preview_reads_no_rows(self):
        self.unit('Real')
        resolved, errors = engine.resolve(design(
            tree(), timeline(), metrics({'label': 'Total', 'fn': 'count'},
                                        date_field='created_at')), preview=True)
        self.assertEqual(errors, [])
        request = APIRequestFactory().get('/')
        request.user = self.user
        with CaptureQueriesContext(connection) as queries:
            html = engine.render(resolved, request).content.decode()
        self.assertNotIn('Real', html)
        self.assertFalse([item for item in queries.captured_queries
                          if 'demoapp_department' in item['sql']
                          or 'demoapp_purchaserequest' in item['sql']])
        self.assertIn('Total', html)


# -- access ---------------------------------------------------------------------------

class AccessTests(Base):
    def setUp(self):
        super().setUp()
        self.unit('Global')
        self.unit('Of A', site=self.site_a)
        self.unit('Of B', site=self.site_b)
        self.meetup('Global')
        self.meetup('Of A', site=self.site_a)
        self.meetup('Of B', site=self.site_b)
        self.page = self.publish(tree(), timeline(),
                                 node('metrics', 'kpis', {
                                     'datasource': MEETUPS,
                                     'metrics': [{'label': 'n', 'fn': 'count'}]}))

    def test_a_row_of_another_site_does_not_appear(self):
        for host, other in (('a.example', 'Of A'), ('b.example', 'Of B')):
            nodes = self.get(self.page, 'org', host=host).json()['nodes']
            self.assertEqual(sorted(item['title'] for item in nodes),
                             ['Global', other])
            items = self.get(self.page, 'history', host=host).json()['items']
            self.assertEqual(sorted(item['title'] for item in items),
                             ['Global', other])
            cards = self.get(self.page, 'kpis', host=host).json()['metrics']
            self.assertEqual(cards[0]['value'], 2)

    def test_a_model_with_site_field(self):
        page = self.publish(node('tree', 'org', {
            'model': 'demoapp.Department', 'title_field': 'name',
            'parent_field': 'parent', 'site_field': 'site'}), path='model')
        titles = sorted(item['title'] for item in self.json(page, 'org')['nodes'])
        self.assertEqual(titles, ['Global', 'Of A'])

    def test_without_permission_it_is_403(self):
        self.client.force_login(User.objects.create_user('beto', password='pw'))
        for node_id in ('org', 'history', 'kpis'):
            self.assertEqual(self.get(self.page, node_id).status_code, 403, node_id)
        self.assertEqual(self.page_html().count(
            'You do not have permission to see this.'), 3)

    def test_the_build_perms(self):
        page = self.publish(tree(perms=['demoapp.change_department']),
                            path='perms')
        self.assertEqual(self.get(page, 'org').status_code, 403)
        self.client.force_login(grant(self.user, 'demoapp.change_department'))
        self.assertEqual(self.get(page, 'org').status_code, 200)

    def test_anonymous(self):
        self.client.logout()
        for node_id in ('org', 'history', 'kpis'):
            self.assertEqual(self.get(self.page, node_id).status_code, 403)

    def test_a_node_condition_hides_the_endpoint(self):
        page = self.publish(tree(condition={'perm': 'demoapp.delete_department'}),
                            timeline(condition={'perm': 'demoapp.delete_meetup'}),
                            metrics(condition={'perm': 'demoapp.delete_meetup'}),
                            path='cond')
        for node_id in ('org', 'history', 'kpis'):
            self.assertEqual(self.get(page, node_id).status_code, 404)
        html = self.page_html('cond')
        for node_id in ('org', 'history', 'kpis'):
            self.assertNotIn('id="%s_gtconfig"' % node_id, html)

    def test_an_unavailable_source_is_503(self):
        page = self.publish(node('metrics', 'kpis', {
            'datasource': DOWN, 'metrics': [{'label': 'n', 'fn': 'count'}]}),
            node('tree', 'org', {'datasource': DOWN, 'title_field': 'id',
                                 'parent_field': 'id'}), path='down')
        self.assertEqual(self.get(page, 'kpis').status_code, 503)
        self.assertEqual(self.get(page, 'org').status_code, 503)
        # The page stays: the cards say they could not be computed.
        self.assertIn('The metrics could not be computed.', self.page_html('down'))

    def test_the_page_renders_each_component(self):
        html = self.page_html()
        for node_id in ('org', 'history', 'kpis'):
            self.assertIn('id="%s_gtconfig"' % node_id, html)
        self.assertIn('gentelella/js/designs/tree_timeline_metrics.js', html)
        self.assertIn('gentelella/css/tree_timeline_metrics.css', html)


class FacetTests(Base):
    """A facets panel filters the three (``?params=``), and ``filtered_by``
    lets one panel filter several."""

    def setUp(self):
        super().setUp()
        self.meetup('Talk', kind='talk')
        self.meetup('Workshop', kind='workshop')
        self.meetup('Social', kind='social', city='Heredia')
        self.page = self.publish(
            timeline(), facets('history', ['kind']),
            node('metrics', 'kpis', {'datasource': MEETUPS, 'filtered_by': 'filters',
                                     'metrics': [{'label': 'n', 'fn': 'count'}]}))
        self.params = {'filters': [{'column': 'kind', 'op': 'in',
                                    'value': ['talk', 'social']}]}

    def test_timeline_and_metrics_follow_the_filters(self):
        items = self.json(self.page, 'history', params=self.params)['items']
        self.assertEqual(sorted(item['title'] for item in items), ['Social', 'Talk'])
        self.assertEqual(self.json(self.page, 'kpis')['metrics'][0]['value'], 3)
        self.assertEqual(self.json(self.page, 'kpis', params=self.params)
                         ['metrics'][0]['value'], 2)

    def test_they_share_the_group_of_the_panel(self):
        html = self.page_html()
        self.assertEqual(html.count('"group": "gtdesign:history"'), 2)

    def test_the_tree_follows_the_filters(self):
        root = self.unit('Root')
        self.unit('Alpha', root)
        self.unit('Beta', root)
        page = self.publish(tree(), facets('org', ['name']), path='treefacets')
        params = {'filters': [{'column': 'name', 'op': 'ne', 'value': 'Beta'}]}
        children = self.json(page, 'org', parent=str(root.pk), params=params)['nodes']
        self.assertEqual([item['title'] for item in children], ['Alpha'])
        self.assertEqual(self.get(page, 'org', params='{').status_code, 400)

    def test_filtered_by_another_source_is_an_error(self):
        errors = self.errors(timeline(), facets('history', ['kind']),
                             metrics(filtered_by='filters'))
        self.assertIn('filters another data source', str(errors))


# -- tree -----------------------------------------------------------------------------

class TreeTests(Base):
    def setUp(self):
        super().setUp()
        self.board = self.unit('Board', icon='fa fa-institution')
        self.ops = self.unit('Operations', self.board, head='Beto')
        self.logistics = self.unit('Logistics', self.ops)
        self.tech = self.unit('Technology', self.board)

    def titles(self, nodes):
        return [item['title'] for item in nodes]

    def test_lazy_levels(self):
        page = self.publish(tree(subtitle_field='head', icon_field='icon',
                                 ordering=['name'], row_links=[UNIT_LINK]))
        roots = self.json(page, 'org')
        self.assertEqual(self.titles(roots['nodes']), ['Board'])
        board = roots['nodes'][0]
        self.assertEqual((board['key'], board['children'], board['icon'],
                          board['orphan'], board['cycle']),
                         (str(self.board.pk), True, 'fa fa-institution', False, False))
        self.assertEqual(board['url'], reverse('admin:demoapp_department_change',
                                               args=[self.board.pk]))
        self.assertEqual((roots['orphans'], roots['cycles'], roots['checked']),
                         (0, 0, True))
        level = self.json(page, 'org', parent=board['key'])['nodes']
        self.assertEqual(self.titles(level), ['Operations', 'Technology'])
        self.assertEqual([item['children'] for item in level], [True, False])
        self.assertEqual(level[0]['subtitle'], 'Beto')
        self.assertEqual(self.titles(self.json(page, 'org', parent=level[0]['key'])
                                     ['nodes']), ['Logistics'])

    def test_paging_a_level(self):
        for index in range(5):
            self.unit('Child %d' % index, self.tech)
        page = self.publish(tree(limit=2, ordering=['name']))
        first = self.json(page, 'org', parent=str(self.tech.pk))
        self.assertEqual((self.titles(first['nodes']), first['next_offset']),
                         (['Child 0', 'Child 1'], 2))
        last = self.json(page, 'org', parent=str(self.tech.pk), offset=4)
        self.assertEqual((self.titles(last['nodes']), last['next_offset']),
                         (['Child 4'], None))
        self.assertEqual(self.get(page, 'org', offset='-1').status_code, 400)
        self.assertEqual(self.get(page, 'org', parent='abc').status_code, 400)

    def test_an_absent_parent_goes_to_the_root(self):
        # The parent is of another Site: not among the rows of this one.
        hidden = self.unit('Of B', site=self.site_b)
        self.unit('Lost', hidden)
        page = self.publish(tree(ordering=['name']))
        roots = self.json(page, 'org')
        self.assertEqual(self.titles(roots['nodes']), ['Board', 'Lost'])
        self.assertEqual([item['orphan'] for item in roots['nodes']], [False, True])
        self.assertEqual(roots['orphans'], 1)
        full = self.publish(tree(load='full', ordering=['name']), path='full')
        body = self.json(full, 'org')
        lost = [item for item in body['nodes'] if item['title'] == 'Lost'][0]
        self.assertEqual((lost['parent'], lost['depth'], lost['orphan']),
                         (None, 0, True))
        self.assertEqual(body['orphans'], 1)

    def test_a_cycle_does_not_hang(self):
        first = self.unit('Cycle A')
        second = self.unit('Cycle B', first)
        Department.objects.filter(pk=first.pk).update(parent=second)
        self_loop = self.unit('Self')
        Department.objects.filter(pk=self_loop.pk).update(parent=self_loop)
        page = self.publish(tree(ordering=['name']))
        roots = self.json(page, 'org')
        self.assertEqual(self.titles(roots['nodes']), ['Board', 'Cycle A', 'Self'])
        self.assertEqual([item['cycle'] for item in roots['nodes']],
                         [False, True, True])
        self.assertEqual(roots['cycles'], 2)
        cycle = roots['nodes'][1]
        self.assertTrue(cycle['children'])
        # Opening it: B, whose child is A again (the browser stops there).
        child = self.json(page, 'org', parent=cycle['key'])['nodes']
        self.assertEqual(self.titles(child), ['Cycle B'])
        self.assertEqual(self.titles(self.json(page, 'org', parent=child[0]['key'])
                                     ['nodes']), ['Cycle A'])
        # A row is never its own child.
        self.assertFalse(roots['nodes'][2]['children'])
        self.assertEqual(self.json(page, 'org', parent=roots['nodes'][2]['key'])
                         ['nodes'], [])
        full = self.publish(tree(load='full', ordering=['name']), path='full')
        body = self.json(full, 'org')
        self.assertEqual(sorted(self.titles(body['nodes'])),
                         ['Board', 'Cycle A', 'Cycle B', 'Logistics', 'Operations',
                          'Self', 'Technology'])
        self.assertEqual(body['cycles'], 2)

    def test_cycles_of_pairs(self):
        self.assertEqual(ttm.tree_cycles([('1', None), ('2', '1')]), [])
        self.assertEqual(ttm.tree_cycles([('3', '2'), ('2', '3'), ('4', '3')]), ['2'])
        self.assertEqual(ttm.tree_cycles([('5', '5')]), ['5'])
        self.assertEqual(ttm.tree_cycles([('a', 'b'), ('b', 'c'), ('c', 'a'),
                                          ('d', 'zz')]), ['a'])

    def test_full_load_in_pre_order(self):
        page = self.publish(tree(load='full', ordering=['name'], expand=2))
        body = self.json(page, 'org')
        self.assertEqual([(item['title'], item['depth']) for item in body['nodes']],
                         [('Board', 0), ('Operations', 1), ('Logistics', 2),
                          ('Technology', 1)])
        self.assertEqual(body['nodes'][1]['parent'], str(self.board.pk))
        self.assertFalse(body['truncated'])
        limited = self.publish(tree(load='full', limit=2, ordering=['name']),
                               path='limited')
        self.assertTrue(self.json(limited, 'org')['truncated'])

    def test_a_deep_chain(self):
        parent = None
        for index in range(1500):
            # By id: a chain of instances would be freed recursively.
            parent = Department.objects.create(name='L%04d' % index,
                                               parent_id=parent).pk
        page = self.publish(tree(load='full', limit=2000, ordering=['name']))
        body = self.json(page, 'org')
        self.assertEqual(max(item['depth'] for item in body['nodes']), 1499)

    def test_queries_do_not_grow_with_the_rows(self):
        page = self.publish(tree(ordering=['name']))
        self.json(page, 'org')
        with CaptureQueriesContext(connection) as few:
            self.json(page, 'org')
        for index in range(30):
            self.unit('Root %d' % index)
            self.unit('Leaf %d' % index, self.tech)
        with CaptureQueriesContext(connection) as many:
            body = self.json(page, 'org')
        self.assertEqual(len(body['nodes']), 31)
        self.assertEqual(len(few), len(many))

    def test_a_string_id_and_parent(self):
        source = ModelDataSource(Department, name='tests.ttm.byname',
                                 fields=['id', 'name', 'head'])
        register_datasource(source)
        self.addCleanup(unregister_datasource, source.name)
        Department.objects.filter(pk=self.ops.pk).update(head='Board')
        Department.objects.filter(pk=self.board.pk).update(head='')
        page = self.publish(node('tree', 'org', {
            'datasource': 'tests.ttm.byname', 'title_field': 'name',
            'id_field': 'name', 'parent_field': 'head', 'ordering': ['name']}))
        roots = self.json(page, 'org')['nodes']
        board = [item for item in roots if item['title'] == 'Board'][0]
        self.assertEqual(board['key'], 'Board')
        self.assertTrue(board['children'])
        self.assertEqual(self.titles(self.json(page, 'org', parent='Board')['nodes']),
                         ['Operations'])


# -- timeline -------------------------------------------------------------------------

class TimelineTests(Base):
    def test_newest_first_in_pages(self):
        for index in range(7):
            self.meetup('M%d' % index, days=-index, city='City %d' % index)
        page = self.publish(timeline(page_size=3, subtitle_field='city',
                                     description_field='city', fields=['kind'],
                                     row_links=[MEETUP_LINK]))
        first = self.json(page, 'history')
        self.assertEqual([item['title'] for item in first['items']],
                         ['M0', 'M1', 'M2'])
        item = first['items'][0]
        meetup = Meetup.objects.get(title='M0')
        self.assertEqual(item['url'], reverse('admin:demoapp_meetup_change',
                                              args=[meetup.pk]))
        self.assertEqual((item['subtitle'], item['description'], item['fields']),
                         ('City 0', 'City 0', [{'label': 'Kind', 'value': 'Talk'}]))
        self.assertTrue(item['when'] and item['group'])
        second = self.json(page, 'history', cursor=first['next'])
        self.assertEqual([item['title'] for item in second['items']],
                         ['M3', 'M4', 'M5'])
        last = self.json(page, 'history', cursor=second['next'])
        self.assertEqual(([item['title'] for item in last['items']], last['next']),
                         (['M6'], None))

    def test_the_same_moment_is_not_lost_between_pages(self):
        for index in range(5):
            self.meetup('Same %d' % index)
        page = self.publish(timeline(page_size=2))
        seen, cursor = [], None
        for _round in range(4):
            body = self.json(page, 'history', **({'cursor': cursor} if cursor else {}))
            seen += [item['title'] for item in body['items']]
            cursor = body['next']
            if not cursor:
                break
        self.assertEqual(sorted(seen), ['Same %d' % index for index in range(5)])

    def test_a_range(self):
        self.meetup('Old', days=-40)
        self.meetup('Recent', days=-2)
        self.meetup('Future', days=10)
        page = self.publish(timeline())
        body = self.json(page, 'history',
                         **{'from': (self.now - timedelta(days=5)).isoformat(),
                            'to': (self.now + timedelta(days=1)).isoformat()})
        self.assertEqual([item['title'] for item in body['items']], ['Recent'])
        self.assertEqual(self.get(page, 'history', **{'from': 'yesterday'})
                         .status_code, 400)
        self.assertEqual(self.get(page, 'history', cursor='nope!').status_code, 400)

    def test_colours(self):
        self.meetup('Talk', kind='talk')
        self.meetup('Workshop', kind='workshop', days=-1)
        self.meetup('Social', kind='social', city='Heredia', days=-2)
        page = self.publish(timeline(color_field='kind', colors={
            'talk': '#3498db', 'workshop': 'orange'}, color_rules=[
            {'filter': {'column': 'city', 'op': 'eq', 'value': 'Heredia'},
             'color': '#2ecc71'}]))
        colours = {item['title']: item.get('color')
                   for item in self.json(page, 'history')['items']}
        self.assertEqual(colours, {'Talk': '#3498db', 'Workshop': 'orange',
                                   'Social': '#2ecc71'})

    def test_queries_do_not_grow_with_the_pages(self):
        for index in range(12):
            self.meetup('M%02d' % index, days=-index)
        page = self.publish(timeline(page_size=3, color_field='kind'))
        first = self.json(page, 'history')
        with CaptureQueriesContext(connection) as at_first:
            self.json(page, 'history')
        cursor = first['next']
        for _round in range(2):
            cursor = self.json(page, 'history', cursor=cursor)['next']
        with CaptureQueriesContext(connection) as later:
            self.json(page, 'history', cursor=cursor)
        self.assertEqual(len(at_first), len(later))

    def test_a_date_column(self):
        source = ModelDataSource(PurchaseRequest, name='tests.ttm.bydate',
                                 fields=['id', 'title', 'created_at'])
        register_datasource(source)
        self.addCleanup(unregister_datasource, source.name)
        requester = User.objects.create_user('req')
        for index in range(3):
            row = PurchaseRequest.objects.create(title='P%d' % index, amount=1,
                                                 requester=requester)
            PurchaseRequest.objects.filter(pk=row.pk).update(
                created_at=self.now - timedelta(days=index))
        page = self.publish(node('timeline', 'history', {
            'datasource': 'tests.ttm.bydate', 'title_field': 'title',
            'start_field': 'created_at', 'page_size': 2}))
        body = self.json(page, 'history')
        self.assertEqual([item['title'] for item in body['items']], ['P0', 'P1'])
        self.assertEqual([item['title'] for item in self.json(
            page, 'history', cursor=body['next'])['items']], ['P2'])


# -- metrics --------------------------------------------------------------------------

class MetricsTests(Base):
    def setUp(self):
        super().setUp()
        self.requester = User.objects.create_user('req')
        today = timezone.localdate()
        self.this_month = timezone.now().replace(microsecond=0)
        start = today.replace(day=1)
        self.last_month = timezone.make_aware(
            timezone.datetime.combine(start - timedelta(days=5),
                                      timezone.datetime.min.time())) \
            + timedelta(hours=12)

    def purchase(self, amount, when=None, supplier='ACME'):
        row = PurchaseRequest.objects.create(title='P', amount=Decimal(amount),
                                             supplier=supplier,
                                             requester=self.requester)
        PurchaseRequest.objects.filter(pk=row.pk).update(
            created_at=when or self.this_month)
        return row

    def cards(self, *specs, params=None, **props):
        page = self.publish(metrics(*specs, **props), path='m%d' % self.counter())
        extra = {'params': params} if params is not None else {}
        return {card['key']: card for card in self.json(page, 'kpis', **extra)
                ['metrics']}

    def counter(self):
        self._count = getattr(self, '_count', 0) + 1
        return self._count

    def test_each_aggregate(self):
        self.purchase('10.00', supplier='ACME')
        self.purchase('30.00', supplier='ACME')
        self.purchase('20.00', supplier='Globex')
        cards = self.cards(*[{'label': fn, 'fn': fn, 'column': 'amount'}
                             for fn in ('sum', 'avg', 'min', 'max')],
                           {'label': 'count', 'fn': 'count'},
                           {'label': 'suppliers', 'fn': 'count_distinct',
                            'column': 'supplier'})
        self.assertEqual([cards['m%d' % index]['value'] for index in range(6)],
                         [60.0, 20.0, 10.0, 30.0, 3, 2])
        self.assertEqual(cards['m0']['display'], '60.00')
        self.assertEqual(cards['m4']['display'], '3')
        self.assertFalse(cards['m0']['compare'])
        self.assertNotIn('previous', cards['m0'])

    def test_no_rows(self):
        cards = self.cards({'label': 'sum', 'fn': 'sum', 'column': 'amount'},
                           {'label': 'avg', 'fn': 'avg', 'column': 'amount'})
        self.assertEqual((cards['m0']['value'], cards['m1']['value']), (0, None))
        self.assertEqual(cards['m1']['display'], '—')

    def test_a_filter_per_card(self):
        self.purchase('10.00', supplier='ACME')
        self.purchase('20.00', supplier='Globex')
        cards = self.cards({'label': 'acme', 'fn': 'sum', 'column': 'amount',
                            'filters': [{'column': 'supplier', 'op': 'eq',
                                         'value': 'ACME'}]},
                           {'label': 'all', 'fn': 'sum', 'column': 'amount'})
        self.assertEqual((cards['m0']['value'], cards['m1']['value']), (10.0, 30.0))

    def test_the_previous_period(self):
        self.purchase('30.00')
        self.purchase('20.00', self.last_month)
        self.purchase('5.00', self.last_month - timedelta(days=70))
        cards = self.cards(
            {'label': 'sum', 'fn': 'sum', 'column': 'amount'},
            {'label': 'costs', 'fn': 'sum', 'column': 'amount',
             'higher_is_better': False},
            {'label': 'n', 'fn': 'count', 'compare': False},
            date_field='created_at', period='month')
        card = cards['m0']
        self.assertEqual((card['value'], card['previous'], card['delta'],
                          card['change'], card['trend'], card['good']),
                         (30.0, 20.0, 10.0, 50.0, 'up', True))
        self.assertEqual((card['delta_display'], card['change_display']),
                         ('+10.00', '+50.0 %'))
        self.assertIs(cards['m1']['good'], False)
        self.assertEqual((cards['m2']['value'], cards['m2']['compare']), (1, False))

    def test_an_empty_previous_period_divides_by_nothing(self):
        self.purchase('30.00')
        cards = self.cards({'label': 'sum', 'fn': 'sum', 'column': 'amount'},
                           {'label': 'avg', 'fn': 'avg', 'column': 'amount'},
                           {'label': 'n', 'fn': 'count'},
                           date_field='created_at', period='month')
        self.assertEqual((cards['m0']['previous'], cards['m0']['change'],
                          cards['m0']['trend']), (0, None, 'up'))
        self.assertEqual(cards['m0']['change_display'], '')
        self.assertEqual((cards['m1']['previous'], cards['m1']['change'],
                          cards['m1']['trend']), (None, None, None))
        self.assertEqual((cards['m2']['previous'], cards['m2']['change']), (0, None))

    def test_a_fall_and_no_change(self):
        self.purchase('10.00')
        self.purchase('40.00', self.last_month)
        cards = self.cards({'label': 'sum', 'fn': 'sum', 'column': 'amount'},
                           {'label': 'n', 'fn': 'count'},
                           date_field='created_at', period='month')
        self.assertEqual((cards['m0']['change'], cards['m0']['trend'],
                          cards['m0']['good']), (-75.0, 'down', False))
        self.assertEqual(cards['m0']['change_display'], '−75.0 %')
        self.assertEqual((cards['m1']['trend'], cards['m1']['good']), ('flat', None))

    def test_every_period(self):
        self.purchase('30.00')
        for period in query.PERIODS:
            cards = self.cards({'label': 'n', 'fn': 'count'},
                               date_field='created_at', period=period)
            self.assertEqual(cards['m0']['value'], 1, period)

    def test_period_bounds(self):
        build = ttm.MetricsBuild('k', 'metrics', {}, period='month')
        now = timezone.make_aware(timezone.datetime(2026, 3, 10, 15, 0))
        date_column = Column('d', 'd', 'date')
        current, previous = ttm.period_bounds(build, date_column, now)
        self.assertEqual([str(day) for day in current + previous],
                         ['2026-03-01', '2026-04-01', '2026-02-01', '2026-03-01'])
        build.to_date = True
        current, previous = ttm.period_bounds(build, date_column, now)
        self.assertEqual(str(previous[1]), '2026-02-11')
        moment_column = Column('d', 'd', 'datetime')
        current, previous = ttm.period_bounds(build, moment_column, now)
        self.assertEqual(previous[1] - previous[0], timedelta(days=9, hours=15))

    def test_formats(self):
        metric = {'format': 'currency', 'decimals': 2, 'prefix': '$', 'suffix': ''}
        self.assertEqual(ttm.format_metric(metric, 1234.5), '$1,234.50')
        metric = {'format': 'percent', 'decimals': 1, 'prefix': '', 'suffix': ''}
        self.assertEqual(ttm.format_metric(metric, 0.125), '12.5 %')
        self.assertEqual(ttm.format_metric(metric, -0.5, signed=True),
                         '−50.0 %')
        metric = {'format': 'number', 'decimals': 0, 'prefix': '', 'suffix': ' u'}
        self.assertEqual(ttm.format_metric(metric, 3), '3 u')
        self.assertEqual(ttm.format_metric(metric, None), '—')

    def test_a_card_condition(self):
        self.purchase('10.00')
        cards = self.cards({'label': 'n', 'fn': 'count'},
                           {'label': 'secret', 'fn': 'sum', 'column': 'amount',
                            'condition': {'perm': 'demoapp.delete_purchaserequest'}})
        self.assertEqual(list(cards), ['m0'])

    def test_one_query_for_every_card(self):
        self.purchase('10.00')
        page = self.publish(metrics(*[{'label': fn, 'fn': fn, 'column': 'amount'}
                                      for fn in ('sum', 'avg', 'min', 'max')],
                                    date_field='created_at'), path='one')
        self.json(page, 'kpis')
        with CaptureQueriesContext(connection) as queries:
            self.json(page, 'kpis')
        aggregates = [item for item in queries
                      if 'demoapp_purchaserequest' in item['sql']]
        self.assertEqual(len(aggregates), 1, [item['sql'] for item in aggregates])

    def test_the_page_shows_the_cards(self):
        self.purchase('30.00')
        self.publish(metrics({'label': 'Requested', 'fn': 'sum', 'column': 'amount',
                              'prefix': '$', 'format': 'currency'},
                             date_field='created_at'), path='kpis')
        html = self.page_html('kpis')
        self.assertIn('Requested', html)
        self.assertIn('$30.00', html)
        self.assertIn('vs. the previous month', html)
        self.assertIn('fa-arrow-up', html)
        response = self.get(Page.objects.get(path='kpis'), 'kpis')
        self.assertIn('$30.00', response.json()['html'])
