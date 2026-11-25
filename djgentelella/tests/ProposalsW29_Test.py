"""W29: widget options in the designs and in ``widgetmap``; the proposals of
the consumers of wave 10 over the data sources.

* ``widgetmap.WIDGET_OPTIONS``/``widget_options``/``build_widget`` and the
  ``widget_options`` of a design form (and of an ``interactive_grid``);
* ``DataSourceUnavailable`` is checked before ``ValidationError``: a class
  that inherits from both is a 503 in every endpoint;
* the read-only grid over a data source follows a facets panel
  (``gtfilters``);
* ``order_by_value`` in the parameter document; ``max``/``min`` of dates.
"""

import datetime
import inspect
import json

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from demoapp import models as demo
from djgentelella.datasources import query
from djgentelella.datasources.base import (
    DataSourceUnavailable, ModelDataSource, api_error, register_datasource,
    unregister_datasource,
)
from djgentelella.designs import engine, jsonschema, publishing
from djgentelella.designs.exposure import expose
from djgentelella.designs.grid import grid_page_context
from djgentelella.forms import widgetmap
from djgentelella.tests.Designs_Test import design, node
from djgentelella.tests.SourceReadOnly_Test import (
    REMOTE, ReadOnlyBase, RemoteSource, grid, listing,
)
from djgentelella.widgets import extras, geocoding, imagecrop, markdown

__all__ = ['W29WidgetOptionsTableTests', 'W29DesignWidgetOptionsTests',
           'W29TransitionErrorTests', 'W29GridFacetsTests', 'W29AggregateTests',
           'W29SchemaKeywordTests']


# -- widget options in widgetmap -------------------------------------------------------

