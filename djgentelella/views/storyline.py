import csv
import json
from rest_framework import serializers

from django.http import HttpResponse, JsonResponse
from django.urls import path, reverse, reverse_lazy
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

class OptionsSerializer(serializers.Serializer):
    data = DataSerializer
    chart = ChartSerializer
    slider = SliderSerializer


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
        # this view only retrieves the options from the overridden self.create_options in gtstoryline, validates them
        # and add the url to get_csv() view
        options = self.create_options()
        url_name = request.GET.get('url_name')
        options_serializer = OptionsSerializer(data=options)
        if options_serializer.is_valid():
            self.csv = self.create_csv()
            self.options.update(options)
            pk = None
            options['data']['url'] = reverse_lazy(url_name+'-detail', args=[pk])
            return JsonResponse(self.options)
        else:
            return JsonResponse(options_serializer.errors, status=400)

    def create_csv(self):
        # overriden method to create csv
        pass

    def retrieve(self, request, pk=None):
        # this view only retrieves the csv from the overrriden method self.create_csv()
        # then it validates the info and creates the response for storyline
        csv_data = self.create_csv()
        try:
            reader = csv.reader(csv_data)
            parsed_lines = list(reader)
            title_len = len(parsed_lines[0])
            response = HttpResponse(
                content_type='text/csv',
                headers={'Content-Disposition': 'attachment; filename="data.csv"'})
            writer = csv.writer(response)
            for index, row in enumerate(parsed_lines):
                if len(row) < title_len:
                    if len(row) < 2:
                        raise Exception("Less than two columns defined in line {}".format(index+1))
                    row.append(",")
                elif len(row) > title_len:
                    raise Exception("defined {} columns, but found {} columns in line {}".format(title_len, len(row),
                                                                                                  index + 1))
                writer.writerow(row)
            return response
        except Exception as e:
            return HttpResponse(e, status=400, reason=e)




