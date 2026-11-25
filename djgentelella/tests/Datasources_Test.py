"""djgentelella.datasources: columns, query engine, facets, exports and API."""
import csv
import datetime
import io
import json
from unittest import mock, skipUnless

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models import F
from django.test import RequestFactory, TestCase, override_settings, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone, translation

from demoapp import models as demo
from djgentelella.datasources import base as ds_base
from djgentelella.datasources import export as ds_export
from djgentelella.datasources import query
from djgentelella.datasources.base import (
    Column, FunctionDataSource, ModelDataSource, get_datasource,
    register_datasource, unregister_datasource,
)

#: Each test signs users in: a fast hasher keeps it from spending seconds
#: per test hashing their passwords (PBKDF2).
FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

try:
    import openpyxl
except ImportError:  # the `export` extra
    openpyxl = None
try:
    import xhtml2pdf
    from pypdf import PdfReader
except ImportError:  # the `pdf` extra
    xhtml2pdf = None

User = get_user_model()

OBJECT_FIELDS = ['id', 'name', 'float_number', 'knob_number', 'born_date',
                 'last_time', 'description', 'radio_elements', 'yes_no',
                 'field_autocomplete', 'm2m_autocomplete']


def aware(*args):
    return timezone.make_aware(datetime.datetime(*args))


class DataSourceFixture:
    """Three ObjectManagerDemoModel rows that cover every column kind."""

    @classmethod
    def setUpTestData(cls):
        cls.cr = demo.Country.objects.create(name='Costa Rica', code='cr')
        cls.pa = demo.Country.objects.create(name='Panama', code='pa')
        community = demo.Community.objects.create(name='Community')
        common = {'livetime_range': '', 'simple_archive': 'a.txt',
                  'chunked_archive': 'b.txt', 'taging_list': '',
                  'field_select': community}
        cls.alpha = demo.ObjectManagerDemoModel.objects.create(
            name='Alpha', float_number=1.5, knob_number=10,
            born_date=datetime.date(2026, 1, 15),
            last_time=aware(2026, 1, 15, 10, 0), description='red apple',
            radio_elements=1, yes_no=True, field_autocomplete=cls.cr, **common)
        cls.beta = demo.ObjectManagerDemoModel.objects.create(
            name='Beta', float_number=2.5, knob_number=20,
            born_date=datetime.date(2026, 2, 10),
            last_time=aware(2026, 2, 10, 10, 0), description='green pear',
            radio_elements=2, yes_no=False, field_autocomplete=cls.pa, **common)
        cls.gamma = demo.ObjectManagerDemoModel.objects.create(
            name='Gamma', float_number=10.0, knob_number=30,
            born_date=datetime.date(2025, 12, 31),
            last_time=aware(2025, 12, 31, 10, 0), description='red cherry',
            radio_elements=3, yes_no=True, field_autocomplete=cls.cr, **common)
        cls.alpha.m2m_autocomplete.set([cls.cr, cls.pa])
        cls.beta.m2m_autocomplete.set([cls.pa])
        cls.cal_a = demo.Calendar.objects.create(title='A', options={'a': 1})
        cls.cal_b = demo.Calendar.objects.create(title='B', options=None)
        cls.cal_c = demo.Calendar.objects.create(title='C', options={'a': 2})

    def setUp(self):
        # The demo speaks Spanish; the expected labels here are the English.
        translation.activate('en')
        self.addCleanup(translation.deactivate)
        self.source = ModelDataSource(demo.ObjectManagerDemoModel,
                                      name='test.objects', fields=OBJECT_FIELDS,
                                      perms=[])
        self.json_source = ModelDataSource(demo.Calendar, name='test.calendars',
                                           fields=['id', 'title', 'options'],
                                           perms=[])
        self.request = RequestFactory().get('/')
        self.request.user = AnonymousUser()

    def names(self, params, source=None):
        source = source or self.source
        return {getattr(o, 'name', None) or o.title
                for o in query.apply_params(source, self.request, params)}


class ColumnsTest(DataSourceFixture, TestCase):

    def test_kinds_come_from_the_model(self):
        kinds = {c.name: c.kind for c in self.source.columns(self.request)}
        self.assertEqual(kinds, {
            'id': 'integer', 'name': 'string', 'float_number': 'decimal',
            'knob_number': 'integer', 'born_date': 'date',
            'last_time': 'datetime', 'description': 'text',
            'radio_elements': 'choices', 'yes_no': 'boolean',
            'field_autocomplete': 'fk', 'm2m_autocomplete': 'm2m'})
        self.assertEqual(self.json_source.column_map(self.request)['options'].kind,
                         'json')

    def test_aggregatable_and_sortable_defaults(self):
        cols = self.source.column_map(self.request)
        self.assertTrue(cols['knob_number'].aggregatable)
        self.assertTrue(cols['float_number'].aggregatable)
        self.assertFalse(cols['id'].aggregatable)
        self.assertFalse(cols['name'].aggregatable)
        self.assertFalse(cols['m2m_autocomplete'].sortable)
        self.assertEqual(cols['radio_elements'].choices,
                         [(1, 'A'), (2, 'B'), (3, 'C'), (4, 'D')])

    def test_default_fields_and_exclude(self):
        source = ModelDataSource(demo.Person, exclude=['last_time'])
        names = [c.name for c in source.columns(self.request)]
        self.assertEqual(names, ['id', 'name', 'num_children', 'country',
                                 'born_date'])
        self.assertEqual(source.name, 'demoapp.person')
        self.assertEqual(source.perms, ['demoapp.view_person'])

    def test_related_path(self):
        source = ModelDataSource(demo.Person, fields=['country__name'])
        column = source.columns(self.request)[0]
        self.assertEqual((column.kind, column.label), ('string', 'Country name'))

    def test_unknown_kind(self):
        with self.assertRaises(ValueError):
            Column('x', 'X', 'money')


