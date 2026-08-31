"""Server side of the ``DJGraph`` widget: the chart configuration as DRF.

The javascript never builds a chart configuration -- ``gentelella_chart``
fetches this JSON and hands it to ``new Chart(ctx, config)`` unchanged. So the
serializers below are the schema of a Chart.js configuration, and the
``get_<option>()`` hooks on :class:`BaseChartGetter` are what a project
overrides to shape a chart.

**Chart.js 4.** The vocabulary here is Chart.js 4's, which renamed a good part
of Chart.js 2's:

===============================  ==========================================
Chart.js 2                       Chart.js 4
===============================  ==========================================
``options.title``                ``options.plugins.title``
``options.legend``               ``options.plugins.legend``
``options.tooltips``             ``options.plugins.tooltip``
``scales.xAxes: [{...}]``        ``scales: {x: {...}}``
``scale.scaleLabel.labelString`` ``scale.title.text``
``scale.gridLines``              ``scale.grid``
``elements.rectangle``           ``elements.bar``
``dataset.steppedLine``          ``dataset.stepped``
``type: 'horizontalBar'``        ``type: 'bar'`` + ``indexAxis: 'y'``
===============================  ==========================================

The **getter names did not change**: ``get_title``, ``get_legend`` and
``get_tooltips`` name a chart concept, not a configuration path, so a subclass
written against the old release keeps working -- ``get_options`` files what
they return under ``options.plugins``. The three shapes that could not survive
a rename are translated instead of dropped: a ``scales`` dict in the
``xAxes``/``yAxes`` form, an ``elements.rectangle`` block, and a
``steppedLine`` key on a dataset. Those translations are transitional; write
new charts in the Chart.js 4 vocabulary.
"""

from rest_framework import serializers, viewsets
from rest_framework.response import Response

#: Dataset keys Chart.js 3 renamed. Applied by :meth:`BaseChartGetter.get_data`.
LEGACY_DATASET_KEYS = {'steppedLine': 'stepped'}


def scale_to_v4(scale):
    """Rename the two keys Chart.js 3 moved inside a single scale."""
    scale = dict(scale)
    label = scale.pop('scaleLabel', None)
    if label is not None:
        title = {key: value for key, value in label.items()
                 if key != 'labelString'}
        if 'labelString' in label:
            title['text'] = label['labelString']
        scale.setdefault('title', title)
    grid = scale.pop('gridLines', None)
    if grid is not None:
        scale.setdefault('grid', grid)
    # v2 kept the range inside ticks; from Chart.js 3 on min/max live on the
    # scale itself and ticks.min/max are silently ignored.
    ticks = scale.get('ticks')
    if isinstance(ticks, dict) and {'min', 'max'} & set(ticks):
        ticks = dict(ticks)
        for bound in ('min', 'max'):
            if bound in ticks:
                scale.setdefault(bound, ticks.pop(bound))
        scale['ticks'] = ticks
    # `id` named the axis in the v2 list form; in v4 the key of the dict does.
    scale.pop('id', None)
    return scale


def scales_to_v4(scales):
    """Accept both the Chart.js 4 ``{'x': {...}}`` and the Chart.js 2
    ``{'xAxes': [{...}]}`` shapes, always returning the former.

    The v2 form named the second and later axes through their ``id``; without
    one they become ``x2``, ``y2``, ... in declaration order, which is what the
    dataset's ``xAxisID``/``yAxisID`` then has to point at.
    """
    if not scales:
        return scales
    if not {'xAxes', 'yAxes'} & set(scales):
        return {name: scale_to_v4(scale) for name, scale in scales.items()}

    dev = {name: scale_to_v4(scale) for name, scale in scales.items()
           if name not in ('xAxes', 'yAxes')}
    for legacy, axis in (('xAxes', 'x'), ('yAxes', 'y')):
        for position, scale in enumerate(scales.get(legacy) or []):
            name = scale.get('id') or (axis if position == 0
                                       else '%s%d' % (axis, position + 1))
            dev[name] = scale_to_v4(scale)
    return dev


def elements_to_v4(elements):
    """``elements.rectangle`` is ``elements.bar`` from Chart.js 3 on."""
    if not elements or 'rectangle' not in elements:
        return elements
    elements = dict(elements)
    elements.setdefault('bar', elements.pop('rectangle'))
    return elements


class DataSetSerializer(serializers.Serializer):
    label = serializers.CharField()
    backgroundColor = serializers.CharField(required=False)
    borderColor = serializers.CharField(required=False)
    data = serializers.ListField(child=serializers.FloatField())
    fill = serializers.BooleanField(default=False, required=False)
    borderWidth = serializers.IntegerField(default=0, required=False)
    stack = serializers.CharField(required=False)
    stepped = serializers.CharField(required=False)
    type = serializers.CharField(required=False)


