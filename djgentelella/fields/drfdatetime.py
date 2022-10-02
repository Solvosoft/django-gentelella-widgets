from django import forms
from django.utils import formats
from datetime import datetime

class DateRangeTextWidget(forms.Widget):
    DATEFORMAT = '%m/%d/%y'
    format_key = 'DATE_INPUT_FORMATS'

    def get_date_format(self):
        return formats.get_format(self.format_key)[0]

    def format_date(self, value):
        dev = None
        for formattest in formats.get_format(self.format_key):
            try:
                dev = datetime.strptime(value, formattest)
            except ValueError as e:
                dev = None
            if dev is not None:
                break

        return dev

    def value_omitted_from_data(self, data, files, name):
        return name not in data

    def value_from_datadict(self, data, files, name):
        text = data.get(name)
        if not text:
            return

        dates = text.split('-')
        if len(dates) != 2:
            return
        dates[0] = self.format_date(dates[0].strip())
        dates[1] = self.format_date(dates[1].strip())

        return dates


class DateTimeRangeTextWidget(forms.Widget):
    DATEFORMAT = '%d/%m/%y HH:mm:ss'
    format_key = 'DATETIME_INPUT_FORMATS'

    def get_date_format(self):
        return formats.get_format(self.format_key)[0]

    def format_date(self, value):
        dev = None
        try:
            dev = datetime.strptime(value, self.get_date_format())
        except ValueError as e:
            pass
        return dev

    def value_omitted_from_data(self, data, files, name):
        return name not in data

    def value_from_datadict(self, data, files, name):
        text = data.get(name)
        if not text:
            return

        dates = text.split('-')
        if len(dates) != 2:
            return
        dates[0] = self.format_date(dates[0].strip())
        dates[1] = self.format_date(dates[1].strip())

        return dates
