
from django import forms

from djgentelella.widgets.core import *
# "'<tr%(html_class_attr)s><th>%(label)s</th><td>%(errors)s%(field)s%(help_text)s</td></tr>'"
class CustomForm(forms.Form):

    def as_plain(self):
        "Returns this form rendered as HTML <tr>s -- excluding the <table></table>."

        return self._html_output(
            normal_row='<div %(html_class_attr)s >%(label)s%(errors)s%(field)s%(help_text)s</div>',
            error_row='%s',
            row_ender=' ',
            help_text_html='<br /><span class="helptext">%s</span>',
            errors_on_separate_row=False)

    def as_inline(self):
            "Return this form rendered as HTML <tr>s -- excluding the <table></table>."
            return self._html_output(
                normal_row='<div class="form-group"><span class="">%(label)s</span> %(field)s%(help_text)s</div>',
                error_row='%s',
                row_ender='</div>',
                help_text_html=' <span class="helptext">%s</span>',
                errors_on_separate_row=False,
            )

    def as_horizontal(self):
            "Return this form rendered as HTML <tr>s -- excluding the <table></table>."
            return self._html_output(
                normal_row='<div class="form-group row"><span class="col-sm-3">%(label)s</span> <div class="col-sm-9">%(field)s%(help_text)s</div></div>',
                error_row='%s',
                row_ender='</div>',
                help_text_html=' <span class="helptext">%s</span>',
                errors_on_separate_row=False,
            )

class NameForm(CustomForm):
    FAVORITE_COLORS_CHOICES = [
        ('blue', 'Blue'),
        ('green', 'Green'),
        ('black', 'Black'),
    ]
    FAVORITE_NUMBERS_CHOICES = [
        ('one', 'One'),
        ('two', 'Two'),
        ('three', 'Three'),
    ]

    time_input = forms.TimeField(widget=TimeInput,required=True)
    date_input = forms.DateField(widget=DateInput)
    daterange_input = forms.DateField(widget=DateRangeInput)
    datetime_input = forms.DateField(widget=DateTimeInput)
    daterangetime_input = forms.DateField(widget=DateRangeTimeInput)
    username = forms.CharField(widget=TextInput,required=True)
    text_area = forms.CharField(widget=Textarea,required=True)
    password = forms.CharField(widget=PasswordInput,required=True)

    phone = forms.CharField(widget=PhoneNumberMaskInput)
    email_input_mask = forms.CharField(widget=EmailMaskInput)
    datetime_input_mask = forms.DateField(widget=DateTimeMaskInput)
    date_input_mask = forms.DateField(widget=DateMaskInput)
    boolean = forms.BooleanField(widget=CheckboxInput)
    checkbox_favorite_colors = forms.MultipleChoiceField(
            required=False,
            widget=SelectMultiple,
            choices=FAVORITE_COLORS_CHOICES,
        )
    radio_favorite_numbers = forms.ChoiceField(
        required=False,
        widget=Select,
        choices=FAVORITE_NUMBERS_CHOICES,
    )