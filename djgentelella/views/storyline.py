import csv
import json

from django.http import HttpResponse, JsonResponse
from django.urls import path, reverse


class StorylineBuilder:

    options = {}

    name = "gtExample"

    def get_options(self, request):
        request_options = request.GET.get('options')
        options = json.loads(request_options)
        request_csv = request.GET.get('csv').replace("\"","")
        self.options.update(options)
        options['data']['url'] = reverse(self.name+"csv", args=[request_csv])

        return JsonResponse(self.options)

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



