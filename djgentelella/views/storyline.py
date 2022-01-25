import csv
import json
from rest_framework import serializers

from django.http import HttpResponse, JsonResponse
from django.urls import path, reverse
from rest_framework.serializers import Serializer


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


class StorylineBuilder:

    options = {}
    name = "storyline"

    def validate_csv(self, csv_data):
        csv_data = csv_data.splitlines()
        try:
            reader = csv.reader(csv_data)
            parsed_lines = list(reader)
            title_len = len(parsed_lines[0])
            for index, row in enumerate(parsed_lines):
                if len(row) > title_len:
                    return False, "defined {} columns, but found {} columns in line {}".format(title_len, len(row),
                                                                                               index + 1)
            return True, "CSV is correct"
        except:
            return False, "CSV format is incorrect"



    def get_options(self, request):
        request_options = request.GET.get('options')
        options = json.loads(request_options)
        data_info = options['data']
        chart_info = options['chart']
        slider_info = options['slider']
        data_val = DataSerializer(data=data_info)
        chart_val = ChartSerializer(data=chart_info)
        slider_val = SliderSerializer(data=slider_info)
        if data_val.is_valid():
            if chart_val.is_valid():
                if slider_val.is_valid():
                    request_csv = request.GET.get('csv')
                    # validate CSV
                    val_csv, msg_csv = self.validate_csv(request_csv)
                    if val_csv:
                        self.options.update(options)
                        options['data']['url'] = reverse(self.name+"csv", args=[request_csv])
                        return JsonResponse(self.options)
                    else:
                        return JsonResponse(msg_csv, status=400)
                else:
                    return JsonResponse(slider_val.errors, status=400)
            else:
                return JsonResponse(chart_val.errors, status=400)
        else:
            return JsonResponse(data_val.errors, status=400)

    def get_csv(self, request, **kwargs):
        csv_data = kwargs['request_csv'].replace("\\r\\n","\r\n").splitlines()
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="data.csv"'})

        reader = csv.reader(csv_data)
        parsed_lines = list(reader)
        writer = csv.writer(response)
        for row in parsed_lines:
            mod_row = list(row)
            writer.writerow(row)

        return response
    def urls(self):
        return [
            path('stoptions', self.get_options, name=self.name+"options"),
            path('stcsv/<str:request_csv>', self.get_csv, name=self.name + "csv"),
        ]