#: (column, op, value, expected names) -- every operator of every kind.
CASES = [
    # string
    ('name', 'eq', 'Alpha', {'Alpha'}),
    ('name', 'ne', 'Alpha', {'Beta', 'Gamma'}),
    ('name', 'in', ['Alpha', 'Beta'], {'Alpha', 'Beta'}),
    ('name', 'contains', 'mm', {'Gamma'}),
    ('name', 'icontains', 'ALP', {'Alpha'}),
    ('name', 'startswith', 'Be', {'Beta'}),
    ('name', 'isnull', False, {'Alpha', 'Beta', 'Gamma'}),
    # text
    ('description', 'eq', 'red apple', {'Alpha'}),
    ('description', 'ne', 'red apple', {'Beta', 'Gamma'}),
    ('description', 'in', ['green pear'], {'Beta'}),
    ('description', 'contains', 'red', {'Alpha', 'Gamma'}),
    ('description', 'icontains', 'PEAR', {'Beta'}),
    ('description', 'startswith', 'green', {'Beta'}),
    ('description', 'isnull', True, set()),
    # integer
    ('knob_number', 'eq', 20, {'Beta'}),
    ('knob_number', 'ne', '20', {'Alpha', 'Gamma'}),
    ('knob_number', 'lt', 20, {'Alpha'}),
    ('knob_number', 'lte', 20, {'Alpha', 'Beta'}),
    ('knob_number', 'gt', 20, {'Gamma'}),
    ('knob_number', 'gte', 20, {'Beta', 'Gamma'}),
    ('knob_number', 'in', [10, '30'], {'Alpha', 'Gamma'}),
    ('knob_number', 'between', [15, 30], {'Beta', 'Gamma'}),
    ('knob_number', 'isnull', False, {'Alpha', 'Beta', 'Gamma'}),
    # decimal
    ('float_number', 'eq', '2.5', {'Beta'}),
    ('float_number', 'ne', 2.5, {'Alpha', 'Gamma'}),
    ('float_number', 'lt', 2.5, {'Alpha'}),
    ('float_number', 'lte', 2.5, {'Alpha', 'Beta'}),
    ('float_number', 'gt', 2.5, {'Gamma'}),
    ('float_number', 'gte', '2.5', {'Beta', 'Gamma'}),
    ('float_number', 'in', [1.5, 10], {'Alpha', 'Gamma'}),
    ('float_number', 'between', [2, None], {'Beta', 'Gamma'}),
    ('float_number', 'isnull', True, set()),
    # boolean
    ('yes_no', 'eq', 'true', {'Alpha', 'Gamma'}),
    ('yes_no', 'ne', True, {'Beta'}),
    ('yes_no', 'isnull', 'false', {'Alpha', 'Beta', 'Gamma'}),
    # date
    ('born_date', 'eq', '2026-01-15', {'Alpha'}),
    ('born_date', 'ne', '2026-01-15', {'Beta', 'Gamma'}),
    ('born_date', 'lt', '2026-01-15', {'Gamma'}),
    ('born_date', 'lte', '2026-01-15', {'Alpha', 'Gamma'}),
    ('born_date', 'gt', '2026-01-15', {'Beta'}),
    ('born_date', 'gte', '2026-01-15', {'Alpha', 'Beta'}),
    ('born_date', 'in', ['2026-01-15', '2026-02-10'], {'Alpha', 'Beta'}),
    ('born_date', 'between', ['2026-01-01', '2026-01-31'], {'Alpha'}),
    ('born_date', 'isnull', False, {'Alpha', 'Beta', 'Gamma'}),
    ('born_date', 'date_period', {'period': 'year', 'date': '2026-06-01'},
     {'Alpha', 'Beta'}),
    # datetime
    ('last_time', 'eq', '2026-01-15T10:00:00', {'Alpha'}),
    ('last_time', 'ne', '2026-01-15T10:00:00', {'Beta', 'Gamma'}),
    ('last_time', 'lt', '2026-01-15', {'Gamma'}),
    ('last_time', 'lte', '2026-01-15T10:00:00', {'Alpha', 'Gamma'}),
    ('last_time', 'gt', '2026-01-16', {'Beta'}),
    ('last_time', 'gte', '2026-01-15', {'Alpha', 'Beta'}),
    ('last_time', 'in', ['2026-02-10T10:00:00'], {'Beta'}),
    ('last_time', 'between', ['2026-01-01', '2026-01-31'], {'Alpha'}),
    # A date-only upper bound takes in the whole day.
    ('last_time', 'between', ['2026-01-15', '2026-01-15'], {'Alpha'}),
    ('last_time', 'isnull', True, set()),
    ('last_time', 'date_period', {'period': 'month', 'date': '2026-02-27'},
     {'Beta'}),
    # fk
    ('field_autocomplete', 'eq', 'PA', {'Beta'}),
    ('field_autocomplete', 'ne', 'PA', {'Alpha', 'Gamma'}),
    ('field_autocomplete', 'in', ['CR'], {'Alpha', 'Gamma'}),
    ('field_autocomplete', 'isnull', False, {'Alpha', 'Beta', 'Gamma'}),
    # m2m: a row matching on two related objects is still one row
    ('m2m_autocomplete', 'eq', 'PA', {'Alpha', 'Beta'}),
    ('m2m_autocomplete', 'in', ['CR', 'PA'], {'Alpha', 'Beta'}),
    ('m2m_autocomplete', 'isnull', True, {'Gamma'}),
    # choices
    ('radio_elements', 'eq', '2', {'Beta'}),
    ('radio_elements', 'ne', 2, {'Alpha', 'Gamma'}),
    ('radio_elements', 'in', [1, 3], {'Alpha', 'Gamma'}),
    ('radio_elements', 'isnull', False, {'Alpha', 'Beta', 'Gamma'}),
]

JSON_CASES = [
    ('options', 'eq', {'a': 1}, {'A'}),
    ('options', 'ne', {'a': 1}, {'B', 'C'}),  # ne keeps NULL
    ('options', 'isnull', True, {'B'}),
]