class W29WidgetOptionsTableTests(SimpleTestCase):

    def setUp(self):
        translation.activate('en')
        self.addCleanup(translation.deactivate)

    def test_every_option_is_an_argument_of_its_widget(self):
        for key, options in widgetmap.WIDGET_OPTIONS.items():
            self.assertIn(key, widgetmap.WIDGETS)
            parameters = inspect.signature(widgetmap.widget_class(key)).parameters
            for name in options:
                self.assertIn(name, parameters, '%s.%s' % (key, name))
                self.assertNotIn(name, ('attrs', 'extraskwargs'))

    def test_the_widgets_asked_for_have_options(self):
        expected = {
            'StarRatingInput': {'stars', 'readonly'},
            'RangeInput': {'min_value', 'max_value', 'step', 'suffix'},
            'ComboboxInput': {'choices'},
            'QRCodeInput': {'scan'},
            'ImageCropInput': {'aspect_ratio', 'max_width', 'max_height'},
            'GeocodedAddressInput': {'point_field', 'replace_text'},
            'MarkdownInput': {'rows'},
        }
        for key, names in expected.items():
            self.assertLessEqual(names, set(widgetmap.WIDGET_OPTIONS[key]), key)

    def test_widget_options_is_a_closed_object_schema(self):
        schema = widgetmap.widget_options('StarRatingInput')
        self.assertEqual(schema['type'], 'object')
        self.assertIs(schema['additionalProperties'], False)
        self.assertEqual(set(schema['properties']), {'stars', 'readonly'})
        self.assertEqual(widgetmap.widget_options('TextInput')['properties'], {})

    def test_build_widget_with_each_widget(self):
        stars = widgetmap.build_widget('StarRatingInput', {'stars': 10,
                                                           'readonly': True})
        self.assertIsInstance(stars, extras.StarRatingInput)
        self.assertEqual((stars.stars, stars.readonly), (10, True))
        ranged = widgetmap.build_widget('RangeInput', {
            'min_value': 0, 'max_value': 10, 'step': 0.5, 'suffix': '%',
            'show_value': False})
        self.assertEqual(ranged.fixed, {'min': 0, 'max': 10, 'step': 0.5})
        self.assertEqual((ranged.suffix, ranged.show_value), ('%', False))
        combo = widgetmap.build_widget('ComboboxInput', {
            'choices': ['red', ['bl', 'Blue']]})
        self.assertEqual(list(combo.choices), [('red', 'red'), ('bl', 'Blue')])
        qr = widgetmap.build_widget('QRCodeInput', {'scan': True, 'size': 200})
        self.assertTrue(qr.scan)
        self.assertEqual(qr.attrs['data-size'], 200)
        crop = widgetmap.build_widget('ImageCropInput', {
            'aspect_ratio': 1.5, 'max_width': 800, 'max_height': 600,
            'output_type': 'image/png', 'quality': 0.8})
        self.assertIsInstance(crop, imagecrop.ImageCropInput)
        self.assertEqual(crop.attrs['data-aspect-ratio'], 1.5)
        self.assertEqual(crop.attrs['data-max-width'], 800)
        self.assertEqual(crop.attrs['data-output-type'], 'image/png')
        address = widgetmap.build_widget('GeocodedAddressInput', {
            'point_field': 'location', 'replace_text': True})
        self.assertIsInstance(address, geocoding.GeocodedAddressInput)
        self.assertEqual(address.attrs['data-point-field'], 'location')
        self.assertEqual(address.attrs['data-replace-text'], 'true')
        text = widgetmap.build_widget('MarkdownInput', {'rows': 20})
        self.assertIsInstance(text, markdown.MarkdownInput)
        self.assertEqual(text.attrs['rows'], '20')
        switch = widgetmap.build_widget('SwitchInput', {'label': 'On'})
        self.assertEqual(switch.label, 'On')
        # Without options: the widget as the table builds it.
        self.assertEqual(widgetmap.build_widget('StarRatingInput').stars, 5)

    def test_invalid_options_are_rejected(self):
        def errors(key, options):
            return [(error.path, error.message)
                    for error in widgetmap.validate_widget_options(key, options)]

        self.assertEqual(errors('StarRatingInput', {'stars': 11}),
                         [('$.stars', 'greater than 10')])
        self.assertEqual(errors('StarRatingInput', {'stars': '5'}),
                         [('$.stars', 'expected integer, got str')])
        self.assertEqual(errors('StarRatingInput', {'attrs': {'onclick': 'x'}}),
                         [('$.attrs', 'unexpected property')])
        self.assertEqual(errors('RangeInput', {'step': 0}),
                         [('$.step', 'not greater than 0')])
        self.assertEqual(errors('RangeInput', {'min_value': 5, 'max_value': 5}),
                         [('$.max_value',
                           'the maximum must be greater than the minimum')])
        self.assertEqual(errors('RangeInput', {'max_value': float('inf')}),
                         [('$.max_value', 'not a finite number')])
        self.assertEqual(errors('ComboboxInput', {'choices': ['a', ['b']]}),
                         [('$.choices[1]', 'fewer than 2 items')])
        self.assertEqual(errors('ComboboxInput', {'choices': ['a', ['a', 'A']]}),
                         [('$.choices', 'a value is listed twice')])
        self.assertEqual(errors('ComboboxInput', {'choices': ['x' * 256]}),
                         [('$.choices[0]', 'longer than 255')])
        self.assertEqual(errors('ImageCropInput', {'output_type': 'image/gif'}),
                         [('$.output_type', "'image/gif' is not one of "
                                            "'image/jpeg', 'image/png', 'image/webp'")])
        self.assertEqual(errors('GeocodedAddressInput', {'point_field': 'a b'}),
                         [('$.point_field', "'a b' does not match "
                                            "^[A-Za-z_][A-Za-z0-9_]*$")])
        self.assertEqual(errors('TextInput', {'size': 3}),
                         [('$', 'TextInput takes no options')])
        self.assertEqual(errors('Nope', {}), [('$', "'Nope' is not a widget")])
        self.assertEqual(errors('StarRatingInput', []),
                         [('$', 'expected object, got list')])
        with self.assertRaisesMessage(ValueError, '$.stars: greater than 10'):
            widgetmap.build_widget('StarRatingInput', {'stars': 11})


# -- widget options in a design -----------------------------------------------------

SHOWCASE = 'demoapp.WidgetShowcase'


def showcase_design(form, **props):
    return design(node('object_management', 'items', {
        'model': SHOWCASE, 'form': 'showcase', **props}),
        forms={'showcase': {'model': SHOWCASE, **form}})


