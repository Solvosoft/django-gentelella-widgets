"""W23: data sources that do not live in the project's database.

The parameters a source can take (``get_queryset(request, params=None)``),
``DataSourceUnavailable`` (502/503/504), ``validate_params`` without reading,
the CSV export that reads its first rows before answering, ``project_model``,
the read-only ``object_management`` (list mode) and ``interactive_grid`` over
any data source, ``default_form`` and the calendar's locale.
"""

import json
import warnings
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.http import StreamingHttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from demoapp import models as demo
from djgentelella.datasources import base as ds_base
from djgentelella.datasources import export as ds_export
from djgentelella.datasources import query
from djgentelella.datasources.base import (
    Column, DataSource, DataSourceUnavailable, FunctionDataSource, ModelDataSource,
    project_model_of, register_datasource, takes_params, unregister_datasource,
)
from djgentelella.designs import engine, publishing, registry
from djgentelella.designs.builds import ObjectManagementBuild
from djgentelella.designs.exposure import expose
from djgentelella.designs.forms import default_form
from djgentelella.designs.regions import calendar_locale
from djgentelella.tests.DesignsPages_Test import grant
from djgentelella.tests.Designs_Test import DesignState, design, node

FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
REMOTE = 'tests.w23.remote'
LOCAL = 'tests.w23.local'


class Unreachable(QuerySet):
    """A queryset whose rows cannot be read: like the rows of an external API
    that is down, read only when the queryset is evaluated."""

    def _fail(self):
        raise DataSourceUnavailable('The provider API is down.')

    def _fetch_all(self):
        if self._result_cache is None:
            self._fail()

    def count(self):
        self._fail()

    def exists(self):
        self._fail()

    def aggregate(self, *args, **kwargs):
        self._fail()

    def iterator(self, *args, **kwargs):
        self._fail()


class RemoteSource(DataSource):
    """Rows that are not rows of a model of the project, as djgentelella sees
    them (``project_model = None``); they take the query parameters."""

    name = REMOTE
    label = 'Remote countries'
    perms = []
    project_model = None

    def __init__(self):
        self.seen = []
        self.down = False

    def columns(self, request):
        return [Column('name', 'Name', 'string'), Column('code', 'Code', 'string'),
                Column('id', 'Id', 'integer', aggregatable=False)]

    def get_queryset(self, request, params=None):
        self.seen.append(params)
        if self.down:
            return Unreachable(model=demo.Country)
        return demo.Country.objects.all()


class Fixture:
    @classmethod
    def setUpTestData(cls):
        cls.cr = demo.Country.objects.create(name='Costa Rica', code='cr')
        cls.pa = demo.Country.objects.create(name='Panama', code='pa')
        cls.ni = demo.Country.objects.create(name='Nicaragua', code='ni')

    def setUp(self):
        super().setUp()
        translation.activate('en')
        self.addCleanup(translation.deactivate)
        self.source = RemoteSource()
        register_datasource(self.source)
        self.addCleanup(unregister_datasource, REMOTE)
        self.request = RequestFactory().get('/')
        self.request.user = User(is_superuser=True, is_active=True)


# -- the data source API -------------------------------------------------------------