class ApplyParamsTest(DataSourceFixture, TestCase):

    def value(self, value):
        # Country placeholders: the pks are only known at run time.
        mapping = {'CR': self.cr.pk, 'PA': self.pa.pk}
        if isinstance(value, list):
            return [mapping.get(v, v) for v in value]
        return mapping.get(value, value) if isinstance(value, str) else value

    def test_every_operator_of_every_kind(self):
        for column, op, value, expected in CASES:
            with self.subTest(column=column, op=op, value=value):
                params = {'filters': [{'column': column, 'op': op,
                                       'value': self.value(value)}]}
                result = query.apply_params(self.source, self.request, params)
                self.assertEqual({o.name for o in result}, expected)
                # No duplicated rows (the m2m filters go through a subquery).
                self.assertEqual(result.count(), len(expected))
        for column, op, value, expected in JSON_CASES:
            with self.subTest(column=column, op=op):
                params = {'filters': [{'column': column, 'op': op,
                                       'value': value}]}
                self.assertEqual(
                    {o.title for o in query.apply_params(
                        self.json_source, self.request, params)}, expected)

    def test_cases_cover_the_operator_table(self):
        kinds = {c.name: c.kind for c in self.source.columns(self.request)}
        kinds['options'] = 'json'
        covered = {(kinds[c], op) for c, op, _v, _e in CASES + JSON_CASES}
        expected = {(kind, op) for kind, ops in query.OPERATORS_BY_KIND.items()
                    for op in ops}
        self.assertEqual(covered, expected)

    def test_date_period_offset(self):
        today = timezone.localdate()
        self.beta.born_date = today
        self.beta.save()
        params = {'filters': [{'column': 'born_date', 'op': 'date_period',
                               'value': {'period': 'week', 'offset': 0}}]}
        self.assertIn('Beta', self.names(params))
        params['filters'][0]['value']['offset'] = -1
        self.assertNotIn('Beta', self.names(params))
        for period in query.PERIODS:
            params['filters'][0]['value'] = {'period': period}
            self.assertIn('Beta', self.names(params))

    def test_several_filters_are_and(self):
        params = {'filters': [
            {'column': 'yes_no', 'op': 'eq', 'value': True},
            {'column': 'knob_number', 'op': 'gt', 'value': 15}]}
        self.assertEqual(self.names(params), {'Gamma'})

    def test_rejects_unknown_columns(self):
        with self.assertRaises(ValidationError):
            self.names({'filters': [{'column': 'field_select', 'op': 'eq',
                                     'value': 1}]})
        with self.assertRaises(ValidationError):
            self.names({'filters': [{'column': 'name__startswith',
                                     'op': 'eq', 'value': 'A'}]})
        with self.assertRaises(ValidationError):
            self.names({'ordering': ['-password']})
        with self.assertRaises(ValidationError):
            query.selected_columns(self.source, self.request,
                                   {'columns': ['name', 'nope']})

    def test_rejects_operators_not_allowed_for_the_kind(self):
        bad = [('knob_number', 'icontains', '1'), ('yes_no', 'gt', True),
               ('name', 'date_period', {'period': 'year'}),
               ('name', 'between', ['a', 'b']), ('field_autocomplete', 'lt', 1),
               ('m2m_autocomplete', 'ne', 1), ('options', 'contains', 'a'),
               ('name', 'regex', '.*')]
        for column, op, value in bad:
            with self.subTest(column=column, op=op):
                source = self.json_source if column == 'options' else self.source
                with self.assertRaises(ValidationError):
                    query.apply_params(source, self.request, {'filters': [
                        {'column': column, 'op': op, 'value': value}]})

    def test_rejects_invalid_values(self):
        bad = [('knob_number', 'eq', 'abc'), ('knob_number', 'eq', 1.5),
               ('float_number', 'eq', 'x'), ('yes_no', 'eq', 'maybe'),
               ('born_date', 'eq', '2026-13-01'), ('radio_elements', 'eq', 9),
               ('knob_number', 'between', [1]),
               ('born_date', 'date_period', {'period': 'century'}),
               ('born_date', 'date_period', '2026'),
               # Out of the calendar: year 10000 and a timedelta overflow.
               ('born_date', 'date_period', {'period': 'year', 'offset': 100000}),
               ('born_date', 'date_period', {'period': 'month',
                                             'offset': -10 ** 6}),
               ('born_date', 'date_period', {'period': 'day', 'offset': 10 ** 12}),
               ('last_time', 'date_period', {'period': 'week',
                                             'offset': 10 ** 12}),
               # fk / m2m values are read with the related primary key.
               ('field_autocomplete', 'eq', 'abc'),
               ('field_autocomplete', 'in', [1, 'abc']),
               ('field_autocomplete', 'ne', 'abc'),
               ('m2m_autocomplete', 'eq', 'abc'),
               ('m2m_autocomplete', 'in', ['x'])]
        for column, op, value in bad:
            with self.subTest(column=column, value=value):
                with self.assertRaises(ValidationError):
                    self.names({'filters': [{'column': column, 'op': op,
                                             'value': value}]})

    def test_fk_values_as_strings(self):
        pk = str(self.pa.pk)
        self.assertEqual(self.names({'filters': [
            {'column': 'field_autocomplete', 'op': 'eq', 'value': pk}]}),
            {'Beta'})
        self.assertEqual(self.names({'filters': [
            {'column': 'm2m_autocomplete', 'op': 'in', 'value': [pk]}]}),
            {'Alpha', 'Beta'})

    def test_bad_highlight_value(self):
        queryset = query.apply_params(self.source, self.request, {})
        with self.assertRaises(ValidationError):
            query.highlight_classes(
                self.source, self.request, queryset, [self.alpha.pk],
                [{'filter': {'column': 'field_autocomplete', 'op': 'eq',
                             'value': 'abc'}}])

    def test_rejects_malformed_documents(self):
        for params in ('{nope', '[]', {'filters': {}}, {'filters': ['x']},
                       {'search': 1}, {'pivot': []}):
            with self.subTest(params=params):
                with self.assertRaises(ValidationError):
                    self.names(params)

    def test_params_as_json_string(self):
        params = json.dumps({'filters': [{'column': 'name', 'op': 'eq',
                                          'value': 'Beta'}]})
        self.assertEqual(self.names(params), {'Beta'})

    def test_search_icontains_on_text_columns(self):
        self.assertEqual(self.names({'search': 'RED'}), {'Alpha', 'Gamma'})
        self.assertEqual(self.names({'search': 'bet'}), {'Beta'})
        self.assertEqual(self.names({'search': '  '}), {'Alpha', 'Beta', 'Gamma'})

    def test_ordering(self):
        result = query.apply_params(self.source, self.request,
                                    {'ordering': ['-knob_number']})
        self.assertEqual([o.name for o in result], ['Gamma', 'Beta', 'Alpha'])
        result = query.apply_params(self.source, self.request,
                                    {'ordering': ['born_date']})
        self.assertEqual([o.name for o in result], ['Gamma', 'Alpha', 'Beta'])
        with self.assertRaises(ValidationError):
            query.apply_params(self.source, self.request,
                               {'ordering': ['m2m_autocomplete']})

    def test_serialize_rows(self):
        queryset = query.apply_params(self.source, self.request,
                                      {'ordering': ['name']})
        columns = query.selected_columns(
            self.source, self.request,
            {'columns': ['name', 'field_autocomplete', 'm2m_autocomplete',
                         'radio_elements']})
        rows = query.serialize_rows(self.source, self.request, queryset, columns)
        self.assertEqual(rows[0]['field_autocomplete'],
                         {'id': self.cr.pk, 'display_name': 'Costa Rica'})
        self.assertEqual(sorted(r['display_name'] for r in
                                rows[0]['m2m_autocomplete']),
                         ['Costa Rica', 'Panama'])
        self.assertEqual(rows[2]['m2m_autocomplete'], [])
        self.assertEqual(rows[0]['radio_elements'], 1)
        shown = query.serialize_rows(self.source, self.request, queryset, columns,
                                     display=True)
        self.assertEqual(shown[0]['field_autocomplete'], 'Costa Rica')
        self.assertEqual(shown[1]['m2m_autocomplete'], 'Panama')
        self.assertEqual(shown[1]['radio_elements'], 'B')
        self.assertEqual(set(rows[0]), {'pk', 'name', 'field_autocomplete',
                                        'm2m_autocomplete', 'radio_elements'})

    def test_highlights(self):
        queryset = query.apply_params(self.source, self.request, {})
        pks = [self.alpha.pk, self.beta.pk, self.gamma.pk]
        css = query.highlight_classes(self.source, self.request, queryset, pks, [
            {'filter': {'column': 'knob_number', 'op': 'gt', 'value': 15},
             'css': 'table-danger'},
            {'filter': {'column': 'yes_no', 'op': 'eq', 'value': True},
             'css': 'bold'}])
        self.assertEqual(css, {self.beta.pk: 'table-danger',
                               self.gamma.pk: 'table-danger bold',
                               self.alpha.pk: 'bold'})


