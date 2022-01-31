import csv
import json
from itertools import repeat

from rest_framework import serializers

from django.http import HttpResponse, JsonResponse
from django.urls import path, reverse, reverse_lazy, NoReverseMatch
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
    data = DataSerializer(required=True)
    chart = ChartSerializer(required=True)
    slider = SliderSerializer(required=True)


class StorylineBuilder(ViewSet):

    options = {}
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
        print(url_name)
        options_serializer = OptionsSerializer(data=options)
        try:
            options_serializer.is_valid(raise_exception=True)
            self.options.update(options)
            pk = None
            options['data']['url'] = reverse(url_name+'-detail', args=[pk])
            return JsonResponse(self.options)
        except NoReverseMatch as e:
            resp = {"error": e.args[0]}
            return JsonResponse(resp, status=400)
        except TypeError as e:
            resp = {"error": e.args[0]}
            return JsonResponse(resp, status=400)
        except Exception as e:
            return JsonResponse(e, status=400)


    def create_csv(self):
        # overriden method to create csv
        pass

    def validate_csv(self):
        csv_data = self.create_csv()
        reader = csv.reader(csv_data)
        parsed_lines = list(reader)
        title_len = len(parsed_lines[0])
        valid = True
        finished = False
        exception = ""
        while valid and not finished:
            for index, row in enumerate(parsed_lines):
                if len(row) < 2:
                    exception = "Less than two columns defined in line {}".format(index + 1)
                    valid = False
                elif len(row) > title_len:
                    exception = "defined {} columns, but found {} columns in line {}".format(title_len, len(row), index + 1)
                    valid = False
            finished = True
        return valid, exception

    def retrieve(self, request, pk=None):
        # this view only retrieves the csv from the overriden method self.create_csv()
        # then it validates the info and creates the response for storyline
        try:
            valid, csv_data = self.validate_csv()
            if valid:
                csv_data = self.create_csv()
                reader = csv.reader(csv_data)
                parsed_lines = list(reader)
                title_len = len(parsed_lines[0])
                response = HttpResponse(
                    content_type='text/csv',
                    headers={'Content-Disposition': 'attachment; filename="data.csv"'})
                writer = csv.writer(response)
                for index, row in enumerate(parsed_lines):
                    if len(row) < title_len:
                        for i in range(len(row), title_len):
                            row.append(",")
                    writer.writerow(row)
                return response
            else:
                return HttpResponse(status=400, reason=csv_data)
        except Exception as e:
            return HttpResponse(status=400, reason=e)