@override_settings(LANGUAGE_CODE='en')
class W29DesignWidgetOptionsTests(ReadOnlyBase):

    def setUp(self):
        super().setUp()
        expose(demo.WidgetShowcase)

    def resolve(self, form, **props):
        resolved, errors = engine.resolve(showcase_design(form, **props))
        return resolved, [(error.path, error.message) for error in errors]

    def form_class(self, form):
        resolved, errors = self.resolve(form)
        self.assertEqual(errors, [])
        return resolved.nodes['items'].build.form.form_class

    def test_each_widget_from_widget_options(self):
        form_class = self.form_class({
            'fields': ['name', 'rating', 'volume', 'category', 'code',
                       'description', 'photo', 'address', 'location'],
            'widgets': {'rating': 'StarRatingInput', 'volume': 'RangeInput',
                        'category': 'ComboboxInput', 'code': 'QRCodeInput',
                        'description': 'MarkdownInput', 'photo': 'ImageCropInput',
                        'address': 'GeocodedAddressInput'},
            'widget_options': {
                'rating': {'stars': 10},
                'volume': {'min_value': 0, 'max_value': 11, 'step': 1,
                           'suffix': 'dB'},
                'category': {'choices': ['Books', ['mus', 'Music']]},
                'code': {'scan': True},
                'description': {'rows': 15},
                'photo': {'aspect_ratio': 1, 'max_width': 400, 'max_height': 400},
                'address': {'point_field': 'location', 'replace_text': True},
            }})
        form = form_class()
        widgets = {name: field.widget for name, field in form.fields.items()}
        self.assertEqual(widgets['rating'].stars, 10)
        self.assertEqual(widgets['volume'].fixed, {'min': 0, 'max': 11, 'step': 1})
        self.assertEqual(widgets['volume'].suffix, 'dB')
        self.assertIn(('mus', 'Music'), list(widgets['category'].choices))
        self.assertTrue(widgets['code'].scan)
        self.assertEqual(widgets['description'].attrs['rows'], '15')
        self.assertEqual(widgets['photo'].attrs['data-aspect-ratio'], 1.0)
        self.assertEqual(widgets['address'].attrs['data-point-field'], 'location')
        html = str(form['rating'])
        self.assertEqual(html.count('data-value='), 10, html)

    def test_options_of_a_default_widget(self):
        # MarkdownInput is not the default of a TextField: the options are for
        # the widget the field gets, the default one included.
        form_class = self.form_class({'fields': ['name', 'description'],
                                      'widgets': {'description': 'MarkdownInput'},
                                      'widget_options': {
                                          'description': {'rows': 4}}})
        self.assertEqual(form_class().fields['description'].widget.attrs['rows'], '4')
        _resolved, errors = self.resolve({'fields': ['name', 'description'],
                                          'widget_options': {
                                              'description': {'rows': 4}}})
        self.assertEqual(errors, [('$.forms.showcase.widget_options.description',
                                   'Textarea takes no options')])

    def test_an_invalid_option_is_an_error_of_the_design(self):
        cases = [
            ({'rating': {'stars': 0}}, {'rating': 'StarRatingInput'},
             '$.forms.showcase.widget_options.rating.stars', 'less than 1'),
            ({'rating': {'max': 3}}, {'rating': 'StarRatingInput'},
             '$.forms.showcase.widget_options.rating.max', 'unexpected property'),
            ({'volume': {'step': 0.5}}, {'volume': 'RangeInput'},
             '$.forms.showcase.widget_options.volume.step',
             'volume is an integer field: use a whole number'),
            ({'address': {'point_field': 'name'}},
             {'address': 'GeocodedAddressInput'},
             '$.forms.showcase.widget_options.address.point_field',
             "'name' is not a point field of this form"),
            ({'category': {'choices': ['x' * 61]}}, {'category': 'ComboboxInput'},
             '$.forms.showcase.widget_options.category.choices',
             'is longer than the 60 characters of category'),
            ({'nope': {}}, {}, '$.forms.showcase.widget_options',
             "'nope' is not a field of this form"),
            ({'rating': 3}, {'rating': 'StarRatingInput'},
             '$.forms.showcase.widget_options.rating', 'expected object'),
        ]
        for options, widgets, path, text in cases:
            _resolved, errors = self.resolve({
                'fields': ['name', 'rating', 'volume', 'category', 'address',
                           'location'],
                'widgets': widgets, 'widget_options': options})
            self.assertTrue(any(where == path and text in message
                                for where, message in errors), (options, errors))

    def test_the_document_schema_takes_widget_options(self):
        document = showcase_design({'fields': ['name'],
                                    'widget_options': {'name': []}})
        _resolved, errors = engine.resolve(document)
        self.assertIn('$.forms.showcase.widget_options.name',
                      [error.path for error in errors])

    def test_an_interactive_grid_passes_them_to_its_form(self):
        expose(demo.WidgetShowcase)
        resolved, errors = engine.resolve(design(node('interactive_grid', 'g', {
            'model': SHOWCASE, 'columns': ['name', 'rating'],
            'editable': ['name', 'rating'],
            'widgets': {'rating': 'StarRatingInput'},
            'widget_options': {'rating': {'stars': 3}}})))
        self.assertEqual(errors, [])
        form = resolved.nodes['g'].build.form.form_class()
        self.assertEqual(form.fields['rating'].widget.stars, 3)
        errors = self.errors(node('interactive_grid', 'g', {
            'model': SHOWCASE, 'columns': ['name', 'rating'], 'editable': ['name'],
            'widget_options': {'rating': {'stars': 3}}}))
        self.assertIn(('$.root.children[0].children[0].children[0].props'
                       '.widget_options', "'rating' is not an editable column"),
                      errors)
        self.assertError(grid(widget_options={'name': {}}),
                         "it has no 'widget_options'")

    def test_the_page_renders_the_configured_widget(self):
        self.user = User.objects.create_superuser('root', password='pw')
        self.client.force_login(self.user)
        page, errors = publishing.publish(showcase_design({
            'fields': ['name', 'rating'], 'widgets': {'rating': 'StarRatingInput'},
            'widget_options': {'rating': {'stars': 7}}}), path='w29')
        self.assertEqual(errors, [])
        content = self.client.get('/designs/w29').content.decode()
        self.assertIn('data-stars="7"', content)