class ParamsHookTests(Fixture, TestCase):

    def test_a_source_says_it_takes_the_params_by_its_signature(self):
        self.assertTrue(takes_params(self.source))
        self.assertFalse(takes_params(ModelDataSource(demo.Country, perms=[])))
        self.assertFalse(takes_params(FunctionDataSource(
            lambda request: demo.Country.objects.all(), [], perms=[])))

    def test_apply_params_hands_the_normalized_document(self):
        params = {'filters': [{'column': 'code', 'op': 'eq', 'value': 'cr'}]}
        names = [row.name for row in query.apply_params(self.source, self.request,
                                                        params)]
        self.assertEqual(names, ['Costa Rica'])
        seen = self.source.seen[-1]
        self.assertEqual(seen['filters'], params['filters'])
        self.assertEqual(seen['search'], '')
        self.assertEqual(seen['group_by'], [])

    def test_aggregate_and_pivot_hand_their_documents(self):
        params = {'group_by': ['code'], 'aggregates': [{'fn': 'count'}]}
        rows = query.aggregate(self.source, self.request, params)
        self.assertEqual(len(rows), 3)
        self.assertEqual(self.source.seen[-1]['group_by'], ['code'])
        query.pivot(self.source, self.request,
                    {'pivot': {'rows': 'code', 'columns': 'name'}})
        self.assertEqual(self.source.seen[-1]['pivot']['rows'], 'code')

    def test_each_facet_gets_every_filter_but_its_own(self):
        params = {'filters': [{'column': 'code', 'op': 'in', 'value': ['cr']}]}
        result = query.facets(self.source, self.request, params, ['code', 'name'])
        # The facet of "code" still sees the three codes; "name" only Costa Rica.
        self.assertEqual(sorted(item['value'] for item in result['code']),
                         ['cr', 'ni', 'pa'])
        self.assertEqual([item['value'] for item in result['name']], ['Costa Rica'])
        filters = sorted(json.dumps(seen['filters']) for seen in self.source.seen)
        self.assertEqual(filters, ['[]', json.dumps(params['filters'])])

    def test_a_source_without_params_is_called_as_before(self):
        calls = []

        def rows(request):
            calls.append(request)
            return demo.Country.objects.all()

        source = FunctionDataSource(rows, [Column('name', 'Name', 'string')],
                                    perms=[])
        query.apply_params(source, self.request, {'search': 'pan'})
        query.facets(source, self.request, {}, ['name'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(query.source_queryset(source, self.request, {}).count(), 3)

    def test_the_export_hands_the_params(self):
        params = {'ordering': ['-name']}
        response = ds_export.export(self.source, self.request, params, 'json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.source.seen[-1]['ordering'], ['-name'])


class ValidateWithoutReadingTests(Fixture, TestCase):

    def test_validating_never_reads_the_rows(self):
        self.source.down = True
        params = {'filters': [{'column': 'code', 'op': 'eq', 'value': 'cr'}],
                  'ordering': ['name'], 'group_by': ['code'],
                  'aggregates': [{'fn': 'count'}]}
        clean, errors = query.validate_params(self.source, self.request, params)
        self.assertEqual(errors, [])
        self.assertEqual(clean['ordering'], ['name'])
        # The queryset was built (the ORM checked the values)...
        self.assertEqual(len(self.source.seen), 1)
        # ...and reading it is what fails.
        with self.assertRaises(DataSourceUnavailable):
            list(query.apply_params(self.source, self.request, params))

    def test_build_false_does_not_even_build_it(self):
        clean, errors = query.validate_params(
            self.source, self.request, {'ordering': ['name']}, build=False)
        self.assertEqual(errors, [])
        self.assertEqual(self.source.seen, [])
        _clean, errors = query.validate_params(
            self.source, self.request, {'ordering': ['nope']}, build=False)
        self.assertEqual(len(errors), 1)


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class UnavailableApiTests(Fixture, TestCase):

    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_user('viewer', password='x'))

    def url(self, endpoint):
        if endpoint is None:
            return reverse('gtdatasource', args=[REMOTE])
        return reverse('gtdatasource-' + endpoint, args=[REMOTE])

    def test_a_source_without_a_project_model_works_in_the_api(self):
        body = self.client.get(self.url('rows'), {
            'params': json.dumps({'ordering': ['name']})}).json()
        self.assertEqual([row['name'] for row in body['data']],
                         ['Costa Rica', 'Nicaragua', 'Panama'])
        self.assertEqual(body['recordsTotal'], 3)
        body = self.client.get(self.url('facets'), {'columns': 'code'}).json()
        self.assertEqual(len(body['code']), 3)
        params = json.dumps({'ordering': ['name'], 'columns': ['name']})
        response = self.client.get(self.url('export'), {'fmt': 'csv', 'params': params})
        self.assertEqual(response.status_code, 200)
        text = b''.join(response.streaming_content).decode('utf-8-sig')
        self.assertEqual(text.splitlines(), ['Name', 'Costa Rica', 'Nicaragua',
                                             'Panama'])

    def test_every_endpoint_answers_503(self):
        self.source.down = True
        for endpoint, extra in (('rows', {}), ('aggregate', {}),
                                ('pivot', {'params': json.dumps({'pivot': {
                                    'rows': 'code', 'columns': 'name'}})}),
                                ('facets', {'columns': 'code'}),
                                ('export', {'fmt': 'json'})):
            response = self.client.get(self.url(endpoint), extra)
            self.assertEqual(response.status_code, 503, endpoint)
            self.assertEqual(response.json()['detail'], 'The provider API is down.')
        # The columns do not read rows.
        self.assertEqual(self.client.get(self.url(None)).status_code, 200)

    def test_bad_params_are_still_a_400(self):
        self.source.down = True
        response = self.client.get(self.url('rows'), {
            'params': json.dumps({'ordering': ['nope']})})
        self.assertEqual(response.status_code, 400)

    def test_the_csv_is_an_error_and_not_a_cut_file(self):
        self.source.down = True
        response = self.client.get(self.url('export'), {'fmt': 'csv'})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.streaming)
        self.assertEqual(response.json()['detail'], 'The provider API is down.')

    def test_502_504_and_retry_after(self):
        error = DataSourceUnavailable('Bad answer', status=502, retry_after=30)
        with mock.patch.object(RemoteSource, 'get_queryset', side_effect=error):
            response = self.client.get(self.url('rows'))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response['Retry-After'], '30')
        self.assertEqual(DataSourceUnavailable(status=504).status_code, 504)
        self.assertEqual(DataSourceUnavailable().get_codes(), 'datasource_unavailable')
        with self.assertRaises(ValueError):
            DataSourceUnavailable(status=500)