class DataPieSetSerializer(serializers.Serializer):
    label = serializers.CharField()
    backgroundColor = serializers.ListField(child=serializers.CharField(required=False))
    data = serializers.ListField(child=serializers.IntegerField())
    fill = serializers.BooleanField(default=False, required=False)


class ScatterItemSerializer(serializers.Serializer):
    x = serializers.IntegerField()
    y = serializers.IntegerField()


class DataScatterSetSerializer(serializers.Serializer):
    label = serializers.CharField()
    backgroundColor = serializers.CharField(required=False)
    borderColor = serializers.CharField(required=False)
    data = serializers.ListField(child=ScatterItemSerializer())
    fill = serializers.BooleanField(default=False, required=False)
    borderWidth = serializers.IntegerField(default=0, required=False)
    stack = serializers.CharField(required=False)
    stepped = serializers.CharField(required=False)
    type = serializers.CharField(required=False)


class DataSerializer(serializers.Serializer):
    labels = serializers.ListField(child=serializers.CharField())
    datasets = serializers.ListField(child=DataSetSerializer())


class TitleSerializer(serializers.Serializer):
    display = serializers.BooleanField(default=False, required=False)
    text = serializers.CharField(required=False)


class LegendSerializer(serializers.Serializer):
    display = serializers.BooleanField(required=False)
    position = serializers.CharField(required=False, default='top')


class TooltipSerializer(serializers.Serializer):
    mode = serializers.CharField(required=False)
    intersect = serializers.BooleanField(required=False)
    # The values are names, not functions: the browser looks each one up in
    # `document.chartcallbacks`. JSON cannot carry a callable.
    callbacks = serializers.DictField(child=serializers.CharField(), required=False)


class PluginsSerializer(serializers.Serializer):
    title = TitleSerializer(required=False)
    legend = LegendSerializer(required=False)
    tooltip = TooltipSerializer(required=False)

    def to_representation(self, instance):
        """Keep the plugins this serializer does not know about.

        ``options.plugins`` is also where third-party plugins are configured
        (datalabels, annotation, zoom); the field used to be a bare DictField,
        so dropping anything unlisted here would silently break those charts.
        """
        dev = super().to_representation(instance)
        for name, value in instance.items():
            dev.setdefault(name, value)
        return dev


class HoverSerializer(serializers.Serializer):
    mode = serializers.CharField(required=False)
    intersect = serializers.BooleanField(required=False)


class ScaleTitleSerializer(serializers.Serializer):
    display = serializers.BooleanField(required=False)
    text = serializers.CharField(required=False)


class GridSerializer(serializers.Serializer):
    display = serializers.BooleanField(required=False)
    drawOnChartArea = serializers.BooleanField(required=False)


class ScaleSerializer(serializers.Serializer):
    type = serializers.CharField(required=False)
    stacked = serializers.BooleanField(required=False)
    display = serializers.BooleanField(required=False)
    position = serializers.CharField(required=False)
    beginAtZero = serializers.BooleanField(required=False)
    min = serializers.FloatField(required=False)
    max = serializers.FloatField(required=False)
    suggestedMin = serializers.FloatField(required=False)
    suggestedMax = serializers.FloatField(required=False)
    title = ScaleTitleSerializer(required=False)
    grid = GridSerializer(required=False)
    time = serializers.DictField(child=serializers.CharField(), required=False)
    ticks = serializers.DictField(required=False)


class ElementsSerializer(serializers.Serializer):
    bar = serializers.DictField(required=False)
    line = serializers.DictField(required=False)
    point = serializers.DictField(required=False)
    arc = serializers.DictField(required=False)


class AnimationSerializer(serializers.Serializer):
    # Both survive in Chart.js 4 as doughnut/pie specific options. animateRotate
    # used to be written as an annotation here, so it was never a field and the
    # value a chart returned for it was silently dropped.
    animateScale = serializers.BooleanField(required=False)
    animateRotate = serializers.BooleanField(required=False)


class OptionsSerializer(serializers.Serializer):
    responsive = serializers.BooleanField(default=True, required=False)
    maintainAspectRatio = serializers.BooleanField(required=False)
    # 'y' turns a bar chart into what Chart.js 2 called a horizontalBar.
    indexAxis = serializers.CharField(required=False)
    plugins = PluginsSerializer(required=False)
    hover = HoverSerializer(required=False)
    scales = serializers.DictField(child=ScaleSerializer(), required=False)
    elements = ElementsSerializer(required=False)
    animation = AnimationSerializer(required=False)


class ChartSerializer(serializers.Serializer):
    type = serializers.CharField(required=True)
    data = DataSerializer(required=True)
    options = OptionsSerializer(required=True)


