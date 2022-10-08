from djgentelella.fields import tree
from djgentelella.forms.forms import CustomForm
from djgentelella.widgets import core
from djgentelella.widgets import trees


def get_field_widget(widget_type):
    widget = None
    name = type(widget_type.widget).__name__
    if hasattr(core, name):
        params = {
            'attrs': widget_type.widget.attrs
        }
        if hasattr(widget_type.widget, 'choices'):
            params['choices'] = getattr(widget_type.widget, 'choices')
        widget = getattr(core, name)(**params)

    return widget

def decore_treenode(form_instance, field):
    if type(form_instance.fields[field]) == 'TreeNodeChoiceField':
        form_instance.fields[field] = tree.GentelellaTreeNodeChoiceField(
            queryset=form_instance.fields[field].queryset,
            required=form_instance.fields[field].required,
            widget=trees.TreeSelect(
                attrs=form_instance.fields[field].widget.attrs,
                choices=form_instance.fields[field].widget.choices)
        )
    elif type(form_instance.fields[field]) =='TreeNodeMultipleChoiceField':
        form_instance.fields[field] = tree.GentelellaTreeNodeMultipleChoiceField(
            queryset=form_instance.fields[field].queryset,
            required=form_instance.fields[field].required,
            widget=trees.TreeSelectMultiple(
                attrs=form_instance.fields[field].widget.attrs,
                choices=form_instance.fields[field].widget.choices)
        )

def _form_instance(fnc, instance):
    def new_fnc():
        return fnc(instance)
    return new_fnc

def decore_form_instance(form_instance, exclude=()):
    for field in form_instance.fields:
        if field in exclude:
            continue
        if type(form_instance.fields[field]) in ['TreeNodeChoiceField',
                                                 'TreeNodeMultipleChoiceField']:
            decore_treenode(form_instance, field)
        else:
            widget = get_field_widget(form_instance.fields[field])
            if widget:
                form_instance.fields[field].widget = widget
    for method in CustomForm.exposed_method:
        setattr(form_instance, method,
                _form_instance(getattr(CustomForm, method),form_instance))
    form_instance.is_customized = True
    return form_instance