class CsvFirstChunkTests(Fixture, TestCase):

    def test_the_first_chunk_is_read_before_answering_and_the_rest_streams(self):
        params = {'ordering': ['name'], 'columns': ['code']}
        with mock.patch.object(ds_export, 'CHUNK_SIZE', 2):
            response = ds_export.export_csv(self.source, self.request, params)
            self.assertIsInstance(response, StreamingHttpResponse)
            text = b''.join(response.streaming_content).decode('utf-8-sig')
        self.assertEqual(text.splitlines(), ['Code', 'cr', 'ni', 'pa'])

    def test_a_failing_read_raises_before_the_response(self):
        self.source.down = True
        with self.assertRaises(DataSourceUnavailable):
            ds_export.export_csv(self.source, self.request, {})


class ProjectModelTests(TestCase):

    def test_the_sources_of_djgentelella(self):
        self.assertIs(ModelDataSource(demo.Country, perms=[]).project_model,
                      demo.Country)
        function = FunctionDataSource(lambda request: None, [], model=demo.Country)
        self.assertIs(function.project_model, demo.Country)
        self.assertIsNone(FunctionDataSource(lambda request: None, []).project_model)
        self.assertIsNone(RemoteSource().project_model)

    def test_model_still_works_with_a_deprecation_warning(self):
        class Legacy(DataSource):
            model = demo.Country

        class Explicit(DataSource):
            model = demo.Country    # what it reads, not a model of the project
            project_model = None

        class Duck:
            model = demo.Country

        ds_base._warned.clear()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.assertIs(project_model_of(Legacy()), demo.Country)
            self.assertIs(project_model_of(Duck()), demo.Country)
            self.assertIsNone(project_model_of(Explicit()))
            self.assertIsNone(project_model_of(object()))
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        self.assertEqual(len(deprecations), 2)
        self.assertIn('project_model', str(deprecations[0].message))


