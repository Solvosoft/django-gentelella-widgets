import csv

from django.http import HttpResponse, JsonResponse, Http404
from django.urls import reverse, NoReverseMatch
from rest_framework.viewsets import ReadOnlyModelViewSet
from djgentelella.serializers.storyline import OptionsSerializer


class StorylineBuilder(ReadOnlyModelViewSet):
    urlbasename = None
    options = {}
    retryname = "storyline"
    line_jump = "\n"
    delimit = ","
    allow_errors = True
    exit_on_error = False
    validate = True
    row_size = 5
    title_len = None

    def create_options(self):
        raise NotImplementedError()

    def list(self, request):
        if self.urlbasename is None:
            raise NameError("No base name set")
        try:
            options = self.create_options()
            options['data']['url'] = reverse(self.urlbasename + '-detail', args=[self.retryname])
            options_serializer = OptionsSerializer(data=options)
            options_serializer.is_valid(raise_exception=True)
            return JsonResponse(options_serializer.data)
        except NoReverseMatch as e:
            resp = {"error": e.args[0]}
            return JsonResponse(resp, status=400)
        except TypeError as e:
            resp = {"error": e.args[0]}
            return JsonResponse(resp, status=400)
        except Exception as e:
            return JsonResponse(e, status=400)

    def get_csv(self):
        raise NotImplementedError("You must create get_csv method in your class")

    def validate_row(self, row):
        ok = True
        if not self.validate:
            return row

        if self.title_len is None:
            # only the first one call update the len so always is row[0]
            self.title_len = len(row)
            if self.title_len < 2:
                ok=False
        # do checks
        if len(row) < self.row_size or len(row) != self.title_len:
            ok=False

        if ok or self.allow_errors:
            return row

    def retrieve(self, request, pk=None):
        if pk != self.retryname:
            return HttpResponse(status=400, reason=f"Bad name {pk} != {self.retryname}")
        errors = False
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="data.csv"'})
        writer = csv.writer(response, delimiter=self.delimit)

        for row in self.get_csv():
            validate_row = self.validate_row(row)
            if validate_row is None:
                errors = True
                if self.exit_on_error:
                    break
                continue
            writer.writerow(row)

        if errors and self.exit_on_error:
            return HttpResponse(status=400, reason="Invalid csv data")

        return response