# -- DataSourceUnavailable before ValidationError --------------------------------------

class TransitionError(DataSourceUnavailable, ValidationError):
    """An error of a source in transition: a ``ValidationError`` for the
    callers that still catch it, and a ``DataSourceUnavailable``."""

    def __init__(self, message):
        DataSourceUnavailable.__init__(self, message)
        ValidationError.__init__(self, message)


class W29DownSource(RemoteSource):
    def get_queryset(self, request, params=None):
        raise TransitionError('The provider API is down.')


@override_settings(LANGUAGE_CODE='en')
class W29TransitionErrorTests(ReadOnlyBase):

    def setUp(self):
        super().setUp()
        unregister_datasource(REMOTE)
        register_datasource(W29DownSource())

    def test_api_error(self):
        error = TransitionError('down')
        self.assertIs(api_error(error), error)
        plain = api_error(ValidationError('bad'), 'gtfilters')
        self.assertEqual(plain.detail, {'gtfilters': ['bad']})

    def test_the_data_source_api_answers_503(self):
        for endpoint in ('rows', 'aggregate', 'facets', 'export'):
            response = self.client.get(reverse('gtdatasource-' + endpoint,
                                               args=[REMOTE]),
                                       {'columns': 'code', 'fmt': 'json'})
            self.assertEqual(response.status_code, 503, endpoint)
            self.assertEqual(response.json()['detail'], 'The provider API is down.')
        response = self.client.get(reverse('gtdatasource-rows', args=[REMOTE]),
                                   {'params': '{'})
        self.assertEqual(response.status_code, 400)

    def test_the_component_endpoints_answer_503(self):
        page = self.publish(
            listing(), grid(),
            node('cards', 'cards', {'datasource': REMOTE, 'title_field': 'name'}),
            node('chart', 'chart', {'datasource': REMOTE, 'group_by': 'code',
                                    'perms': ['demoapp.view_country']}),
            node('stat', 'stat', {'datasource': REMOTE, 'aggregate': 'count',
                                  'perms': ['demoapp.view_country']}))
        self.client.force_login(User.objects.create_superuser('root', password='pw'))
        for node_id in ('list', 'grid', 'cards', 'chart', 'stat'):
            response = self.get(page, node_id)
            self.assertEqual(response.status_code, 503, node_id)

    def test_validate_params_does_not_swallow_it(self):
        with self.assertRaises(DataSourceUnavailable):
            query.validate_params(W29DownSource(), self.request, {})