class DataPieSerializer(serializers.Serializer):
    labels = serializers.ListField(child=serializers.CharField())
    datasets = serializers.ListField(child=DataPieSetSerializer())


class PieSerializer(serializers.Serializer):
    type = serializers.CharField(required=True)
    data = DataPieSerializer(required=True)
    options = OptionsSerializer(required=True)


class DataScatterSerializer(serializers.Serializer):
    labels = serializers.ListField(child=serializers.CharField())
    datasets = serializers.ListField(child=DataScatterSetSerializer())


class ScatterSerializer(serializers.Serializer):
    type = serializers.CharField(required=True)
    data = DataScatterSerializer(required=True)
    options = OptionsSerializer(required=True)


class BaseChartGetter(viewsets.ViewSet):
    serializer_class = ChartSerializer

    #: Read straight from ``get_<name>()`` into ``options``.
    option_names = ['responsive', 'maintainAspectRatio', 'indexAxis', 'hover',
                    'scales', 'elements', 'animation', 'plugins']
    #: Getter name -> the plugin it configures. Chart.js 3 moved these three out
    #: of ``options`` and into ``options.plugins``; the getters kept their names.
    plugin_option_names = {'title': 'title', 'legend': 'legend',
                           'tooltips': 'tooltip', 'tooltip': 'tooltip'}

    def get_options(self):
        dev = {}
        for option in self.option_names:
            if hasattr(self, 'get_' + option):
                dev[option] = getattr(self, 'get_' + option)()

        plugins = dict(dev.get('plugins') or {})
        for getter, plugin in self.plugin_option_names.items():
            if hasattr(self, 'get_' + getter):
                plugins[plugin] = getattr(self, 'get_' + getter)()
        if plugins:
            dev['plugins'] = plugins

        if dev.get('scales'):
            dev['scales'] = scales_to_v4(dev['scales'])
        if dev.get('elements'):
            dev['elements'] = elements_to_v4(dev['elements'])
        return dev

    def get_type(self):
        raise NotImplementedError()

    def get_labels(self):
        raise NotImplementedError()

    def get_datasets(self):
        raise NotImplementedError()

    def get_data(self):
        # get_labels() runs first by contract: subclasses often compute in it
        # the series that get_datasets() only packages afterwards.
        labels = self.get_labels()
        datasets = []
        for dataset in self.get_datasets():
            dataset = dict(dataset)
            for legacy, current in LEGACY_DATASET_KEYS.items():
                if legacy in dataset:
                    dataset.setdefault(current, dataset.pop(legacy))
            datasets.append(dataset)
        return {
            'labels': labels,
            'datasets': datasets
        }

    def get_graph_data(self):
        chart_type = self.get_type()
        options = self.get_options()
        if chart_type == 'horizontalBar':  # removed as a type in Chart.js 3
            chart_type = 'bar'
            options.setdefault('indexAxis', 'y')
        return {
            'type': chart_type,
            'data': self.get_data(),
            'options': options
        }

    def list(self, request):
        self.request = request
        data = self.get_graph_data()
        serializer = self.serializer_class(data)
        return Response(serializer.data)


class VerticalBarChart(BaseChartGetter):
    def get_type(self):
        return 'bar'

    def get_responsive(self):
        return True

    def get_legend(self):
        return {'position': 'top'}


class HorizontalBarChart(BaseChartGetter):
    def get_type(self):
        return 'bar'

    def get_indexAxis(self):
        return 'y'

    def get_responsive(self):
        return True

    def get_legend(self):
        return {'position': 'right'}

    def get_elements(self):
        return {'bar': {'borderWidth': 2}}


class StackedBarChart(BaseChartGetter):
    def get_type(self):
        return 'bar'

    def get_tooltips(self):
        return {'mode': 'index', 'intersect': False}

    def get_responsive(self):
        return True

    def get_scales(self):
        return {'x': {'stacked': True}, 'y': {'stacked': True}}


class LineChart(BaseChartGetter):
    def get_type(self):
        return 'line'

    def get_tooltips(self):
        return {'mode': 'index', 'intersect': False}

    def get_responsive(self):
        return True

    def get_hover(self):
        return {'mode': 'nearest', 'intersect': True}


class PieChart(BaseChartGetter):
    serializer_class = PieSerializer

    def get_type(self):
        return 'pie'

    def get_responsive(self):
        return True


class DoughnutChart(BaseChartGetter):
    serializer_class = PieSerializer

    def get_type(self):
        return 'doughnut'

    def get_responsive(self):
        return True

    def get_legend(self):
        return {'position': 'top', }

    def get_animation(self):
        return {'animateScale': True, 'animateRotate': True}


class ScatterChart(BaseChartGetter):
    serializer_class = ScatterSerializer

    def get_type(self):
        return 'scatter'

    def get_responsive(self):
        return True
