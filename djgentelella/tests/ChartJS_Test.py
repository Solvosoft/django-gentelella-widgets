"""The shape of what ``djgentelella.chartjs`` puts on the wire.

The javascript hands this JSON to ``new Chart()`` untouched, so a wrong key is
not a validation error anywhere -- it is a chart that quietly draws nothing.
These tests pin the Chart.js 4 vocabulary and the three translations kept for
configurations written against Chart.js 2.
"""

from django.test import TestCase

from djgentelella.chartjs import (
    BaseChartGetter,
    DoughnutChart,
    HorizontalBarChart,
    LineChart,
    StackedBarChart,
    VerticalBarChart,
    elements_to_v4,
    scales_to_v4,
)


class DemoData:
    """Enough data for the serializers to accept a chart."""

    def get_labels(self):
        return ['one', 'two']

    def get_datasets(self):
        return [{'label': 'series', 'data': [1, 2]}]


class VerticalBar(DemoData, VerticalBarChart):
    def get_title(self):
        return {'display': True, 'text': 'a title'}


class HorizontalBar(DemoData, HorizontalBarChart):
    pass


class Stacked(DemoData, StackedBarChart):
    pass


class Doughnut(DemoData, DoughnutChart):
    def get_datasets(self):
        # A circular chart colours each slice, so its serializer wants a list.
        return [{'label': 'series', 'data': [1, 2],
                 'backgroundColor': ['#111', '#222']}]

    def get_tooltips(self):
        return {'callbacks': {'beforeLabel': 'doughnutbeforeLabel'}}


class OptionPlacementTest(TestCase):
    """title, legend and tooltip live under ``options.plugins`` since v3."""

    def test_title_legend_and_tooltip_are_plugins(self):
        options = VerticalBar().get_options()

        self.assertEqual(options['plugins']['title'],
                         {'display': True, 'text': 'a title'})
        self.assertEqual(options['plugins']['legend'], {'position': 'top'})
        for moved in ('title', 'legend', 'tooltips', 'tooltip'):
            self.assertNotIn(moved, options)

    def test_get_tooltips_configures_the_tooltip_plugin(self):
        options = Doughnut().get_options()

        self.assertEqual(
            options['plugins']['tooltip'],
            {'callbacks': {'beforeLabel': 'doughnutbeforeLabel'}})

    def test_a_plugin_this_library_does_not_know_survives(self):
        class Annotated(VerticalBar):
            def get_plugins(self):
                return {'annotation': {'annotations': {}}}

        options = Annotated().get_options()

        self.assertEqual(options['plugins']['annotation'], {'annotations': {}})
        self.assertIn('title', options['plugins'])

    def test_scales_are_keyed_not_listed(self):
        self.assertEqual(Stacked().get_options()['scales'],
                         {'x': {'stacked': True}, 'y': {'stacked': True}})

    def test_a_horizontal_bar_is_a_bar_along_the_y_axis(self):
        graph = HorizontalBar().get_graph_data()

        self.assertEqual(graph['type'], 'bar')
        self.assertEqual(graph['options']['indexAxis'], 'y')
        self.assertEqual(graph['options']['elements'], {'bar': {'borderWidth': 2}})