class DefaultFormTests(TestCase):

    def test_every_field_a_model_form_shows(self):
        form = default_form(demo.ObjectManagerDemoModel)
        self.assertEqual(form['model'], 'demoapp.ObjectManagerDemoModel')
        self.assertNotIn('id', form['fields'])
        self.assertIn('name', form['fields'])
        self.assertIn('m2m_autocomplete', form['fields'])
        # Concrete fields first, then the many-to-many ones.
        self.assertEqual(form['fields'][-2:],
                         ['m2m_autocomplete', 'm2m_multipleselect'])
        self.assertEqual(default_form(demo.ObjectManagerDemoModel,
                                      fields=['name', 'id', 'yes_no']),
                         {'model': 'demoapp.ObjectManagerDemoModel',
                          'fields': ['name', 'yes_no']})

    def test_it_resolves_as_a_design_form(self):
        expose(demo.Country)
        forms = {'country': default_form(demo.Country)}
        document = design(node('object_management', 'table', {
            'model': 'demoapp.Country', 'form': 'country'}), forms=forms)
        _resolved, errors = engine.resolve(document)
        self.assertEqual(errors, [])


class CalendarLocaleTests(TestCase):

    def test_the_locale_of_the_page(self):
        request = RequestFactory().get('/')
        request.LANGUAGE_CODE = 'pt-BR'
        self.assertEqual(calendar_locale(request), 'pt-br')
        with translation.override('es'):
            self.assertEqual(calendar_locale(RequestFactory().get('/')), 'es')

    def test_only_another_language_loads_the_locales(self):
        component = registry.get_component('calendar')
        build = mock.Mock(initial_view='dayGridMonth', limit=10)
        for code, loads in (('es', True), ('pt-br', True), ('en', False),
                            ('en-us', False)):
            request = RequestFactory().get('/')
            request.LANGUAGE_CODE = code
            config = component.config(build, mock.Mock(request=request))
            self.assertEqual(config['locale'], code)
            self.assertEqual('locales' in config, loads, code)
            if loads:
                self.assertTrue(config['locales'].endswith(
                    'vendors/fullcalendar/locales-all.global.min.js'))


# -- read-only components over any data source --------------------------------------

def listing(**props):
    return node('object_management', 'list', {'datasource': REMOTE,
                                              'list_fields': ['name', 'code'],
                                              **props})


def grid(**props):
    return node('interactive_grid', 'grid', {'datasource': REMOTE,
                                             'columns': ['name', 'code'], **props})


@override_settings(LANGUAGE_CODE='en', ALLOWED_HOSTS=['*'],
                   PASSWORD_HASHERS=FAST_HASHERS)
class ReadOnlyBase(Fixture, DesignState, TestCase):

    def setUp(self):
        super().setUp()
        registry.get_components()
        self.user = User.objects.create_user('ana', password='pw')
        self.client.force_login(self.user)

    def errors(self, *nodes):
        _resolved, errors = engine.resolve(design(*nodes))
        return [(error.path, error.message) for error in errors]

    def assertError(self, document_node, text):
        errors = self.errors(document_node)
        self.assertTrue(any(text in message for _where, message in errors), errors)

    def publish(self, *nodes):
        page, errors = publishing.publish(design(*nodes), path='w23')
        self.assertEqual(errors, [])
        return page

    def get(self, page, node_id, **params):
        url = reverse('gt-design-endpoint', kwargs={
            'page_id': page.pk, 'node_id': node_id, 'rest': ''})
        return self.client.get(url, params)


