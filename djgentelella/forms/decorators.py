from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core


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


def _form_instance(fnc, instance):
    def new_fnc():
        return fnc(instance)

    return new_fnc


def decore_form_instance(form_instance, exclude=()):
    for field in form_instance.fields:
        if field in exclude:
            continue
        widget = get_field_widget(form_instance.fields[field])
        if widget:
            form_instance.fields[field].widget = widget
    for method in GTForm.exposed_method:
        setattr(form_instance, method,
                _form_instance(getattr(GTForm, method), form_instance))
    form_instance.is_customized = True
    return form_instance
