from djgentelella.widgets import core as genwidgets
from django import forms
from django.forms import BaseFormSet, HiddenInput
from django.forms import BaseModelFormSet
from django.forms.formsets import DELETION_FIELD_NAME
from django.utils.safestring import mark_safe

from djgentelella.models import GTDbForm, GTDbField, GTStatus, GTActionsStep, GTStep, \
    GTFlow, GTSkipCondition


class GTForm(forms.Form):
    """
    GTForm is the basis of form management, it does the work of django `forms.Form`, including enhancements and boostrap rendering, so it should be inherited from this form, rather than `forms.Form`.

    Example of use:

    .. code:: python

         from djgentelella.forms.forms import GTForm
         class MyForm(GTForm):
              myfield = forms.TextField()

    Using with forms.ModelForm

    .. code:: python

         from djgentelella.forms.forms import GTForm
         class MyForm(GTForm, forms.ModelForm):
              myfield = forms.TextField()
              class Meta:
                model = MyModel

    Creating an instance and specify how render it.

    .. code:: python

        myform = myGTForm(render_type='as_inline', ... )

    """
    exposed_method = ('as_plain', 'as_inline', 'as_horizontal')
    default_render_type = None
    template_name_plain = 'forms/as_plain.html'
    template_name_inline = 'forms/as_inline.html'
    template_name_horizontal = 'forms/as_horizontal.html'
    template_name_grid = 'forms/as_grid.html'
    grid_representation = None

    def __init__(self, *args, **kwargs):
        render_type = self.default_render_type if self.default_render_type is not None else 'as_horizontal'
        if 'render_type' in kwargs and hasattr(self, kwargs['render_type']):
            render_type = kwargs.pop('render_type')

        super().__init__(*args, **kwargs)

        match render_type:
            case 'as_table':
                self.renderer.form_template_name = self.template_name_table
            case 'as_ul':
                self.renderer.form_template_name = self.template_name_ul
            case 'as_p':
                self.renderer.form_template_name = self.template_name_p
            case 'as_div':
                self.renderer.form_template_name = self.template_name_div
            case 'as_horizontal':
                self.renderer.form_template_name = self.template_name_horizontal
            case 'as_inline':
                self.renderer.form_template_name = self.template_name_inline
            case 'as_plain':
                self.renderer.form_template_name = self.template_name_plain
            case 'as_grid':
                self.renderer.form_template_name = self.template_name_grid
            case _:
                self.renderer.form_template_name = self.template_name_horizontal

    @property
    def grid(self):
        """
        Example of return structure:

        .. code:: python

            [
                [ [forms.Field],[], [] ],
                [ [], [] ],
            ]

        """
        fields = []
        dic_fields = {}
        for name, bf in self._bound_items():
            if not bf.is_hidden:
                fields.append(bf)
                dic_fields[name] = bf

        if self.grid_representation is not None:
            grid = []  # self.grid_representation
            for row in self.grid_representation:
                col_list = []
                for col in row:
                    row_list = []
                    for field in col:
                        if field in dic_fields and dic_fields[field]:
                            row_list.append(dic_fields[field])
                        else:
                            if hasattr(self, field):
                                row_list.append(getattr(self, field)())
                    col_list.append(row_list)
                grid.append(col_list)
            return grid
        return [[fields]]

    def as_plain(self):
        "Returns this form rendered as HTML using as_plain bootstrap approach."
        if hasattr(self, '_html_output'):
            return self._html_output(
                normal_row='<div class="as_plain"><div %(html_class_attr)s ' +
                           '>%(label)s%(errors)s%(field)s%(help_text)s</div></div>',
                error_row='%s',
                row_ender=' ',
                help_text_html='<br /><span class="helptext">%s</span>',
                errors_on_separate_row=False)
        return self.render(self.template_name_plain)

    def as_inline(self):
        "Return this form rendered as HTML using as_inline bootstrap approach."
        if hasattr(self, '_html_output'):
            return self._html_output(
                normal_row='<div class="mb-4"><span class="">%(label)s</span>' +
                           ' %(errors)s%(field)s%(help_text)s</div>',
                error_row='%s',
                row_ender='</div>',
                help_text_html=' <span class="helptext">%s</span>',
                errors_on_separate_row=False,
            )
        return self.render(self.template_name_inline)

    def as_horizontal(self):
        "Return this form rendered as HTML using as_horizontal bootstrap approach."
        if hasattr(self, '_html_output'):
            return self._html_output(
                normal_row='<div class="form-group row"><span class="col-sm-3">' +
                           '%(label)s</span> <div class="col-sm-9 " ' +
                           '>%(errors)s%(field)s%(help_text)s</div></div>',
                error_row='%s',
                row_ender='</div>',
                help_text_html=' <span class="helptext">%s</span>',
                errors_on_separate_row=False,
            )
        return self.render(self.template_name_horizontal)

    def as_grid(self):
        """
        Allow you to arrange the form fields in rows and cols,
        When you use this render needs to fill  `grid_representation` attribute in your form
        Return this form rendered as HTML using grid bootstrap approach.,

        .. code:: python

            grid_representation=[
                [ ['key'],[], [] ],
                [ [], [] ],
            ]

        """
        return self.render(self.template_name_grid)

    def closediv(self):
        return "</div>"


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
    """
    This class Allow to manage FormSet using GTForm and Widgets,
    provide an implementation to integrate with django formset system.
    """

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