class ListModeTests(ReadOnlyBase):

    def test_it_resolves_without_a_model_or_a_form(self):
        resolved, errors = engine.resolve(design(listing()))
        self.assertEqual(errors, [])
        build = resolved.nodes['list'].build
        self.assertIsInstance(build, ObjectManagementBuild)
        self.assertTrue(build.list_only)
        self.assertIsNone(build.model)
        self.assertEqual(build.list_fields, ['name', 'code'])
        self.assertEqual(build.search_fields, ['name', 'code'])
        self.assertEqual(build.title, 'Remote countries')
        self.assertEqual([column['name'] for column in build.source_columns],
                         ['name', 'code'])

    def test_what_a_list_cannot_have(self):
        self.assertError(listing(form='x'), "has no 'form'")
        self.assertError(listing(action_conditions={'create': {'perm': 'a.b'}}),
                         "has no 'action_conditions'")
        self.assertError(listing(optimistic_lock=True), 'nothing to lock')
        self.assertError(listing(perms={'create': []}), "no 'create' permissions")
        self.assertError(listing(row_links=[{'url_name': 'x', 'title': 'x'}]),
                         'row links need a data source over a model')
        self.assertError(listing(list_fields=['nope']), "'nope' is not a column")
        self.assertError(listing(search_fields=['id']), "'id' is not a text column")
        self.assertError(listing(ordering=['nope']), "unknown field 'nope'")
        self.assertError(node('object_management', 'x', {'model': 'demoapp.Country'}),
                         'form is required')

    def test_the_page_and_the_rows(self):
        page = self.publish(listing(ordering=['name']))
        response = self.client.get('/designs/w23')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('"readonly": true', content)
        self.assertNotIn('_create_modal', content)
        body = self.get(page, 'list', draw=4, offset=0, limit=2).json()
        self.assertEqual(body['draw'], 4)
        self.assertEqual(body['recordsTotal'], 3)
        self.assertEqual(body['recordsFiltered'], 3)
        self.assertEqual([row['name'] for row in body['data']],
                         ['Costa Rica', 'Nicaragua'])
        row = body['data'][0]
        self.assertEqual(row['id'], self.cr.pk)
        self.assertEqual(set(row), {'pk', 'id', 'name', 'code', 'actions'})
        self.assertFalse(any(row['actions'].values()))
        body = self.get(page, 'list', search='pan', ordering='-name').json()
        self.assertEqual([row['name'] for row in body['data']], ['Panama'])
        body = self.get(page, 'list', ordering='-id').json()
        self.assertEqual(body['data'][0]['name'], 'Nicaragua')
        filters = [{'column': 'code', 'op': 'in', 'value': ['cr', 'ni']}]
        body = self.get(page, 'list', gtfilters=json.dumps(filters)).json()
        self.assertEqual(body['recordsFiltered'], 2)
        self.assertEqual(self.get(page, 'list', gtfilters='[1]').status_code, 400)

    def test_a_hidden_column(self):
        page = self.publish(listing(column_conditions={'code': {'perm': 'x.nope'}}))
        body = self.get(page, 'list', ordering='code').json()
        self.assertEqual(set(body['data'][0]), {'pk', 'id', 'name', 'actions'})
        # Neither searched, nor filtered, nor ordered by.
        # "cr" is only the code of Costa Rica: the hidden column is not searched.
        self.assertEqual(self.get(page, 'list', search='cr').json()['recordsFiltered'],
                         0)
        filters = [{'column': 'code', 'op': 'eq', 'value': 'cr'}]
        self.assertEqual(self.get(page, 'list',
                                  gtfilters=json.dumps(filters)).status_code, 400)

    def test_permissions(self):
        page = self.publish(listing(perms={'list': ['demoapp.view_country']}))
        self.assertEqual(self.get(page, 'list').status_code, 403)
        grant(self.user, 'demoapp.view_country')
        self.assertEqual(self.get(page, 'list').status_code, 200)
        self.source.perms = ['demoapp.add_country']
        self.addCleanup(setattr, self.source, 'perms', [])
        self.assertEqual(self.get(page, 'list').status_code, 403)

    def test_an_unavailable_source_is_a_503(self):
        page = self.publish(listing())
        self.source.down = True
        response = self.get(page, 'list')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['detail'], 'The provider API is down.')

    def test_a_facets_panel_filters_it_through_the_data_source(self):
        resolved, errors = engine.resolve(design(
            listing(), node('facets', 'filters', {'target': 'list',
                                                  'columns': ['code']})))
        self.assertEqual(errors, [])
        self.assertEqual(resolved.nodes['filters'].build.datasource, REMOTE)

    def test_over_a_source_of_a_project_model_it_has_row_links(self):
        expose(demo.Country)
        register_datasource(ModelDataSource(demo.Country, name=LOCAL, perms=[]))
        self.addCleanup(unregister_datasource, LOCAL)
        resolved, errors = engine.resolve(design(listing(
            datasource=LOCAL, row_links=[{'url_name': 'admin:demoapp_country_change',
                                          'title': 'Open'}])))
        self.assertEqual(errors, [])
        build = resolved.nodes['list'].build
        self.assertIs(build.model, demo.Country)
        self.assertTrue(build.list_only)
        self.assertEqual(len(build.row_links), 1)


