from django import forms

# "'<tr%(html_class_attr)s><th>%(label)s</th><td>%(errors)s%(field)s%(help_text)s</td></tr>'"
from django.forms import BaseFormSet, HiddenInput
from django.forms.formsets import DELETION_FIELD_NAME
from django.utils.safestring import mark_safe
from django.forms import BaseModelFormSet

class GTForm(forms.Form):
    """
    Append the next render methods to forms
    """
    exposed_method = ('as_plain', 'as_inline', 'as_horizontal')

    def as_plain(self):
        "Returns this form rendered as HTML <tr>s -- excluding the <table></table>."

        return self._html_output(
            normal_row='<div class="as_plain"><div %(html_class_attr)s >%(label)s%(errors)s%(field)s%(help_text)s</div></div>',
            error_row='%s',
            row_ender=' ',
            help_text_html='<br /><span class="helptext">%s</span>',
            errors_on_separate_row=False)

    def as_inline(self):
            "Return this form rendered as HTML <tr>s -- excluding the <table></table>."
            return self._html_output(
                normal_row='<div class="form-group"><span class="">%(label)s</span> %(errors)s%(field)s%(help_text)s</div>',
                error_row='%s',
                row_ender='</div>',
                help_text_html=' <span class="helptext">%s</span>',
                errors_on_separate_row=False,
            )

    def as_horizontal(self):
            "Return this form rendered as HTML <tr>s -- excluding the <table></table>."
            return self._html_output(
                normal_row='<div class="form-group row"><span class="col-sm-3">%(label)s</span> <div class="col-sm-9 col-xs-12">%(errors)s%(field)s%(help_text)s</div></div>',
                error_row='%s',
                row_ender='</div>',
                help_text_html=' <span class="helptext">%s</span>',
                errors_on_separate_row=False,
            )

CustomForm=GTForm

class BaseFormset:
    def as_plain(self):
        forms = ' '.join(form.as_plain() for form in self)
        return mark_safe(str(self.management_form) + '\n' + forms)

    def as_inline(self):
        forms = ' '.join(form.as_inline() for form in self)
        return mark_safe(str(self.management_form) + '\n' + forms)

    def as_horizontal(self):
        forms = ' '.join(form.as_horizontal() for form in self)
        return mark_safe(str(self.management_form) + '\n' + forms)


class GTFormSet(BaseFormSet, BaseFormset):
    ordering_widget = HiddenInput

    def add_fields(self, form, index):
        super().add_fields(form, index)
        if self.can_delete:
            form.fields[DELETION_FIELD_NAME].widget.attrs['class'] = 'hidden'
            form.fields[DELETION_FIELD_NAME].label = ''


class GTBaseModelFormSet(BaseModelFormSet):
    ordering_widget = HiddenInput

    def add_fields(self, form, index):
        super().add_fields(form, index)
        if self.can_delete:
            form.fields[DELETION_FIELD_NAME].widget.attrs['class'] = 'hidden'
            form.fields[DELETION_FIELD_NAME].label = ''