class GTDbFormSet(forms.ModelForm):
    class Meta:
        model = GTDbForm
        fields = ['token', 'prefix', 'representation_list', 'template_name']
        widgets = {
            'token': genwidgets.TextInput,
            'prefix': genwidgets.TextInput,
            'representation_list': genwidgets.Select,
            'template_name': genwidgets.TextInput,
        }

class GTDbFieldForm(forms.ModelForm):
    class Meta:
        model = GTDbField
        fields = ['form', 'name', 'label', 'required', 'label_suffix', 'help_text', 'disabled', 'extra_attr', 'extra_kwarg', 'order']
        widgets = {
            'form': genwidgets.Select,
            'name': genwidgets.TextInput,
            'label': genwidgets.TextInput,
            'label_suffix': genwidgets.TextInput,
            'help_text': genwidgets.TextInput,
            'disabled': genwidgets.CheckboxInput,
            'extra_attr': genwidgets.Textarea,
            'extra_kwarg': genwidgets.Textarea,
            'order': genwidgets.NumberInput,
        }

class GTStatusForm(forms.ModelForm):
    class Meta:
        model = GTStatus
        fields = ['name', 'description']
        widgets = {
            'name': genwidgets.TextInput,
            'description': genwidgets.Textarea,
        }

class GTActionsStepForm(forms.ModelForm):
    class Meta:
        model = GTActionsStep
        fields = ['name', 'description', 'content_type', 'object_id']
        widgets = {
            'name': genwidgets.TextInput,
            'description': genwidgets.Textarea,
        }

class GTStepForm(forms.ModelForm):
    class Meta:
        model = GTStep
        fields = ['name', 'order', 'status_id', 'form', 'post_action', 'pre_action']
        widgets = {
            'name': genwidgets.TextInput,
            'status_id': genwidgets.SelectMultiple,
            'order': genwidgets.NumberInput,
            'form': genwidgets.SelectMultiple,
            'post_action': genwidgets.Select,
            'pre_action': genwidgets.Select,
        }

class GTFlowForm(forms.ModelForm):
    class Meta:
        model = GTFlow
        fields = ['name', 'description', 'step']
        widgets = {
            'name': genwidgets.TextInput,
            'description': genwidgets.Textarea,
            'step': genwidgets.Select,
        }

class GTSkipConditionForm(forms.ModelForm):
    class Meta:
        model = GTSkipCondition
        fields = ['step_id', 'condition_field', 'condition_value', 'skip_to_step']
        widgets = {
            'step_id': genwidgets.Select,
            'condition_field': genwidgets.TextInput,
            'condition_value': genwidgets.TextInput,
            'skip_to_step': genwidgets.Select,
        }