# -- the read-only grid with facets ----------------------------------------------------

@override_settings(LANGUAGE_CODE='en')
class W29GridFacetsTests(ReadOnlyBase):

    def facets(self, target='grid'):
        return node('facets', 'filters', {'target': target, 'columns': ['code']})

    def test_a_facets_panel_filters_a_read_only_grid(self):
        resolved, errors = engine.resolve(design(grid(), self.facets()))
        self.assertEqual(errors, [])
        self.assertEqual(resolved.nodes['filters'].build.datasource, REMOTE)

    def test_not_a_grid_that_edits(self):
        expose(demo.Country)
        local = 'tests.w29.local'
        register_datasource(ModelDataSource(demo.Country, name=local, perms=[]))
        self.addCleanup(unregister_datasource, local)
        errors = self.errors(grid(datasource=local), self.facets())
        self.assertTrue(any('edits rows' in message for _where, message in errors),
                        errors)
        # A grid over a model may be filtered since W31 (the panel counts
        # through its own endpoint): only one over a data source that edits
        # rows is refused.
        errors = self.errors(node('interactive_grid', 'grid', {
            'model': 'demoapp.Country', 'columns': ['name']}), self.facets())
        self.assertFalse(any('edits rows' in message for _where, message in errors),
                         errors)

    def test_the_endpoint_reads_gtfilters(self):
        page = self.publish(grid(), self.facets())
        filters = [{'column': 'code', 'op': 'in', 'value': ['pa', 'ni']}]
        body = self.get(page, 'grid', gtfilters=json.dumps(filters)).json()
        self.assertEqual(body['count'], 2)
        self.assertEqual(sorted(row['name'] for row in body['data']),
                         ['Nicaragua', 'Panama'])
        self.assertEqual(self.get(page, 'grid', gtfilters='{').status_code, 400)
        self.assertEqual(self.get(page, 'grid', gtfilters='{"a": 1}').status_code, 400)
        hidden = [{'column': 'id', 'op': 'eq', 'value': self.pa.pk}]
        self.assertEqual(self.get(page, 'grid',
                                  gtfilters=json.dumps(hidden)).status_code, 400)

    def test_the_page_names_the_state_of_the_panel(self):
        self.publish(grid(), self.facets())
        content = self.client.get('/designs/w23').content.decode()
        url = reverse('gtdatasource', kwargs={'name': REMOTE})
        self.assertIn('"datasource_url": "%s"' % url, content)
        self.assertIn('"group": "gtdesign:grid"', content)
        # The panel writes to that same state.
        self.assertIn('data-group="gtdesign:grid"', content)

    def test_grid_page_context_takes_the_datasource_url(self):
        resolved, _errors = engine.resolve(design(grid()))
        build = resolved.nodes['grid'].build
        request = RequestFactory().get('/')
        request.user = User.objects.create_superuser('root2', password='pw')
        context = grid_page_context(build, request, '/rows/',
                                    datasource_url='/api/countries/')
        self.assertIn('"datasource_url": "/api/countries/"', context['config'])


# -- aggregates ------------------------------------------------------------------------