class ReadOnlyGridTests(ReadOnlyBase):

    def test_it_resolves_read_only(self):
        resolved, errors = engine.resolve(design(grid()))
        self.assertEqual(errors, [])
        build = resolved.nodes['grid'].build
        self.assertTrue(build.list_only)
        self.assertEqual(build.editable, [])
        self.assertEqual(build.actions, [])
        self.assertEqual(build.ordering, ['pk'])

    def test_it_cannot_edit(self):
        self.assertError(grid(editable=['name']), "it has no 'editable'")
        self.assertError(grid(actions=['create']), "it has no 'actions'")
        self.assertError(grid(columns=['nope']), "'nope' is not a column")

    def test_the_page_and_the_rows(self):
        page = self.publish(grid(ordering=['-name'], page_size=2))
        content = self.client.get('/designs/w23').content.decode()
        self.assertNotIn('gtgrid-save', content)
        self.assertNotIn('gtgrid-add', content)
        self.assertIn('"editable": false', content)
        body = self.get(page, 'grid', limit=2, offset=0).json()
        self.assertEqual(body['count'], 3)
        self.assertEqual([row['name'] for row in body['data']], ['Panama', 'Nicaragua'])
        self.assertEqual(body['data'][0], {'id': self.pa.pk, 'name': 'Panama',
                                           'code': 'pa', 'readonly': [],
                                           'actions': {'update': False,
                                                       'destroy': False}})
        body = self.get(page, 'grid', search='cos').json()
        self.assertEqual([row['name'] for row in body['data']], ['Costa Rica'])

    def test_an_unavailable_source_is_a_503(self):
        page = self.publish(grid())
        self.source.down = True
        self.assertEqual(self.get(page, 'grid').status_code, 503)

    def test_a_model_data_source_still_edits(self):
        expose(demo.Country)
        register_datasource(ModelDataSource(demo.Country, name=LOCAL, perms=[]))
        self.addCleanup(unregister_datasource, LOCAL)
        resolved, errors = engine.resolve(design(grid(datasource=LOCAL)))
        self.assertEqual(errors, [])
        build = resolved.nodes['grid'].build
        self.assertFalse(build.list_only)
        self.assertEqual(build.editable, ['name', 'code'])


class RegionUnavailableTests(ReadOnlyBase):

    def test_cards_over_an_unavailable_source_are_a_503(self):
        page = self.publish(node('cards', 'list', {'datasource': REMOTE,
                                                   'title_field': 'name'}))
        self.assertEqual(self.get(page, 'list').status_code, 200)
        self.source.down = True
        self.assertEqual(self.get(page, 'list').status_code, 503)


class ValidationErrorIsNotUnavailable(TestCase):

    def test_they_are_different_exceptions(self):
        self.assertFalse(issubclass(DataSourceUnavailable, ValidationError))
