from django import forms
# "'<tr%(html_class_attr)s><th>%(label)s</th><td>%(errors)s%(field)s%(help_text)s</td></tr>'"
from django.forms import BaseFormSet, HiddenInput
from django.forms import BaseModelFormSet
from django.forms.formsets import DELETION_FIELD_NAME
from django.utils.safestring import mark_safe


class BaseRepresentation:

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
            normal_row='<div class="mb-4"><span class="">%(label)s</span> %(errors)s%(field)s%(help_text)s</div>',
            error_row='%s',
            row_ender='</div>',
            help_text_html=' <span class="helptext">%s</span>',
            errors_on_separate_row=False,
        )


    def as_horizontal(self):
        "Return this form rendered as HTML <tr>s -- excluding the <table></table>."
        return self._html_output(
            normal_row='<div class="form-group row"><span class="col-sm-3">%(label)s</span> <div class="col-sm-9 " >%(errors)s%(field)s%(help_text)s</div></div>',
            error_row='%s',
            row_ender='</div>',
            help_text_html=' <span class="helptext">%s</span>',
            errors_on_separate_row=False,
        )


class GTForm(forms.Form, BaseRepresentation):
    """
    Append the next render methods to forms
    """
    exposed_method = ('as_plain', 'as_inline', 'as_horizontal')

CustomForm = GTForm

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
            form.fields[DELETION_FIELD_NAME].widget.attrs['class'] = 'invisible'
            form.fields[DELETION_FIELD_NAME].label = ''


class GTBaseModelFormSet(BaseModelFormSet):
    ordering_widget = HiddenInput

    def add_fields(self, form, index):
        super().add_fields(form, index)
        if self.can_delete:
            form.fields[DELETION_FIELD_NAME].widget.attrs['class'] = 'invisible'
            form.fields[DELETION_FIELD_NAME].label = ''


class BaseFromModel(BaseRepresentation):

    def add_new_item(self, GTDbField, form, name, count):
        self.gtdb_fields.append(GTDbField.objects.create(
            form=form, name=name,
            label=self.fields[name].label,
            required=self.fields[name].required,
            label_suffix=self.fields[name].label_suffix,
            help_text=self.fields[name].help_text,
            disabled=self.fields[name].disabled,
            order=count
        ))

    def update_field(self, name, dbfield):
        self.fields[name].label = dbfield.label
        self.fields[name].required = dbfield.required
        self.fields[name].label_suffix = dbfield.label_suffix
        self.fields[name].help_text = dbfield.help_text
        self.fields[name].disabled = dbfield.disabled

    def get_gtdbform_from_db(self, token):
        from djgentelella.models import GTDbForm, GTDbField
        form = GTDbForm.objects.filter(token=token).first()
        self.gtdb_fields = []
        self.delete_field = []
        count = 0
        if form is None:
            form=GTDbForm.objects.create(token=token, prefix=self.prefix)
            for name in self.fields:
                self.add_new_item(GTDbField, form, name, count)
                count += 1
        else:
            self.gtdb_fields = list(form.gtdbfield_set.all().order_by('order'))
            count=len(self.gtdb_fields)
        keys = list(self.fields.keys())
        for dbfield in self.gtdb_fields:
            if dbfield.name in keys:
                keys.remove(dbfield.name)
                self.update_field(dbfield.name, dbfield)
            else:
                self.delete_field.append(dbfield.pk)

        for name in keys:
            self.add_new_item(GTDbField, form, name, count)
            count += 1

        if self.delete_field:
            GTDbForm.objects.filter(pk__in=self.delete_field).delete()

    def load_form_personalization_data(self):
        if self.token is None:
            self.token = self.__class__.__name__
        form = self.get_gtdbform_from_db(self.token)


class GTModelForm(forms.ModelForm, BaseFromModel):
    token = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_form_personalization_data()


class GTMForm(forms.Form, BaseFromModel):
    token = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_form_personalization_data()