class AggregateTest(DataSourceFixture, TestCase):

    def test_totals_without_group_by(self):
        result = query.aggregate(self.source, self.request, {'aggregates': [
            {'column': 'knob_number', 'fn': 'sum'},
            {'column': 'knob_number', 'fn': 'avg'},
            {'column': 'float_number', 'fn': 'max'},
            {'column': 'born_date', 'fn': 'min'},
            {'column': 'field_autocomplete', 'fn': 'count_distinct'},
            {'fn': 'count'}]})
        self.assertEqual(result, [{
            'knob_number__sum': 60, 'knob_number__avg': 20.0,
            'float_number__max': 10.0,
            'born_date__min': datetime.date(2025, 12, 31),
            'field_autocomplete__count_distinct': 2, 'count': 3}])

    def test_filters_apply_before_aggregating(self):
        result = query.aggregate(self.source, self.request, {
            'filters': [{'column': 'yes_no', 'op': 'eq', 'value': True}],
            'aggregates': [{'column': 'knob_number', 'fn': 'sum'}]})
        self.assertEqual(result, [{'knob_number__sum': 40}])

    def test_group_by_fk(self):
        result = query.aggregate(self.source, self.request, {
            'group_by': ['field_autocomplete'],
            'aggregates': [{'column': 'knob_number', 'fn': 'sum'},
                           {'fn': 'count'}]})
        by_country = {r['field_autocomplete__display']: r for r in result}
        self.assertEqual(by_country['Costa Rica']['knob_number__sum'], 40)
        self.assertEqual(by_country['Costa Rica']['count'], 2)
        self.assertEqual(by_country['Panama']['knob_number__sum'], 20)
        self.assertEqual(by_country['Panama']['field_autocomplete'], self.pa.pk)

    def test_group_by_two_columns_and_choices(self):
        result = query.aggregate(self.source, self.request, {
            'group_by': ['yes_no', 'radio_elements'],
            'aggregates': [{'fn': 'count'}]})
        self.assertEqual(
            [(r['yes_no'], r['radio_elements'], r['radio_elements__display'],
              r['count']) for r in result],
            [(False, 2, 'B', 1), (True, 1, 'A', 1), (True, 3, 'C', 1)])

    def test_group_by_period(self):
        result = query.aggregate(self.source, self.request, {
            'group_by': [{'column': 'last_time', 'period': 'year'}],
            'aggregates': [{'column': 'knob_number', 'fn': 'sum'}]})
        self.assertEqual(result, [
            {'last_time': datetime.date(2025, 1, 1), 'knob_number__sum': 30},
            {'last_time': datetime.date(2026, 1, 1), 'knob_number__sum': 30}])
        result = query.aggregate(self.source, self.request, {
            'group_by': [{'column': 'born_date', 'period': 'month'}]})
        self.assertEqual([r['born_date'].month for r in result], [12, 1, 2])

    def test_invalid_aggregates(self):
        for spec in ({'column': 'name', 'fn': 'sum'},
                     {'column': 'id', 'fn': 'avg'},
                     {'column': 'knob_number', 'fn': 'median'},
                     {'column': 'nope', 'fn': 'count'}):
            with self.subTest(spec=spec):
                with self.assertRaises(ValidationError):
                    query.aggregate(self.source, self.request,
                                    {'aggregates': [spec]})
        with self.assertRaises(ValidationError):
            query.aggregate(self.source, self.request,
                            {'group_by': [{'column': 'name', 'period': 'month'}]})

    def test_ordered_by_value_with_a_limit_in_the_database(self):
        params = {'group_by': ['name'],
                  'aggregates': [{'column': 'knob_number', 'fn': 'sum'}]}
        with CaptureQueriesContext(connection) as queries:
            result = query.aggregate(self.source, self.request, params,
                                     order_by_value=True, limit=2)
        self.assertEqual([(r['name'], r['knob_number__sum']) for r in result],
                         [('Gamma', 30), ('Beta', 20)])
        self.assertIn('LIMIT 2', queries[-1]['sql'].upper())
        # Ties keep the order of the group values.
        result = query.aggregate(self.source, self.request,
                                 {'group_by': ['yes_no']},
                                 order_by_value=True)
        self.assertEqual([(r['yes_no'], r['count']) for r in result],
                         [(True, 2), (False, 1)])

    def test_ordered_by_value_with_negative_values(self):
        self.gamma.knob_number = -5
        self.gamma.save()
        result = query.aggregate(self.source, self.request, {
            'group_by': ['name'],
            'aggregates': [{'column': 'knob_number', 'fn': 'sum'}]},
            order_by_value=True)
        self.assertEqual([r['name'] for r in result], ['Beta', 'Alpha', 'Gamma'])

    @override_settings(GT_DATASOURCE_MAX_GROUPS=2)
    def test_too_many_groups(self):
        params = {'group_by': ['name']}
        with self.assertRaisesMessage(ValidationError, 'More than 2 groups'):
            query.aggregate(self.source, self.request, params)
        # A limit under the cap only reads that many.
        self.assertEqual(len(query.aggregate(self.source, self.request, params,
                                             limit=2)), 2)
        # Under the cap, nothing changes.
        self.assertEqual(
            [r['yes_no'] for r in query.aggregate(self.source, self.request,
                                                  {'group_by': ['yes_no']})],
            [False, True])


class PivotTest(DataSourceFixture, TestCase):

    def test_static_columns_with_case_when(self):
        result = query.pivot(self.source, self.request, {'pivot': {
            'rows': 'field_autocomplete', 'columns': 'radio_elements',
            'value': {'column': 'knob_number', 'fn': 'sum'}}})
        self.assertEqual(result['columns'], [1, 2, 3, 4])
        self.assertEqual(result['column_labels'], ['A', 'B', 'C', 'D'])
        rows = dict(zip(result['row_labels'], result['data']))
        self.assertEqual(rows['Costa Rica'], [10, None, 30, None])
        self.assertEqual(rows['Panama'], [None, 20, None, None])

    def test_static_boolean_count(self):
        result = query.pivot(self.source, self.request, {'pivot': {
            'rows': 'field_autocomplete', 'columns': 'yes_no'}})
        self.assertEqual(result['columns'], [True, False])
        rows = dict(zip(result['rows'], result['data']))
        self.assertEqual(rows[self.cr.pk], [2, 0])
        self.assertEqual(rows[self.pa.pk], [0, 1])

    def test_dynamic_columns_composed_in_python(self):
        result = query.pivot(self.source, self.request, {
            'filters': [{'column': 'knob_number', 'op': 'gte', 'value': 10}],
            'pivot': {'rows': 'yes_no', 'columns': 'field_autocomplete',
                      'value': {'column': 'float_number', 'fn': 'max'}}})
        self.assertEqual(result['rows'], [False, True])
        self.assertEqual(result['column_labels'], ['Costa Rica', 'Panama'])
        self.assertEqual(result['data'], [[None, 2.5], [10.0, None]])

    def test_dynamic_count_fills_zeros_and_periods(self):
        result = query.pivot(self.source, self.request, {'pivot': {
            'rows': {'column': 'born_date', 'period': 'year'},
            'columns': 'field_autocomplete', 'value': {'fn': 'count'}}})
        self.assertEqual(result['row_labels'], ['2025', '2026'])
        self.assertEqual(result['data'], [[1, 0], [1, 1]])

    def test_pivot_is_required(self):
        with self.assertRaises(ValidationError):
            query.pivot(self.source, self.request, {})

    @override_settings(GT_DATASOURCE_MAX_GROUPS=2)
    def test_too_many_rows_or_columns(self):
        for pivot, what in (({'rows': 'name', 'columns': 'yes_no'}, 'rows'),
                            ({'rows': 'name', 'columns': 'field_autocomplete'},
                             'rows'),
                            ({'rows': 'yes_no', 'columns': 'name'}, 'columns')):
            with self.subTest(pivot=pivot):
                with self.assertRaisesMessage(ValidationError,
                                              'More than 2 %s' % what):
                    query.pivot(self.source, self.request, {'pivot': pivot})
        # At the cap it is the same table as ever.
        result = query.pivot(self.source, self.request, {'pivot': {
            'rows': 'yes_no', 'columns': 'field_autocomplete'}})
        self.assertEqual(result['data'], [[0, 1], [2, 0]])