class LegacyConfigurationTest(TestCase):
    """Chart.js 2 shapes a project may still be returning from its getters."""

    def test_the_xaxes_yaxes_lists_become_a_keyed_dict(self):
        self.assertEqual(
            scales_to_v4({'xAxes': [{'stacked': True}],
                          'yAxes': [{'stacked': True}]}),
            {'x': {'stacked': True}, 'y': {'stacked': True}})

    def test_a_second_axis_keeps_its_id_or_is_numbered(self):
        scales = scales_to_v4(
            {'yAxes': [{'id': 'left'}, {'id': 'right'}, {'display': False}]})

        self.assertEqual(sorted(scales), ['left', 'right', 'y3'])
        # `id` named the axis in the list form; the key does it now.
        self.assertNotIn('id', scales['left'])

    def test_scale_label_and_grid_lines_are_renamed(self):
        scales = scales_to_v4({'yAxes': [{
            'scaleLabel': {'display': True, 'labelString': 'units'},
            'gridLines': {'drawOnChartArea': False},
        }]})

        self.assertEqual(scales['y']['title'], {'display': True, 'text': 'units'})
        self.assertEqual(scales['y']['grid'], {'drawOnChartArea': False})
        self.assertNotIn('scaleLabel', scales['y'])
        self.assertNotIn('gridLines', scales['y'])

    def test_the_v2_ticks_range_moves_onto_the_scale(self):
        """Chart.js 4 silently ignores ticks.min/max; the range lives on the
        scale now, while stepSize stays inside ticks."""
        scales = scales_to_v4({'xAxes': [
            {'ticks': {'min': 0, 'max': 1, 'stepSize': 0.1}}]})

        self.assertEqual(scales['x']['min'], 0)
        self.assertEqual(scales['x']['max'], 1)
        self.assertEqual(scales['x']['ticks'], {'stepSize': 0.1})

    def test_a_chart_returning_the_old_scales_shape_still_serializes(self):
        class OldScales(DemoData, LineChart):
            def get_scales(self):
                return {'yAxes': [{'ticks': {'beginAtZero': True}}]}

        self.assertEqual(OldScales().get_options()['scales'],
                         {'y': {'ticks': {'beginAtZero': True}}})

    def test_elements_rectangle_is_elements_bar(self):
        self.assertEqual(elements_to_v4({'rectangle': {'borderWidth': 2}}),
                         {'bar': {'borderWidth': 2}})

    def test_a_dataset_stepped_line_is_renamed(self):
        class OldStepped(DemoData, LineChart):
            def get_datasets(self):
                return [{'label': 'series', 'data': [1, 2],
                         'steppedLine': 'middle'}]

        dataset = OldStepped().get_data()['datasets'][0]

        self.assertEqual(dataset['stepped'], 'middle')
        self.assertNotIn('steppedLine', dataset)

    def test_the_horizontal_bar_type_is_translated(self):
        class OldHorizontal(DemoData, VerticalBarChart):
            def get_type(self):
                return 'horizontalBar'

        graph = OldHorizontal().get_graph_data()

        self.assertEqual(graph['type'], 'bar')
        self.assertEqual(graph['options']['indexAxis'], 'y')


class SerializedPayloadTest(TestCase):
    """What the viewset actually answers, through the serializer."""

    def serialize(self, chart):
        data = chart.get_graph_data()
        return chart.serializer_class(data).data

    def test_a_bar_chart_serializes_to_the_v4_vocabulary(self):
        payload = self.serialize(VerticalBar())

        self.assertEqual(payload['type'], 'bar')
        self.assertEqual(payload['options']['plugins']['title']['text'], 'a title')
        self.assertNotIn('tooltips', payload['options'])

    def test_scales_survive_the_serializer(self):
        payload = self.serialize(Stacked())

        self.assertEqual(payload['options']['scales']['x']['stacked'], True)
        self.assertEqual(payload['options']['scales']['y']['stacked'], True)

    def test_a_scale_range_survives_the_serializer(self):
        class Ranged(DemoData, LineChart):
            def get_scales(self):
                return {'x': {'min': 0, 'max': 1, 'ticks': {'stepSize': 0.1}}}

        payload = self.serialize(Ranged())

        self.assertEqual(payload['options']['scales']['x'],
                         {'min': 0, 'max': 1, 'ticks': {'stepSize': 0.1}})

    def test_a_scale_only_carries_what_it_declared(self):
        """No default `position`: on the x scale of a v4 chart it is a position,
        not a harmless leftover."""
        class Titled(DemoData, LineChart):
            def get_scales(self):
                return {'x': {'display': True}}

        payload = self.serialize(Titled())

        self.assertEqual(payload['options']['scales']['x'], {'display': True})

    def test_the_doughnut_animation_keeps_both_flags(self):
        payload = self.serialize(Doughnut())

        self.assertEqual(payload['options']['animation'],
                         {'animateScale': True, 'animateRotate': True})

    def test_a_chart_without_getters_still_answers_options(self):
        class Bare(DemoData, BaseChartGetter):
            def get_type(self):
                return 'bar'

        self.assertEqual(Bare().get_options(), {})


class LabelsBeforeDatasetsTest(TestCase):
    """get_labels() runs before get_datasets(): subclasses often compute the
    series inside get_labels(), and get_datasets() only packages them."""

    def test_get_data_calls_labels_first(self):
        calls = []

        class Ordered(VerticalBar):
            def get_labels(self):
                calls.append('labels')
                self.series = [1, 2]
                return ['one', 'two']

            def get_datasets(self):
                calls.append('datasets')
                return [{'label': 'series', 'data': self.series}]

        data = Ordered().get_data()
        self.assertEqual(calls, ['labels', 'datasets'])
        self.assertEqual(data['datasets'][0]['data'], [1, 2])
