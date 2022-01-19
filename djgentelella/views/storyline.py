import csv
import datetime
import os

from django.http import HttpResponse, JsonResponse
from django.urls import path, reverse
from rest_framework import serializers
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet


class BaseStorylineView(ViewSet):

    options = {}

    def get_params(self):
        pass

    # initial attempt to obtain CSV, after that, should try to modify titles and coincidences issues

    #def list(self, request, format=None):
    #   self.request = request
    #  response = HttpResponse(
    #     content_type='text/csv',
    #        headers={'Content-Disposition': 'attachment; filename="datos.csv"'},
    #    )
    #    return Response(self.get_serializer(response).data)

class StorylineBuilder:

    def list(self, request):
        self.request = request
        file = []
        csv_url = request.data['csv_url']
        with open(csv_url,'r') as f:
            file = self.get_csv()
        response = HttpResponse(file, content_type='text/csv',
                                headers={'Content-Disposition': 'attachment; filename="datos.csv"'})
        return response

    options = {
        "data": {
                   "datetime_column_name": "year",
                   "datetime_format": "%Y",
                   "data_column_name": "temperature"},
               "chart": {
                   "datetime_format": "%Y",
                   "y_axis_label": "temperature"
               },
                 "slider": {
           "start_at_card": 0,
           "title_column_name": "Title",
           "text_column_name": "Text",
           "cards": [
               {
                   "display_date": "1980",
                   "title": "0: Global Temperature change",
                   "text": "Based on NASA data, this chart shows average annual temperature difference from a baseline computed over the years 1951-1980. See https://climate.nasa.gov/vital-signs/global-temperature/ for more information.",
                   "row_number": 2
               },
               {
                   "title": "Car Manufacturing Takes Off",
                   "text": "Here come the cars.",
                   "row_number": 3
               }
           ]
         }}

    name = "gtExample"

    def get_options(self, request):
        options = {}
        options.update(self.options)
        options['data']['url'] = reverse(self.name+"csv")

        return JsonResponse(self.options)

    def get_csv(self, request):

        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="datos.csv"'})

        writer = csv.writer(response)
        writer.writerow(self.get_headers())
        for row in self.get_rows():
            writer.writerow(row)

        return response

    def get_headers(self):
        return [
            "year","temperature"
        ]

    def get_rows(self):
        rows = {"1980": 35,"1990":60,"2000":25,"2010":32}
        for key, value in rows.items():
            yield [key,value]


    def urls(self):
        return [
            path('stoptions', self.get_options, name=self.name+"options"),
            path('stcsv', self.get_csv, name=self.name + "csv"),
        ]