class FacetsTest(DataSourceFixture, TestCase):

    def counts(self, facet):
        return {entry['label']: entry['count'] for entry in facet}

    def test_own_filter_is_ignored_and_the_others_respected(self):
        params = {'filters': [
            {'column': 'field_autocomplete', 'op': 'in', 'value': [self.cr.pk]},
            {'column': 'yes_no', 'op': 'eq', 'value': True}]}
        result = query.facets(self.source, self.request, params,
                              ['field_autocomplete', 'yes_no', 'radio_elements'])
        # Country: its own filter is ignored, yes_no=True still applies.
        self.assertEqual(self.counts(result['field_autocomplete']),
                         {'Costa Rica': 2})
        # yes_no: ignores itself, keeps country=CR.
        self.assertEqual(self.counts(result['yes_no']), {'Yes': 2})
        # Other facets get both filters.
        self.assertEqual(self.counts(result['radio_elements']), {'A': 1, 'C': 1})

        params['filters'][1]['value'] = False
        result = query.facets(self.source, self.request, params,
                              ['field_autocomplete', 'yes_no'])
        self.assertEqual(self.counts(result['field_autocomplete']), {'Panama': 1})
        self.assertEqual(self.counts(result['yes_no']), {'Yes': 2})

    def test_search_applies_to_facets(self):
        result = query.facets(self.source, self.request, {'search': 'red'},
                              'yes_no,field_autocomplete')
        self.assertEqual(self.counts(result['yes_no']), {'Yes': 2})

    def test_m2m_facet(self):
        result = query.facets(self.source, self.request, {}, ['m2m_autocomplete'])
        self.assertEqual(self.counts(result['m2m_autocomplete']),
                         {'Panama': 2, 'Costa Rica': 1, 'Empty': 1})

    def test_numeric_buckets(self):
        result = query.facets(self.source, self.request, {}, ['knob_number'])
        facet = result['knob_number']
        self.assertEqual([e['value'] for e in facet],
                         [[10, 14], [15, 19], [20, 24], [25, 29], [30, 30]])
        self.assertEqual([e['count'] for e in facet], [1, 0, 1, 0, 1])
        self.assertTrue(all(e['op'] == 'between' for e in facet))
        facet = query.facets(self.source, self.request, {},
                             ['float_number'])['float_number']
        # Decimal ranges share their edges: 2.5 may count twice.
        self.assertGreaterEqual(sum(e['count'] for e in facet), 3)
        self.assertLessEqual(facet[0]['value'][0], 1.5)
        self.assertGreaterEqual(facet[-1]['value'][1], 10)

    def test_date_buckets(self):
        facet = query.facets(self.source, self.request, {},
                             ['born_date'])['born_date']
        self.assertEqual([(e['label'], e['count']) for e in facet],
                         [('2026-02', 1), ('2026-01', 1), ('2025-12', 1)])
        facet = query.facets(self.source, self.request, {},
                             ['last_time'])['last_time']
        self.assertEqual(facet[0]['value'], {'period': 'month',
                                             'date': '2026-02-01'})

    def test_entries_are_filters(self):
        """Selecting an entry (its op and value) returns ``count`` rows."""
        for name in ('knob_number', 'float_number', 'born_date', 'last_time',
                     'field_autocomplete', 'radio_elements', 'yes_no'):
            for entry in query.facets(self.source, self.request, {}, [name])[name]:
                value = entry['value']
                if entry['op'] == 'in':
                    value = [value]
                params = {'filters': [{'column': name, 'op': entry['op'],
                                       'value': value}]}
                with self.subTest(column=name, entry=entry['label']):
                    self.assertEqual(len(self.names(params)), entry['count'])

    def test_unknown_or_json_facet(self):
        with self.assertRaises(ValidationError):
            query.facets(self.source, self.request, {}, ['nope'])
        with self.assertRaises(ValidationError):
            query.facets(self.json_source, self.request, {}, ['options'])


