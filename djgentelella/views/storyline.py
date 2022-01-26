import csv
import json
from rest_framework import serializers

from django.http import HttpResponse, JsonResponse
from django.urls import path, reverse
from rest_framework.viewsets import ViewSet


class DataSerializer(serializers.Serializer):
    data_column_name = serializers.CharField(required=True)
    datetime_format = serializers.CharField(required=True) # still missing to validate date format
    datetime_column_name = serializers.CharField(required=True)


class ChartSerializer(serializers.Serializer):
    datetime_format = serializers.CharField(required=True)
    y_axis_label = serializers.CharField(required=False)


class CardSerializer(serializers.Serializer):
    title = serializers.CharField(required=True)
    text = serializers.CharField(required=True)
    row_number = serializers.CharField(required=True)
    display_date = serializers.CharField()


class SliderSerializer(serializers.Serializer):
    start_at_card = serializers.CharField()
    title_column_name = serializers.CharField(required=True)
    text_column_name = serializers.CharField(required=True)
    cards = CardSerializer(many=True, required=False)  #needs to check if cards work


class StorylineBuilder(ViewSet):

    options = {}
    csv = []
    name = "storyline"
    line_jump = "\n"
    delimit = ","

    def create_options(self):
        # overriden method to create options
        pass

    def list(self, request):
        # this view only retrieve the options from the overriden self.create_options in gtstoryline, validates them
        # and add the url to get_csv() view
        options = self.create_options()
        data_info = options['data']
        chart_info = options['chart']
        slider_info = options['slider']
        data_val = DataSerializer(data=data_info)
        chart_val = ChartSerializer(data=chart_info)
        slider_val = SliderSerializer(data=slider_info)
        if data_val.is_valid():
            if chart_val.is_valid():
                if slider_val.is_valid():
                    self.options.update(options)
                    options['data']['url'] = reverse(StorylineBuilder.name+"csv") # this one is the url to get to get_csv() view
                    return JsonResponse(self.options)
                else:
                    return JsonResponse(slider_val.errors, status=400)
            else:
                return JsonResponse(chart_val.errors, status=400)
        else:
            return JsonResponse(data_val.errors, status=400)

    def create_csv(self):
        # overriden method to create csv
        pass

    def get_csv(self, request):
        # this branch only needs to retrieve the csv from the overrriden method self.create_csv()
        # then it validates the info and creates the response for storyline
        csv_data = self.create_csv()
        try:
            # from here and on still needs to be checked, code havent compiled after this line
            reader = csv.reader(csv_data)
            parsed_lines = list(reader)
            title_len = len(parsed_lines[0])
            response = HttpResponse(
                content_type='text/csv',
                headers={'Content-Disposition': 'attachment; filename="data.csv"'})
            writer = csv.writer(response)
            for index, row in enumerate(parsed_lines):
                if len(row) < title_len:
                    parsed_lines[index] = row.ljust(title_len - len(row), ",")
                elif len(row) > title_len:
                    raise ValueError("defined {} columns, but found {} columns in line {}".format(title_len, len(row),
                                                                                                  index + 1))
                writer.writerow(row)
                return response
        except ValueError as e:
            return JsonResponse(e, status=400)

    def urls(self):
        # the url to get_csv(), not sure if this one is the one needed or should be handled differently
        # (similarly as the list view)
        return [
            # path('stoptions', self.get_options, name=self.name+"options"),
            path('stcsv', self.get_csv, name=StorylineBuilder.name + "csv"),
        ]




