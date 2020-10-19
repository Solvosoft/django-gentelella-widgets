from datetime import datetime,date
from django.forms import MultiWidget
from .core import Select,TextInput

def list_countries():
    return [{"name": "Belize", "code": "BZ"},{"name": "Brazil", "code": "BR"},
            {"name": "Canada", "code": "CA"},{"name": "Chile", "code": "CL"},
            {"name": "China", "code": "CN"},{"name": "Costa Rica", "code": "CR"},
            {"name": "Cuba", "code": "CU"},{"name": "Ecuador", "code": "EC"},
            {"name": "El Salvador", "code": "SV"},{"name": "Honduras", "code": "HN"},
            {"name": "Japan", "code": "JP"},{"name": "Nicaragua", "code": "NI"},
            {"name": "United Kingdom", "code": "GB"},{"name": "United States", "code": "US"},
            {"name": "Uruguay", "code": "UY"},{"name": "Venezuela", "code": "VE"},
        ]
class SplitDate(MultiWidget):

    template_name = "gentelella/widgets/splitdate.html"

    def __init__(self, attrs=None):
        days = [(day, day) for day in range(1, 32)]
        months = [(month, month) for month in range(1, 13)]
        years = [(year, year) for year in range(1950, datetime.now().year+50)]

        widgets = [
            Select(attrs=attrs, choices=days),
            Select(attrs=attrs, choices=months),
            Select(attrs=attrs, choices=years),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if isinstance(value, date):
            return [value.day, value.month, value.year]
        elif isinstance(value, str):
            year, month, day = value.split('-')
            return [day, month, year]
        return [None, None, None]

    def value_from_datadict(self, data, files, name):
        day, month, year = super().value_from_datadict(data, files, name)
        return '{}-{}-{}'.format(year, month, day)



class PhoneNumberMultiWidget(MultiWidget):
    template_name = "gentelella/widgets/phonenumber_multiwidget.html"

    def __init__(self, attrs=None):
        numbers = [('('+str(number)+')', '+('+str(number)+')') for number in range(1, 1000)]
        widget = (
            Select(attrs=attrs, choices=numbers),
            TextInput(attrs={'placeholder': 'insert the phone number'}),
        )
        super(PhoneNumberMultiWidget, self).__init__(widget, attrs)

    def decompress(self, value):
        if value:
            number = value
            return value.split(" ")
        return [None, None]

       
    def value_from_datadict(self, data, files, name):
        datalist = [
            widget.value_from_datadict(data, files, name + '_%s' % i)
            for i, widget in enumerate(self.widgets)]
        try:
            data = datalist[0]+" "+datalist[1]
        except ValueError:
            return ''
        else:
            return data
    
class PassportWidget(MultiWidget):
    template_name = "gentelella/widgets/phonenumber_multiwidget.html"
    def __init__(self, attrs=None,choices=()):
        countries= [(country['name']+'('+country['code']+')', country['name']+'('+country['code']+')') for country in list_countries()]

        widget = (
            Select(attrs=attrs, choices=countries),
            TextInput(attrs={'placeholder': 'insert the passport digits'}),
        )
        super(PassportWidget, self).__init__(widget, attrs)

    def decompress(self, value):
        if value:
            number = value
            return value.split(", ")
        return [None, None]
 
    def value_from_datadict(self, data, files, name):
        datalist = [
            widget.value_from_datadict(data, files, name + '_%s' % i)
            for i, widget in enumerate(self.widgets)]
        try:
            data = datalist[0]+", "+datalist[1]
        except ValueError:
            return ''
        else:
            return data

