import mimetypes
import posixpath
from pathlib import Path

from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponseNotModified, FileResponse
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.http import http_date
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.static import directory_index
from django.views.static import was_modified_since

from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets import numberknobinput as knobwidget
from djgentelella.widgets.files import FileChunkedUpload


@csrf_exempt
def serve_static(request, path, show_indexes=False):
    try:
        normalized_path = posixpath.normpath(path).lstrip('/')
        fullpath = finders.find(normalized_path)

        # Convert fullpath to a Path object
        fullpath = Path(fullpath)

        if fullpath.is_dir():
            if show_indexes:
                return directory_index(path, fullpath)
            raise Http404(_("Directory indexes are not allowed here."))

        if not fullpath.exists():
            raise Http404(_("“%(path)s” does not exist") % {"path": fullpath})

        # Respect the If-Modified-Since header.
        statobj = fullpath.stat()
        if not was_modified_since(
            request.META.get("HTTP_IF_MODIFIED_SINCE"), statobj.st_mtime
        ):
            return HttpResponseNotModified()

        content_type, encoding = mimetypes.guess_type(str(fullpath))
        content_type = content_type or "application/octet-stream"

        response = FileResponse(fullpath.open("rb"), content_type=content_type)
        response.headers["Last-Modified"] = http_date(statobj.st_mtime)
        if encoding:
            response.headers["Content-Encoding"] = encoding

        return response
    except Exception as e:
        raise Http404()


class ExampleForm(GTForm):
    photo_record = forms.FileField(label='Your photo',
                                   widget=genwidgets.ImageRecordInput)
    video_record = forms.FileField(label='Your video',
                                   widget=genwidgets.VideoRecordInput)
    your_name = forms.CharField(label='Your name', max_length=100,
                                widget=genwidgets.TextInput)
    your_age = forms.IntegerField(
        widget=genwidgets.NumberInput(attrs={'min_value': 2, 'max_value': 8}))
    your_email = forms.EmailField(widget=genwidgets.EmailInput)
    your_email_mask = forms.EmailField(widget=genwidgets.EmailMaskInput)
    your_url = forms.URLField(widget=genwidgets.URLInput)
    your_pass = forms.CharField(widget=genwidgets.PasswordInput)

    your_file = forms.FileField(widget=genwidgets.FileInput)
    your_trunk = forms.FileField(widget=FileChunkedUpload)
    your_area = forms.CharField(widget=genwidgets.Textarea, max_length=50)
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
        ('marzo', 'Marzo'), ('abril', 'Abril')
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
    your_boolean = forms.BooleanField(
        widget=genwidgets.YesNoInput(attrs={
            'rel': ['#id_your_radio_vertical', 'your_datemask', 'you_emailmask']}))
    your_datemask = forms.DateField(widget=genwidgets.DateMaskInput)
    your_datetimeMask = forms.DateTimeField(widget=genwidgets.DateTimeMaskInput)
    you_emailmask = forms.EmailField(widget=genwidgets.EmailMaskInput)
    # your_daterangeinput = forms.CharField(widget=genwidgets.DateRangeInput)
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

    # your_wysiwyg = forms.CharField(widget=genwidgets.TextareaWysiwyg)

    # text_6 = forms.CharField(
    #     widget=ColorInput
    # )
    # text_7 = forms.CharField(
    #     widget=ColorInput
    # )

    your_age = forms.IntegerField(
        widget=knobwidget.NumberKnobInput(
            attrs={"value": 5, "data-min": 1, "data-max": 10}))


def home(request):
    form = ExampleForm()
    if request.method == 'POST':
        form = ExampleForm(request.POST)
        form.is_valid()
        # print(form.cleaned_data)
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
        'ok': True,
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
