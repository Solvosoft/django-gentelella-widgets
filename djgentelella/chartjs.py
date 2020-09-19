from rest_framework import serializers, viewsets
from rest_framework.response import Response


class DataSetSerializer(serializers.Serializer):
    label = serializers.CharField()
    backgroundColor = serializers.CharField(required=False)
    borderColor = serializers.CharField(required=False)
    data = serializers.ListField(child=serializers.IntegerField())
    fill = serializers.BooleanField(default=False, required=False)
    borderWidth = serializers.IntegerField(default=0, required=False)
    stack = serializers.CharField(required=False)
    steppedLine = serializers.CharField(required=False)
    type = serializers.CharField(required=False)


class DataPieSetSerializer(serializers.Serializer):
    label = serializers.CharField()
    backgroundColor = serializers.ListField(child=serializers.CharField(required=False))
    data = serializers.ListField(child=serializers.IntegerField())
    fill = serializers.BooleanField(default=False, required=False)

    # borderWidth = serializers.IntegerField(default=0, required=False)
    # stack = serializers.CharField(required=False)
    # steppedLine = serializers.CharField(required=False)


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
    steppedLine = serializers.CharField(required=False)
    type = serializers.CharField(required=False)


class DataSerializer(serializers.Serializer):
    labels = serializers.ListField(child=serializers.CharField())
    datasets = serializers.ListField(child=DataSetSerializer())


class TitleSerializer(serializers.Serializer):
    display = serializers.BooleanField(default=False, required=False)
    text = serializers.CharField(required=False)


class LegendSerializer(serializers.Serializer):
    position = serializers.CharField(required=False, default='top')


class TooltipsSerializer(serializers.Serializer):
    mode = serializers.CharField(required=False)
    intersect = serializers.BooleanField(required=False)
    callbacks = serializers.DictField(child=serializers.CharField(), required=False)


class HoverSerializer(serializers.Serializer):
    mode = serializers.CharField(required=False)
    intersect = serializers.BooleanField(required=False)


class scaleLabelSerializer(serializers.Serializer):
    display = serializers.BooleanField(required=False)
    labelString = serializers.CharField(required=False)


class gridLinesSerializer(serializers.Serializer):
    drawOnChartArea = serializers.BooleanField()


class ScaleSerializer(serializers.Serializer):
    type = serializers.CharField(required=False)
    stacked = serializers.BooleanField(required=False, default=False)
    display = serializers.BooleanField(required=False, default=True)
    position = serializers.CharField(required=False, default='left')
    id = serializers.CharField(required=False)
    scaleLabel = scaleLabelSerializer(required=False)
    gridLines = gridLinesSerializer(required=False)
    time = serializers.DictField(child=serializers.CharField(), required=False)


class OptionScaleSerializer(serializers.Serializer):
    xAxes = serializers.ListField(child=ScaleSerializer(), required=False)
    yAxes = serializers.ListField(child=ScaleSerializer(), required=False)


class RectangleSerialize(serializers.Serializer):
    borderWidth = serializers.IntegerField(default=0)


class ElementsSerialize(serializers.Serializer):
    rectangle = RectangleSerialize()


class AnimationSerialize(serializers.Serializer):
    animateScale = serializers.BooleanField(required=False)
    animateRotate: serializers.BooleanField(required=False)


class OptionsSerializer(serializers.Serializer):
    responsive = serializers.BooleanField(default=True, required=False)
    title = TitleSerializer(required=False)
    legend = LegendSerializer(required=False)
    tooltips = TooltipsSerializer(required=False)
    hover = HoverSerializer(required=False)
    scales = OptionScaleSerializer(required=False)
    elements = ElementsSerialize(required=False)
    animation = AnimationSerialize(required=False)


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

    def get_options(self):
        options = ['responsive', 'legend', 'title', 'tooltips', 'hover', 'scales', 'elements', 'animation']
        dev = {}
        for option in options:
            if hasattr(self, 'get_' + option):
                dev[option] = getattr(self, 'get_' + option)()
        return dev

    def get_type(self):
        raise NotImplementedError()

    def get_labels(self):
        raise NotImplementedError()

    def get_datasets(self):
        raise NotImplementedError()

    def get_data(self):
        return {
            'labels': self.get_labels(),
            'datasets': self.get_datasets()
        }

    def get_graph_data(self):
        return {
            'type': self.get_type(),
            'data': self.get_data(),
            'options': self.get_options()
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
        return 'horizontalBar'

    def get_responsive(self):
        return True

    def get_legend(self):
        return {'position': 'right'}

    def get_elements(self):
        return {'rectangle': {'borderWidth': 2}}


class StackedBarChart(BaseChartGetter):
    def get_type(self):
        return 'bar'

    def get_tooltips(self):
        return {'mode': 'index', 'intersect': False}

    def get_responsive(self):
        return True

    def get_scales(self):
        return {'xAxes': [{'stacked': True, }], 'yAxes': [{'stacked': True}]}


class LineChart(BaseChartGetter):
    def get_type(self):
        return 'line'

    def get_tooltips(self):
        return {'mode': 'index', 'intersect': False}

    def get_responsive(self):
        return True

    # def get_scales(self):
    #     return {'xAxes': [{'stacked': True, }], 'yAxes': [{'stacked': True}] }

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
