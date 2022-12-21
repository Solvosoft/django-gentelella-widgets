from random import randint

from djgentelella.chartjs import VerticalBarChart, HorizontalBarChart, \
    StackedBarChart, LineChart, PieChart, DoughnutChart, ScatterChart
from djgentelella.groute import register_lookups

default_colors = ["229, 158, 64", "240, 180, 150", "0, 168, 150", "207, 130, 182",
                  "2, 128, 144", "1, 148, 147",
                  "240, 112, 96", "153, 235, 168", "241, 179, 167", "242, 137, 76",
                  "175, 151, 195",
                  "161, 178, 200",
                  "245, 216, 144", "216, 15, 53", "233, 175, 97", "4, 115, 143",
                  "162, 237, 133", "226, 148, 72",
                  "5, 102, 141", "241, 125, 90", "236, 194, 128", "220, 239, 133",
                  "242, 157, 175", "187, 141, 189",
                  "238, 186, 140", "238, 16, 58", "2, 195, 154", "121, 219, 172",
                  "239, 98, 104", "231, 167, 81"]


class BaseChart:
    colors = default_colors

    def get_color(self):
        self.index = (self.index + 1) % len(self.colors)
        color_list = self.colors[self.index]
        color = 'rgb(' + color_list + ')'
        return color

    def get_labels(self):
        return ['January', 'February', 'March', 'April', 'May', 'June', 'July']

    def get_datasets(self):
        self.index = randint(0, len(self.colors))
        return [{'label': 'Stairway',
                 'backgroundColor': self.get_color(),
                 'borderColor': self.get_color(),
                 'borderWidth': 1,
                 'data': [1, 2, 3, 4, 5, 6, 7]
                 },
                {'label': 'Fibonacci',
                 'backgroundColor': self.get_color(),
                 'borderColor': self.get_color(),
                 'borderWidth': 1,
                 'data': [0, 1, 1, 2, 3, 5, 8]
                 },
                {'label': 'Base 2',
                 'backgroundColor': self.get_color(),
                 'borderColor': self.get_color(),
                 'borderWidth': 1,
                 'data': [1, 2, 4, 8, 16, 32, 64]
                 },
                ]


class CircularBase(BaseChart):
    def get_datasets(self):
        self.index = randint(0, len(self.colors))
        backgroundColor = [self.get_color() for x in range(7)]
        return [{'label': 'Stairway',
                 'backgroundColor': backgroundColor,
                 'data': [1, 2, 3, 4, 5, 6, 7]
                 },
                {'label': 'Fibonacci',
                 'backgroundColor': backgroundColor,
                 'data': [0, 1, 1, 2, 3, 5, 8]
                 },
                {'label': 'Base 2',
                 'backgroundColor': backgroundColor,
                 'data': [1, 2, 4, 8, 16, 32, 64]
                 },
                ]


@register_lookups(prefix="verticalbar", basename="verticalbar")
class VerticalBarChartExample(BaseChart, VerticalBarChart):

    def get_title(self):
        return {'display': True,
                'text': 'Chart.js Vertical Bar Chart'
                }


@register_lookups(prefix="horizontalbar", basename="horizontalbar")
class HorizontalBarChartExample(BaseChart, HorizontalBarChart):
    def get_title(self):
        return {'display': True,
                'text': 'Chart.js Horizontal Bar Chart'
                }


@register_lookups(prefix="stackedbar", basename="stackedbar")
class StackedBarChartExample(BaseChart, StackedBarChart):
    def get_title(self):
        return {'display': True,
                'text': 'Chart.js Stacked Bar Chart'
                }


@register_lookups(prefix="line", basename="line")
class LineChartExample(BaseChart, LineChart):
    def get_title(self):
        return {'display': True,
                'text': 'Chart.js Line Chart'
                }


