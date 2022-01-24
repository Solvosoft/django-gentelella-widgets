from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.timezone import now


from djgentelella.forms.forms import CustomForm
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets import numberknobinput as knobwidget
from djgentelella.widgets.files import FileChunkedUpload
from djgentelella.widgets.storyline import UrlStoryLineInput
from djgentelella.widgets.timeline import UrlTimeLineInput


class ExampleForm(CustomForm):

    timeline = forms.CharField(widget=UrlTimeLineInput(
        attrs={"data-url": reverse_lazy('exampletimeline-list'), 'style': "height: 650px;",
        'frameborder':"0", "data-option_language": 'es'}))

    storyline = forms.CharField(widget=UrlStoryLineInput(
        attrs={"data-url": reverse_lazy('storylineoptions'),"height": 568, "width": 1112, 'style': "height: 650px; 'width': 100%"},
        csv='date,income,title,text,,\r\n1984-01-01,48720,,,,\r\n1985-01-01,49631,,,,\r\n1986-01-01,51388,,,,\r\n1987-01-01,52032,,,,\r\n1988-01-01,52432,,,,\r\n1989-01-01,53367,Reagan Boom Boom,"Two major underlying factors lead to a weakening U.S. economy—restrictive moves from the Federal Reserve designed to curb inflation, and a depreciating real estate market.",,\r\n1990-01-01,52684,Hello Downturn My Old Friend,"It’s all over in July, the last month of this period’s economic expansion. When Iraq invades Kuwait in August, oil prices skyrocket, and consumer confidence tanks. We head into a recession.",,\r\n1991-01-01,51145,,,,\r\n1992-01-01,50725,,,,\r\n1993-01-01,50478,Internet FTW,"Okay, technically the internet isn’t acting alone. Alongside this technology boon, the housing market starts to recover, due in part to lower interest rates and energy prices. People start making and spending money again.",,\r\n1994-01-01,51065,,,,\r\n1995-01-01,52664,,,,\r\n1996-01-01,53407,,,,\r\n1997-01-01,54506,,,,\r\n1998-01-01,56510,,,,view\r\n1999-01-01,57909,"Internet, You Have Failed Me","What’s the sound of countless investors sneaking away from Silicon Valley? A dot-com bubble burst. Investors see no path to revenue, dot-coms shut their doors, and the economy slumps. Goodbye, pets.com.",,\r\n2000-01-01,57790,,,,\r\n2001-01-01,56531,,,,\r\n2002-01-01,55871,,,,\r\n2003-01-01,55823,,,,\r\n2004-01-01,55629,,,,\r\n2005-01-01,56224,,,,\r\n2006-01-01,56663,,,,\r\n2007-01-01,57423,,,,\r\n2008-01-01,55376,"Housing Market, You Have REALLY Failed Me","A bubble bursts anew. This time the housing market is the culprit—shady banking practices lead to the subprime mortgage crisis, which combined with a market correction, causes the economy to tank.",,\r\n2009-01-01,54988,,,,\r\n2010-01-01,53568,,,,\r\n2011-01-01,52751,,,,\r\n2012-01-01,52666,Is it safe to come out yet?,"After a few years of economic recovery but general (understandable) wariness, consumers start to emerge from their bunkers. Economic indicators like employment rate and (trigger warning) housing prices see an uptick.",,\r\n2013-01-01,54525,,,,\r\n2014-01-01,53718,,,,\r\n2015-01-01,56516,,,,',
        options={
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
            }},
    ))

    your_name = forms.CharField(label='Your name', max_length=100, widget=genwidgets.TextInput)
    your_age = forms.IntegerField(widget=genwidgets.NumberInput(attrs={'min_value':2, 'max_value': 8}) )
    your_email = forms.EmailField(widget=genwidgets.EmailInput)
    your_email_mask = forms.EmailField(widget=genwidgets.EmailMaskInput)
    your_url = forms.URLField(widget=genwidgets.URLInput)
    your_pass = forms.CharField(widget=genwidgets.PasswordInput)

    your_file = forms.FileField(widget=genwidgets.FileInput)
    your_trunk = forms.FileField(widget=FileChunkedUpload)
    your_area = forms.CharField(widget=genwidgets.Textarea, max_length = 50)
    your_date = forms.DateField(widget=genwidgets.DateInput)
    your_datetime = forms.DateTimeField(widget=genwidgets.DateTimeInput)
    your_daterange = forms.CharField(widget=genwidgets.DateRangeInput)
   #
   #
    your_time = forms.TimeField(widget=genwidgets.TimeInput(attrs={'arrow': True}))
    your_check = forms.BooleanField(widget=genwidgets.CheckboxInput)
   #
   #
   #  your_nullboolean = forms.NullBooleanField(widget=genwidgets.NullBooleanSelect)
   #
   #  your_choice = forms.ChoiceField(choices=(
   #      ('enero', 'Enero'),
   #      ('febrero', 'Febrero'),
   #      ('marzo', 'abril')
   #  ), widget=genwidgets.Select)
   #
   #  your_test = forms.ChoiceField(choices=(
   #      ('enero', 'Enero'),
   #      ('febrero', 'Febrero'),
   #      ('marzo,abril', 'Marzo,Abril')
   #  ), widget=genwidgets.Select)
   #
   #  your_multiple = forms.ChoiceField(choices=(
   #      ('enero', 'Enero'),
   #      ('febrero', 'Febrero'),
   #      ('marzo,abril', 'Marzo,Abril')
   #  ), widget=genwidgets.SelectMultiple)
   #

    your_radio = forms.ChoiceField(choices=(
        ('enero', 'Enero'),
        ('febrero', 'Febrero'),
        ('marzo,abril', 'Marzo,Abril')
    ), widget=genwidgets.RadioHorizontalSelect)
    your_radio_vertical = forms.ChoiceField(choices=(
        ('enero', 'Enero'), ('febrero', 'Febrero'),
        ('marzo', 'Marzo'), ('abril','Abril')
    ), widget=genwidgets.RadioVerticalSelect)
   #
   #  your_checkbox = forms.ChoiceField(choices=(
   #      ('enero', 'Enero'),
   #      ('febrero', 'Febrero'),
   #      ('marzo,abril', 'Marzo,Abril')
   #  ), widget=genwidgets.CheckboxSelectMultiple)
   #
   #  #your_date = forms.DateField(widget=DateInput)
   #  #your_hiddendatime=forms.DateTimeField(widget=SplitHiddenDateTimeWidget)
   #  #your_SplitDateTimeWidget = forms.DateTimeField(widget=SplitDateTimeWidget)
   #
   #  your_selectdate = forms.DateTimeField(widget=genwidgets.SelectDateWidget)
   #
   #  def __init__(self, *args, **kwargs):
   #      kwargs['initial'] = {'your_name': "BINGO", 'your_age': 4,
   #                           'your_SplitDateTimeWidget': now(),
   #                           'your_selectdate': now(),
   #                           'your_time': now(), 'your_nullboolean': True}
   #
   #      super().__init__(*args, **kwargs)

    your_phone = forms.CharField(widget=genwidgets.PhoneNumberMaskInput)
    your_boolean = forms.BooleanField(widget=genwidgets.YesNoInput(attrs={'rel': ['#id_your_radio_vertical' ,'your_datemask', 'you_emailmask']}))
    your_datemask = forms.DateField(widget=genwidgets.DateMaskInput)
    your_datetimeMask  = forms.DateTimeField(widget=genwidgets.DateTimeMaskInput)
    you_emailmask = forms.EmailField(widget=genwidgets.EmailMaskInput)
    #your_daterangeinput = forms.CharField(widget=genwidgets.DateRangeInput)
    # your_knobinput = forms.IntegerField(widget=genwidgets.NumberKnobInput(
    #    attrs={ 'max_value':300, 'min_value': 200,
    #            'data-width': 100, 'data-height': 100,
    #            'data-displayPrevious': "true",
    #            'data-fgColor': "#26B99A",
    #            'data-cursor': "true",
    #            'data-thickness': '.3'
    #            } ))
    #
    # your_test = forms.ChoiceField(choices=(
    #     ('enero', 'Enero'),
    #     ('febrero', 'Febrero'),
    #     ('marzo,abril', 'Marzo,Abril')
    # ), widget=genwidgets.SelectMultipleAdd(
    #     attrs={'add_url': reverse_lazy('add_view_select')}
    # ))
    #
    # your_multiple = forms.ChoiceField(choices=(), widget=genwidgets.SelectWithAdd(
    #     attrs={'add_url': reverse_lazy('add_view_select')}))

    #your_wysiwyg = forms.CharField(widget=genwidgets.TextareaWysiwyg)

    # text_6 = forms.CharField(
    #     widget=ColorInput
    # )
    # text_7 = forms.CharField(
    #     widget=ColorInput
    # )


    your_age = forms.IntegerField(
        widget=knobwidget.NumberKnobInput(attrs={"value": 5, "data-min":1, "data-max":10})
    )


def home(request):
    form = ExampleForm()
    if request.method == 'POST':
        form  = ExampleForm(request.POST)
        form.is_valid()
    return render(request, 'gentelella/index.html', {'form': form})


@login_required
def logeado(request):
    return HttpResponse("Wiii")


def add_view_select(request):
    if request.method == 'POST':
        return JsonResponse({'ok': True, 'id': 2, 'text': 'Data example'})
        return JsonResponse({'ok': False,
                             'title': "Esto no dice nada",
                             'message': 'Esto es un errror'})
    data = {
        'ok':  True,
        'title': 'Formulario de ejemplo',
        'message': """
        <form method="post" action="/add_view_select">
            <textarea name="description" > </textarea>
            <input type="text" name="name" />
            <select name="bingo">
               <option value="Nada">Nada</option><option value="otro">Otro</option>
            </select>
        </form>
        """
    }
    return JsonResponse(data)