def content(response):
    if response.streaming:
        return b''.join(response.streaming_content)
    return response.content


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class ExportTest(DataSourceFixture, TestCase):
    params = {'columns': ['name', 'knob_number', 'field_autocomplete',
                          'radio_elements', 'born_date'],
              'ordering': ['name'],
              'aggregates': [{'column': 'knob_number', 'fn': 'sum'},
                             {'fn': 'count'}],
              'highlights': [{'filter': {'column': 'knob_number', 'op': 'gt',
                                         'value': 15}, 'css': 'table-danger'},
                             {'filter': {'column': 'field_autocomplete',
                                         'op': 'eq', 'value': None},
                              'css': 'table-info'}]}

    def setUp(self):
        super().setUp()
        self.params = json.loads(json.dumps(self.params))
        self.params['highlights'][1]['filter']['value'] = self.pa.pk

    def test_csv(self):
        response = ds_export.export(self.source, self.request, self.params, 'csv')
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('test-objects.csv', response['Content-Disposition'])
        rows = list(csv.reader(io.StringIO(content(response).decode('utf-8-sig'))))
        self.assertEqual(rows, [
            ['Name', 'Knob number', 'Field autocomplete', 'Radio elements',
             'Born date'],
            ['Alpha', '10', 'Costa Rica', 'A', '2026-01-15'],
            ['Beta', '20', 'Panama', 'B', '2026-02-10'],
            ['Gamma', '30', 'Costa Rica', 'C', '2025-12-31']])

    def test_csv_streams_in_chunks(self):
        with mock.patch.object(ds_export, 'CHUNK_SIZE', 2):
            response = ds_export.export(self.source, self.request,
                                        {'filters': [{'column': 'yes_no',
                                                      'op': 'eq', 'value': 1}],
                                         'columns': ['name']}, 'csv')
            self.assertTrue(response.streaming)
            text = content(response).decode('utf-8-sig')
        self.assertEqual(text.split(), ['Name', 'Alpha', 'Gamma'])

    def test_json(self):
        response = ds_export.export(self.source, self.request, self.params,
                                    'json')
        body = json.loads(response.content)
        self.assertEqual(body['source'], 'test.objects')
        self.assertEqual([c['name'] for c in body['columns']],
                         self.params['columns'])
        self.assertEqual([r['name'] for r in body['data']],
                         ['Alpha', 'Beta', 'Gamma'])
        self.assertEqual(body['data'][1]['field_autocomplete'],
                         {'id': self.pa.pk, 'display_name': 'Panama'})
        self.assertEqual(body['data'][0]['born_date'], '2026-01-15')
        self.assertEqual(body['aggregates'], [
            {'column': 'knob_number', 'fn': 'sum', 'value': 60},
            {'column': '', 'fn': 'count', 'value': 3}])

    def test_csv_neutralizes_formulas(self):
        self.alpha.name = '=HYPERLINK("http://x","y")'
        self.alpha.save()
        self.beta.name = '@SUM(1)'
        self.beta.save()
        response = ds_export.export(self.source, self.request, {
            'columns': ['name', 'knob_number'], 'ordering': ['knob_number']},
            'csv')
        rows = list(csv.reader(io.StringIO(content(response).decode('utf-8-sig'))))
        self.assertEqual(rows[1:], [["'=HYPERLINK(\"http://x\",\"y\")", '10'],
                                    ["'@SUM(1)", '20'], ['Gamma', '30']])
        self.assertEqual(ds_export.neutralize_formula('-1+2'), "'-1+2")
        self.assertEqual(ds_export.neutralize_formula('+x'), "'+x")
        self.assertEqual(ds_export.neutralize_formula('plain'), 'plain')

    def test_json_is_limited(self):
        with self.settings(GT_DATASOURCE_EXPORT_MAX_ROWS=2):
            body = json.loads(ds_export.export(
                self.source, self.request, {'ordering': ['name'],
                                            'aggregates': [{'fn': 'count'}]},
                'json').content)
        self.assertEqual([r['name'] for r in body['data']], ['Alpha', 'Beta'])
        self.assertTrue(body['truncated'])
        self.assertEqual(body['limit'], 2)
        # The totals are still those of every row.
        self.assertEqual(body['aggregates'][0]['value'], 3)
        with self.settings(GT_DATASOURCE_EXPORT_MAX_ROWS=3):
            body = json.loads(ds_export.export(self.source, self.request, {},
                                               'json').content)
        self.assertFalse(body['truncated'])
        self.assertEqual(len(body['data']), 3)

    def test_highlight_color(self):
        self.assertEqual(ds_export.highlight_color('x #a1B2c3'), 'A1B2C3')
        self.assertEqual(ds_export.highlight_color('table-danger'), 'F8D7DA')
        for css in ('#zzzzzz', '#12345', '#1234567', '"><b>', None):
            with self.subTest(css=css):
                self.assertEqual(ds_export.highlight_color(css),
                                 ds_export.DEFAULT_HIGHLIGHT_COLOR)

    @skipUnless(openpyxl, 'openpyxl is not installed')
    def test_xlsx_hardening(self):
        self.alpha.name = '=1+1'
        self.alpha.save()
        params = {'columns': ['name', 'knob_number'], 'ordering': ['name'],
                  'highlights': [{'filter': {'column': 'knob_number',
                                             'op': 'gt', 'value': 0},
                                  'css': '#zzzzzz'}]}
        with self.settings(GT_DATASOURCE_EXPORT_MAX_ROWS=2):
            response = ds_export.export(self.source, self.request, params,
                                        'xlsx')
        self.assertEqual(response.status_code, 200)
        sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
        self.assertEqual(sheet['A2'].value, '=1+1')
        self.assertEqual(sheet['A2'].data_type, 's')
        self.assertEqual(sheet['A3'].value, 'Beta')
        self.assertIsNone(sheet['A4'].value)
        self.assertIn('2', sheet['A5'].value)

    @skipUnless(openpyxl, 'openpyxl is not installed')
    def test_xlsx_drops_illegal_control_characters(self):
        # PostgreSQL cannot store NUL, so \x00 is checked on _xlsx_value.
        self.alpha.name = 'Al\x01ph\x08a\x1f\tok'
        self.alpha.save()
        source = ModelDataSource(demo.ObjectManagerDemoModel,
                                 name='test.ctrl', perms=[],
                                 fields=['name', 'description'],
                                 columns=[Column('name', 'Na\x01me', 'string')])
        response = ds_export.export(source, self.request,
                                    {'ordering': ['name'],
                                     'filters': [{'column': 'name', 'op': 'eq',
                                                  'value': self.alpha.name}]},
                                    'xlsx')
        self.assertEqual(response.status_code, 200)
        sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
        self.assertEqual(sheet['A1'].value, 'Name')
        self.assertEqual(sheet['A2'].value, 'Alpha\tok')
        self.assertEqual(ds_export._xlsx_value({'a': '\x02'}), '{"a": "\\u0002"}')
        self.assertEqual(ds_export._xlsx_value('x\x00\x0by\x0cz\x0e\n'),
                         'xyz\n')

    def test_unknown_format(self):
        with self.assertRaises(ValidationError):
            ds_export.export(self.source, self.request, {}, 'docx')

    def test_registry_is_extensible(self):
        def exporter(source, request, params):
            return 'custom'
        with mock.patch.dict(ds_export.EXPORTERS, {'txt': exporter}):
            self.assertEqual(ds_export.export(self.source, self.request, {},
                                              'txt'), 'custom')

    @skipUnless(openpyxl, 'openpyxl is not installed')
    def test_xlsx(self):
        response = ds_export.export(self.source, self.request, self.params,
                                    'xlsx')
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        sheet = workbook.active
        values = [[c.value for c in row] for row in sheet.iter_rows()]
        self.assertEqual(values[0], ['Name', 'Knob number', 'Field autocomplete',
                                     'Radio elements', 'Born date'])
        self.assertEqual(values[1][:4], ['Alpha', 10, 'Costa Rica', 'A'])
        self.assertEqual(values[1][4].date(), datetime.date(2026, 1, 15))
        # Totals row: the sum under its column, the bare count under the first.
        self.assertEqual(values[4][1], 60)
        self.assertEqual(values[4][0], 'Count: 3')
        # The numeric rule is conditional formatting, the fk one static fill.
        rules = [rule for cf in sheet.conditional_formatting for rule in cf.rules]
        self.assertEqual([r.formula for r in rules], [['$B2>15']])
        self.assertEqual(sheet['A3'].fill.start_color.rgb, '00CFF4FC')
        self.assertNotEqual(sheet['A2'].fill.start_color.rgb, '00CFF4FC')

    def test_highlight_formulas(self):
        cols = self.source.column_map(self.request)
        cases = [
            ('name', 'eq', 'Al"x', '$A2="Al""x"'),
            ('name', 'icontains', 'al', 'ISNUMBER(SEARCH("al",$A2))'),
            ('name', 'startswith', 'Al', 'LEFT($A2,2)="Al"'),
            ('knob_number', 'in', [1, 2], 'OR($A2=1,$A2=2)'),
            ('knob_number', 'between', [1, 2], 'AND($A2>=1,$A2<=2)'),
            ('born_date', 'lt', '2026-01-02', '$A2<DATE(2026,1,2)'),
            ('yes_no', 'eq', True, '$A2=TRUE'),
            ('name', 'isnull', True, 'ISBLANK($A2)'),
            ('last_time', 'eq', '2026-01-01', None),
            ('radio_elements', 'eq', 1, None),
        ]
        for name, op, value, formula in cases:
            with self.subTest(name=name, op=op):
                self.assertEqual(ds_export.highlight_formula(
                    cols[name], '$A2', {'column': name, 'op': op,
                                        'value': value}), formula)

    @skipUnless(xhtml2pdf, 'xhtml2pdf is not installed')
    def test_pdf_has_several_pages(self):
        community = demo.Community.objects.first()
        demo.ObjectManagerDemoModel.objects.bulk_create([
            demo.ObjectManagerDemoModel(
                name='Row %03d' % i, float_number=i, knob_number=i,
                born_date=datetime.date(2026, 1, 1), last_time=timezone.now(),
                description='x', radio_elements=1 + i % 4, yes_no=bool(i % 2),
                field_autocomplete=self.cr, field_select=community,
                livetime_range='', simple_archive='a', chunked_archive='b',
                taging_list='') for i in range(150)])
        response = ds_export.export(self.source, self.request, self.params, 'pdf')
        self.assertEqual(response['Content-Type'], 'application/pdf')
        reader = PdfReader(io.BytesIO(response.content))
        self.assertGreater(len(reader.pages), 1)
        first = reader.pages[0].extract_text()
        second = reader.pages[1].extract_text()
        # The header repeats and the page number frame is on every page.
        self.assertIn('Knob number', second)
        self.assertIn('Page 1 of %d' % len(reader.pages), first)
        self.assertIn('Page 2 of %d' % len(reader.pages), second)
        last = reader.pages[-1].extract_text()
        self.assertIn('Sum:', last)

    @skipUnless(xhtml2pdf, 'xhtml2pdf is not installed')
    def test_pdf_empty(self):
        response = ds_export.export(self.source, self.request, {'filters': [
            {'column': 'name', 'op': 'eq', 'value': 'nobody'}]}, 'pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))


class SourcesTest(DataSourceFixture, TestCase):

    def test_site_field_limits_to_the_current_site_and_the_globals(self):
        # The "site" is any object the field points to: the Country FK
        # stands for a Site FK, which the demo models do not have.
        source = ModelDataSource(demo.Person, perms=[], site_field='country')
        demo.Person.objects.create(name='Tico', country=self.cr,
                                   born_date=datetime.date(2000, 1, 1),
                                   last_time=timezone.now())
        demo.Person.objects.create(name='Pana', country=self.pa,
                                   born_date=datetime.date(2000, 1, 1),
                                   last_time=timezone.now())
        with mock.patch.object(ds_base, 'get_current_site', return_value=self.cr):
            names = {p.name for p in source.get_queryset(self.request)}
        self.assertEqual(names, {'Tico'})
        with mock.patch.object(ds_base, 'site_q',
                               wraps=ds_base.site_q) as site_q, \
                mock.patch.object(ds_base, 'get_current_site',
                                  return_value=self.pa):
            names = {p.name for p in query.apply_params(source, self.request, {})}
        self.assertEqual(names, {'Pana'})
        site_q.assert_called_once_with(self.pa, field='country')

    def test_site_q_rule(self):
        q = ds_base.site_q(None, field='country')
        self.assertEqual(q, ds_base.Q(country__isnull=True))
        q = ds_base.site_q(self.cr, field='country')
        self.assertEqual(q, ds_base.Q(country=self.cr)
                         | ds_base.Q(country__isnull=True))

    def test_current_site_from_the_request(self):
        # The Site rule (djgentelella.sites): request.site when it is a Site row.
        site = Site.objects.create(domain='ds.example', name='ds')
        self.request.site = site
        self.assertEqual(ds_base.get_current_site(self.request), site)
        self.assertIsNone(ds_base.get_current_site(None))

    def test_permissions(self):
        source = ModelDataSource(demo.Person)
        demo.Person.objects.create(name='Tico', country=self.cr,
                                   born_date=datetime.date(2000, 1, 1),
                                   last_time=timezone.now())
        user = User.objects.create_user('noperm', password='x')
        self.request.user = user
        self.assertFalse(source.has_permission(self.request))
        self.assertEqual(source.get_queryset(self.request).count(), 0)
        user.user_permissions.add(Permission.objects.get(codename='view_person'))
        self.request.user = User.objects.get(pk=user.pk)
        self.assertTrue(source.has_permission(self.request))

    def test_function_source(self):
        def tagged(request):
            return demo.ObjectManagerDemoModel.objects.filter(yes_no=True)

        source = FunctionDataSource(tagged, [
            Column('name', 'Name', 'string'),
            Column('knob_number', 'Knob', 'integer')], name='test.tagged',
            perms=[])
        self.assertTrue(source.has_permission(self.request))
        result = query.aggregate(source, self.request, {
            'aggregates': [{'column': 'knob_number', 'fn': 'sum'}]})
        self.assertEqual(result, [{'knob_number__sum': 40}])
        self.assertEqual(self.names({'search': 'gam'}, source), {'Gamma'})
        with self.assertRaises(ValidationError):
            self.names({'filters': [{'column': 'yes_no', 'op': 'eq',
                                     'value': True}]}, source)
        locked = FunctionDataSource(tagged, source.columns, perms=['auth.nope'],
                                    model=demo.ObjectManagerDemoModel)
        self.assertEqual(locked.name, 'djgentelella.tagged')
        self.assertFalse(locked.get_queryset(self.request).exists())

    def test_function_source_does_not_run_fn_without_permission(self):
        calls = []

        def costly(request):
            calls.append(request)
            return demo.ObjectManagerDemoModel.objects.all()

        columns = [Column('name', 'Name', 'string')]
        with_model = FunctionDataSource(costly, columns, name='test.costly',
                                        perms=['auth.nope'],
                                        model=demo.ObjectManagerDemoModel)
        queryset = with_model.get_queryset(self.request)
        self.assertEqual(queryset.model, demo.ObjectManagerDemoModel)
        self.assertFalse(queryset.exists())
        without_model = FunctionDataSource(costly, columns, name='test.costly2',
                                           perms=['auth.nope'])
        with self.assertRaises(PermissionDenied):
            without_model.get_queryset(self.request)
        self.assertEqual(calls, [])
        public = FunctionDataSource(costly, columns, name='test.costly3',
                                    perms=[])
        self.assertEqual(public.get_queryset(self.request).count(), 3)
        self.assertEqual(len(calls), 1)

    def test_default_permissions(self):
        """No perms: an authenticated user. [] : anyone. A list: all of it."""
        def everything(request):
            return demo.ObjectManagerDemoModel.objects.all()

        columns = [Column('name', 'Name', 'string')]
        default = FunctionDataSource(everything, columns, name='test.default')
        public = FunctionDataSource(everything, columns, name='test.public',
                                    perms=[])
        locked = FunctionDataSource(everything, columns, name='test.locked',
                                    perms=['demoapp.view_person'])

        class ByHand(ds_base.DataSource):
            name = 'test.byhand'

        self.assertIsNone(default.perms)
        anonymous = self.request
        user = User.objects.create_user('someone', password='x')
        logged = RequestFactory().get('/')
        logged.user = user
        for source, anon, auth in ((default, False, True), (public, True, True),
                                   (locked, False, False),
                                   (ByHand(), False, True)):
            with self.subTest(source=source.name):
                self.assertEqual(source.has_permission(anonymous), anon)
                self.assertEqual(source.has_permission(logged), auth)
        with self.assertRaises(PermissionDenied):
            default.get_queryset(anonymous)
        self.assertEqual(default.get_queryset(logged).count(), 3)

    def test_function_source_with_an_annotated_column(self):
        def doubled(request):
            return demo.ObjectManagerDemoModel.objects.annotate(
                double=F('knob_number') * 2)

        source = FunctionDataSource(doubled, [
            Column('name', 'Name', 'string'),
            Column('double', 'Double', 'integer')], name='test.doubled',
            perms=[])
        params = {'filters': [{'column': 'double', 'op': 'gte', 'value': 40}],
                  'ordering': ['-double']}
        queryset = query.apply_params(source, self.request, params)
        rows = query.serialize_rows(source, self.request, queryset,
                                    source.columns(self.request))
        self.assertEqual([(r['name'], r['double']) for r in rows],
                         [('Gamma', 60), ('Beta', 40)])
        css = query.highlight_classes(
            source, self.request, queryset, [r['pk'] for r in rows],
            [{'filter': {'column': 'double', 'op': 'gt', 'value': 50},
              'css': 'hot'}])
        self.assertEqual(css, {self.gamma.pk: 'hot'})
        facet = query.facets(source, self.request, {}, ['double'])['double']
        self.assertEqual(sum(e['count'] for e in facet), 3)
        self.assertEqual(query.aggregate(source, self.request, {
            'aggregates': [{'column': 'double', 'fn': 'max'}]}),
            [{'double__max': 60}])

    def test_registry(self):
        register_datasource(self.source)
        try:
            self.assertIs(get_datasource('test.objects'), self.source)
        finally:
            unregister_datasource('test.objects')
        with self.assertRaises(KeyError):
            get_datasource('test.objects')
        # The demo's gtdatasources.py was autodiscovered.
        self.assertEqual(get_datasource('demoapp.person').model, demo.Person)
        self.assertIn('requester__username',
                      get_datasource('demoapp.purchases').column_map(None))

    def test_app_is_installed_with_its_label(self):
        self.assertEqual(apps.get_app_config('gtdatasources').name,
                         'djgentelella.datasources')


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class DataSourceAPITest(DataSourceFixture, TestCase):

    def setUp(self):
        super().setUp()
        register_datasource(self.source)
        self.addCleanup(unregister_datasource, 'test.objects')
        self.user = User.objects.create_user('viewer', password='x')

    def url(self, endpoint='rows', name='test.objects'):
        if endpoint is None:
            return reverse('gtdatasource', args=[name])
        return reverse('gtdatasource-' + endpoint, args=[name])

    def test_urls(self):
        self.assertEqual(self.url(), '/gtapis/datasources/test.objects/rows')
        self.assertEqual(self.url(None), '/gtapis/datasources/test.objects/')

    def test_info(self):
        body = self.client.get(self.url(None)).json()
        self.assertEqual(body['name'], 'test.objects')
        self.assertEqual(body['formats'], ['csv', 'json', 'pdf', 'xlsx'])
        self.assertEqual(body['columns'][7]['choices'][0], [1, 'A'])

    def test_rows_in_datatables_format(self):
        params = {'filters': [{'column': 'yes_no', 'op': 'eq', 'value': True}],
                  'columns': ['name', 'knob_number'],
                  'highlights': [{'filter': {'column': 'knob_number', 'op': 'gt',
                                             'value': 15}, 'css': 'table-danger'}]}
        response = self.client.get(self.url(), {
            'params': json.dumps(params), 'draw': 3, 'offset': 1, 'limit': 1,
            'ordering': 'name'})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['draw'], 3)
        self.assertEqual(body['recordsTotal'], 3)
        self.assertEqual(body['recordsFiltered'], 2)
        self.assertEqual(body['data'], [{'pk': self.gamma.pk, 'name': 'Gamma',
                                         'knob_number': 30,
                                         'DT_RowClass': 'table-danger'}])

    def test_rows_by_post_and_datatables_search(self):
        response = self.client.post(
            self.url() + '?search=pear',
            data=json.dumps({'params': {'ordering': ['-name']}}),
            content_type='application/json')
        self.assertEqual([r['name'] for r in response.json()['data']], ['Beta'])
        response = self.client.post(
            self.url(), data=json.dumps({'ordering': ['-name'], 'limit': 2}),
            content_type='application/json')
        self.assertEqual([r['name'] for r in response.json()['data']],
                         ['Gamma', 'Beta'])

    @override_settings(GT_DATASOURCE_MAX_GROUPS=2)
    def test_too_many_groups_is_a_400(self):
        params = json.dumps({'group_by': ['name']})
        response = self.client.get(self.url('aggregate'), {'params': params})
        self.assertEqual(response.status_code, 400)
        self.assertIn('More than 2 groups', response.json()['detail'][0])
        params = json.dumps({'pivot': {'rows': 'name', 'columns': 'yes_no'}})
        response = self.client.get(self.url('pivot'), {'params': params})
        self.assertEqual(response.status_code, 400)

    def test_aggregate_pivot_facets(self):
        params = json.dumps({'group_by': ['yes_no'],
                             'aggregates': [{'column': 'knob_number',
                                             'fn': 'sum'}]})
        body = self.client.get(self.url('aggregate'), {'params': params}).json()
        self.assertEqual(body, [{'yes_no': False, 'knob_number__sum': 20},
                                {'yes_no': True, 'knob_number__sum': 40}])
        params = json.dumps({'pivot': {'rows': 'yes_no',
                                       'columns': 'radio_elements'}})
        body = self.client.get(self.url('pivot'), {'params': params}).json()
        self.assertEqual(body['data'], [[0, 1, 0, 0], [1, 0, 1, 0]])
        body = self.client.get(self.url('facets'), {
            'columns': 'yes_no,field_autocomplete'}).json()
        self.assertEqual(set(body), {'yes_no', 'field_autocomplete'})

    def test_export(self):
        response = self.client.get(self.url('export'), {
            'fmt': 'json', 'params': json.dumps({'columns': ['name']})})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)['data']), 3)
        response = self.client.get(self.url('export'), {'fmt': 'csv'})
        self.assertTrue(content(response).decode('utf-8-sig').startswith('ID,'))

    def test_bad_requests(self):
        cases = [
            (self.url(), {'params': '{bad'}),
            (self.url(), {'params': json.dumps({'filters': [
                {'column': 'nope', 'op': 'eq', 'value': 1}]})}),
            (self.url('facets'), {}),
            (self.url('pivot'), {}),
            (self.url('export'), {'fmt': 'docx'}),
        ]
        for url, data in cases:
            with self.subTest(url=url, data=data):
                response = self.client.get(url, data)
                self.assertEqual(response.status_code, 400)
                self.assertIn('detail', response.json())

    def test_post_body_that_is_not_an_object_is_400(self):
        for endpoint in ('facets', 'export', 'rows'):
            for body in ([1, 2], 'text', 3):
                with self.subTest(endpoint=endpoint, body=body):
                    response = self.client.post(
                        self.url(endpoint), data=json.dumps(body),
                        content_type='application/json')
                    self.assertEqual(response.status_code, 400)
        response = self.client.post(
            self.url('export'), data=json.dumps({'fmt': ['csv']}),
            content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_bad_fk_value_is_400(self):
        for op, value in (('eq', 'abc'), ('in', ['abc']), ('ne', 'x')):
            with self.subTest(op=op):
                response = self.client.get(self.url(), {'params': json.dumps({
                    'filters': [{'column': 'field_autocomplete', 'op': op,
                                 'value': value}]})})
                self.assertEqual(response.status_code, 400)
        response = self.client.get(self.url(), {'params': json.dumps({
            'filters': [{'column': 'born_date', 'op': 'date_period',
                         'value': {'period': 'year', 'offset': 100000}}]})})
        self.assertEqual(response.status_code, 400)

    def test_function_source_needs_a_login_by_default(self):
        def everything(request):
            return demo.ObjectManagerDemoModel.objects.all()

        register_datasource(FunctionDataSource(
            everything, [Column('name', 'Name', 'string')], name='test.fn'))
        self.addCleanup(unregister_datasource, 'test.fn')
        self.assertEqual(self.client.get(self.url('rows', 'test.fn'))
                         .status_code, 403)
        self.client.force_login(self.user)
        response = self.client.get(self.url('rows', 'test.fn'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['recordsTotal'], 3)

    def test_unknown_source_is_404(self):
        self.assertEqual(self.client.get(self.url('rows', 'nope.nope'))
                         .status_code, 404)

    def test_permission_denied_is_403(self):
        """demoapp.person needs demoapp.view_person on every endpoint."""
        endpoints = [(None, {}), ('rows', {}), ('aggregate', {}),
                     ('pivot', {'params': json.dumps({'pivot': {
                         'rows': 'country', 'columns': 'num_children'}})}),
                     ('facets', {'columns': 'country'}),
                     ('export', {'fmt': 'csv'})]
        for endpoint, data in endpoints:
            with self.subTest(endpoint=endpoint, user='anonymous'):
                self.assertEqual(self.client.get(
                    self.url(endpoint, 'demoapp.person'), data).status_code, 403)
        self.client.force_login(self.user)
        for endpoint, data in endpoints:
            with self.subTest(endpoint=endpoint, user='no permission'):
                self.assertEqual(self.client.get(
                    self.url(endpoint, 'demoapp.person'), data).status_code, 403)
        self.user.user_permissions.add(
            Permission.objects.get(codename='view_person'))
        for endpoint, data in endpoints:
            with self.subTest(endpoint=endpoint, user='view_person'):
                self.assertEqual(self.client.get(
                    self.url(endpoint, 'demoapp.person'), data).status_code, 200)


@tag('postgresql')
@skipUnless(connection.vendor == 'postgresql'
            and apps.is_installed('django.contrib.postgres'),
            'full-text search needs PostgreSQL and django.contrib.postgres')
class PostgresFullTextSearchTest(DataSourceFixture, TestCase):

    def test_search_uses_full_text(self):
        self.source.search_config = 'english'
        self.assertTrue(query.use_fulltext(self.source,
                                           demo.ObjectManagerDemoModel.objects))
        # Stemming: "apples" finds "red apple", which icontains would not.
        self.assertEqual(self.names({'search': 'apples'}), {'Alpha'})
        self.assertEqual(self.names({'search': 'red -cherry'}), {'Alpha'})
        self.assertEqual(self.names({'search': 'pear or cherry'}),
                         {'Beta', 'Gamma'})
        # Plain words are prefixes, as in a search box being typed into.
        self.assertEqual(self.names({'search': 'gam'}), {'Gamma'})
        self.assertEqual(self.names({'search': 're app'}), {'Alpha'})
        # Operator characters never reach the raw tsquery.
        self.assertEqual(self.names({'search': 'zz_qq:*&|!('}), set())
        self.source.search_mode = 'icontains'
        self.assertEqual(self.names({'search': 'apples'}), set())

    def test_search_with_aggregates_and_facets(self):
        self.source.search_config = 'english'
        result = query.aggregate(self.source, self.request, {
            'search': 'red', 'group_by': ['yes_no'],
            'aggregates': [{'column': 'knob_number', 'fn': 'sum'}]})
        self.assertEqual(result, [{'yes_no': True, 'knob_number__sum': 40}])
        facet = query.facets(self.source, self.request, {'search': 'red'},
                             ['field_autocomplete'])['field_autocomplete']
        self.assertEqual([(e['label'], e['count']) for e in facet],
                         [('Costa Rica', 2)])


class FulltextFallbackTest(DataSourceFixture, TestCase):

    def test_sqlite_falls_back_to_icontains(self):
        if connection.vendor == 'postgresql':
            self.skipTest('this database does full-text search')
        self.assertFalse(query.use_fulltext(self.source,
                                            demo.ObjectManagerDemoModel.objects))
        self.source.search_mode = 'fulltext'
        with self.assertRaises(ValidationError):
            self.names({'search': 'red'})
