import io
import csv
from django.template.loader import render_to_string

from djgentelella.groute import register_lookups
from djgentelella.views.storyline import StorylineBuilder


@register_lookups(prefix="storyline", basename="examplestoryline")
class StorylineExample(StorylineBuilder):
    urlbasename = "examplestoryline"  # must be the same as basename register_lookups

    def create_options(self):
        options = {
            "data": {
                "datetime_column_name": "date",
                "datetime_format": "%Y-%m-%d",
                "data_column_name": "income"},
            "chart": {
                "datetime_format": "%Y",
                "y_axis_label": "Income"
            },
            "slider": {
                "start_at_card": "1",
                "title_column_name": "title",
                "text_column_name": "text",
            }}
        return options

    def get_csv(self):
        csvfile = io.StringIO(render_to_string('storyline.csv'))
        reader = csv.reader(csvfile, delimiter=',')

        for row in reader:
            yield list(row)