@register_lookups(prefix="steppedline", basename="steppedline")
class steppedLineChartExample(BaseChart, LineChart):
    def get_title(self):
        return {'display': True,
                'text': 'Chart.js Stepped Middle Chart'
                }

    def get_datasets(self):
        self.index = randint(0, len(self.colors))
        return [{'label': 'Stairway',
                 'backgroundColor': self.get_color(),
                 'borderColor': self.get_color(),
                 'borderWidth': 1,
                 'steppedLine': 'middle',
                 'data': [1, 2, 3, 4, 5, 6, 7]
                 },
                {'label': 'Fibonacci',
                 'backgroundColor': self.get_color(),
                 'borderColor': self.get_color(),
                 'borderWidth': 1,
                 'steppedLine': 'middle',
                 'data': [0, 1, 1, 2, 3, 5, 8]
                 },
                {'label': 'Base 2',
                 'backgroundColor': self.get_color(),
                 'borderColor': self.get_color(),
                 'borderWidth': 1,
                 'steppedLine': 'middle',
                 'data': [1, 2, 4, 8, 16, 32, 64]
                 },
                ]


@register_lookups(prefix="arealine", basename="arealine")
class AreaChartExample(BaseChart, LineChart):
    def get_title(self):
        return {'display': True,
                'text': 'Chart.js Area Chart'
                }

    def get_datasets(self):
        self.index = randint(0, len(self.colors))
        return [{'label': 'Stairway',
                 'backgroundColor': self.get_color(),
                 'borderColor': self.get_color(),
                 'borderWidth': 1,
                 'fill': True,
                 'data': [1, 2, 3, 4, 5, 6, 7]
                 },
                {'label': 'Fibonacci',
                 'backgroundColor': self.get_color(),
                 'borderColor': self.get_color(),
                 'borderWidth': 1,
                 'fill': True,
                 'data': [0, 1, 1, 2, 3, 5, 8]
                 },
                {'label': 'Base 2',
                 'backgroundColor': self.get_color(),
                 'borderColor': self.get_color(),
                 'borderWidth': 1,
                 'fill': True,
                 'data': [1, 2, 4, 8, 16, 32, 64]
                 },
                ]


@register_lookups(prefix="pie", basename="pie")
class PieChartExample(BaseChart, PieChart):
    def get_title(self):
        return {'display': True,
                'text': 'Chart.js Pie Chart'
                }

    def get_datasets(self):
        self.index = randint(0, len(self.colors))
        return [{'data': [1, 2, 3, 4, 5, 6, 7],
                 'label': 'Stairway',
                 'backgroundColor': [self.get_color(), self.get_color(),
                                     self.get_color(), self.get_color(),
                                     self.get_color(), self.get_color(),
                                     self.get_color()]
                 }, ]


@register_lookups(prefix="doughnut", basename="doughnut")
class DoughnutChartExample(CircularBase, DoughnutChart):
    def get_title(self):
        return {'display': True,
                'text': 'Chart.js Doughnut Chart'
                }

    def get_legend(self):
        return {'display': True}

    def get_tooltips(self):
        return {
            'callbacks': {
                # 'label': 'doughnutlabels',
                'beforeLabel': 'doughnutbeforeLabel'
            }
        }


@register_lookups(prefix="linebar", basename="linebar")
class LineBarChartExample(BaseChart, LineChart):
    def get_title(self):
        return {'display': True,
                'text': 'Chart.js Line Chart'
                }

    def get_datasets(self):
        dataset = super().get_datasets()
        dataset[0]['type'] = 'bar'
        dataset[1]['type'] = 'bar'
        return dataset


@register_lookups(prefix="scatter", basename="scatter")
class ScatterChartExample(BaseChart, ScatterChart):

    def get_title(self):
        return {'display': True,
                'text': 'Chart.js Scatter Chart'
                }

    def get_datasets(self):
        self.index = randint(0, len(self.colors))
        return [{'label': 'Stairway',
                 'backgroundColor': self.get_color(),
                 'borderColor': self.get_color(),
                 'borderWidth': 1,
                 'data': [{'x': 1, 'y': 10}, {'x': 2, 'y': 20}, {'x': 3, 'y': 30}]
                 },
                {'label': 'Fibonacci',
                 'backgroundColor': self.get_color(),
                 'borderColor': self.get_color(),
                 'borderWidth': 1,
                 'data': [{'x': 1, 'y': 1}, {'x': 2, 'y': 5}, {'x': 3, 'y': 9}]
                 },
                {'label': 'Base 2',
                 'backgroundColor': self.get_color(),
                 'borderColor': self.get_color(),
                 'borderWidth': 1,
                 'data': [{'x': 1, 'y': 7}, {'x': 2, 'y': 3}, {'x': 3, 'y': 19}]
                 },
                ]

    def get_labels(self):
        return ['January', 'February', 'March']