@override_settings(LANGUAGE_CODE='en')
class W29AggregateTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        now = timezone.now().replace(microsecond=0)
        cls.last = {'talk': now - datetime.timedelta(days=1),
                    'workshop': now, 'social': now - datetime.timedelta(days=9)}
        for kind, count in (('talk', 1), ('workshop', 2), ('social', 3)):
            for index in range(count):
                demo.Meetup.objects.create(
                    title='%s %d' % (kind, index), kind=kind,
                    starts_at=cls.last[kind] - datetime.timedelta(days=index))

    def setUp(self):
        self.source = ModelDataSource(demo.Meetup, name='tests.w29.meetups',
                                      perms=[])
        self.request = RequestFactory().get('/')
        self.request.user = User(is_superuser=True, is_active=True)

    def aggregate(self, params, **kwargs):
        return query.aggregate(self.source, self.request, params, **kwargs)

    def test_order_by_value_in_the_document(self):
        params = {'group_by': ['kind'], 'aggregates': [{'fn': 'count'}]}
        self.assertEqual([row['kind'] for row in self.aggregate(params)],
                         ['social', 'talk', 'workshop'])
        ordered = dict(params, order_by_value=True)
        self.assertEqual([(row['kind'], row['count'])
                          for row in self.aggregate(ordered)],
                         [('social', 3), ('workshop', 2), ('talk', 1)])
        # The keyword wins over the document.
        self.assertEqual([row['kind'] for row in self.aggregate(
            ordered, order_by_value=False)], ['social', 'talk', 'workshop'])

    def test_order_by_value_is_a_boolean_kept_only_when_given(self):
        self.assertNotIn('order_by_value', query.parse_params({}))
        self.assertIs(query.parse_params({'order_by_value': False})['order_by_value'],
                      False)
        with self.assertRaises(ValidationError):
            query.parse_params({'order_by_value': 'yes'})
        clean, errors = query.validate_params(
            self.source, self.request, {'order_by_value': True}, strict=True)
        self.assertEqual(errors, [])
        self.assertTrue(clean['order_by_value'])

    def test_max_and_min_of_a_datetime(self):
        rows = self.aggregate({'group_by': ['kind'], 'order_by_value': True,
                               'aggregates': [{'column': 'starts_at', 'fn': 'max'},
                                              {'column': 'starts_at', 'fn': 'min'}]})
        self.assertEqual([(row['kind'], row['starts_at__max']) for row in rows],
                         [('workshop', self.last['workshop']),
                          ('talk', self.last['talk']),
                          ('social', self.last['social'])])
        self.assertEqual(rows[-1]['starts_at__min'],
                         self.last['social'] - datetime.timedelta(days=2))

    def test_max_of_a_date_through_the_api(self):
        source = ModelDataSource(demo.ObjectManagerDemoModel,
                                 name='tests.w29.dates', perms=[])
        register_datasource(source)
        self.addCleanup(unregister_datasource, source.name)
        columns = {column.name: column for column in source.columns(self.request)}
        dates = [name for name, column in columns.items() if column.kind == 'date']
        self.assertTrue(dates)
        params = {'aggregates': [{'column': dates[0], 'fn': 'max'},
                                 {'column': dates[0], 'fn': 'min'}]}
        self.assertEqual(query.validate_params(source, self.request, params)[1], [])
        user = User.objects.create_superuser('dates', password='pw')
        self.client.force_login(user)
        response = self.client.get(reverse('gtdatasource-aggregate',
                                           args=[source.name]),
                                   {'params': json.dumps(params)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()[0]),
                         {dates[0] + '__max', dates[0] + '__min'})

    def test_sum_of_a_date_is_still_refused(self):
        with self.assertRaises(ValidationError):
            self.aggregate({'aggregates': [{'column': 'starts_at', 'fn': 'sum'}]})


# -- the JSON schema keywords --------------------------------------------------------

@override_settings(LANGUAGE_CODE='en')
class W29SchemaKeywordTests(SimpleTestCase):

    def setUp(self):
        translation.activate('en')
        self.addCleanup(translation.deactivate)

    def test_max_length_max_items_and_exclusive_minimum(self):
        def messages(value, schema):
            return [error.message for error in jsonschema.validate(value, schema)]

        self.assertEqual(messages('abc', {'maxLength': 2}), ['longer than 2'])
        self.assertEqual(messages([1, 2, 3], {'maxItems': 2}), ['more than 2 items'])
        self.assertEqual(messages(0, {'exclusiveMinimum': 0}), ['not greater than 0'])
        self.assertEqual(messages(0.1, {'exclusiveMinimum': 0}), [])
        self.assertEqual(messages('ab', {'maxLength': 2}), [])
