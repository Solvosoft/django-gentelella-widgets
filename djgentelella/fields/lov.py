import weakref

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Model
from django.utils.translation import gettext_lazy as _

from djgentelella.lov import get_lov
from djgentelella.widgets.lov import LOVSelect, LOVSelectMultiple


def _parent_value(value):
    if isinstance(value, Model):
        return value.pk
    if isinstance(value, (list, tuple)):
        return ','.join(str(_parent_value(item)) for item in value)
    return value


class LOVFieldMixin:
    default_error_messages = {
        'invalid_choice': _('Select a valid choice. %(value)s is not one of the '
                            'available choices.'),
    }
    widget_class = LOVSelect

    def __init__(self, lov, *, parents=None, coerce=None, widget=None, **kwargs):
        """``lov`` is the registered name; ``parents`` maps a parameter of the
        LOV to the form field that holds it when the names differ."""
        self.lov_name = lov
        self.parents = dict(parents or {})
        self.coerce = coerce
        if widget is None:
            widget = self.widget_class(lov, parents=self.parents)
        elif isinstance(widget, type):
            widget = widget(lov, parents=self.parents)
        self._form_ref = None
        super().__init__(widget=widget, **kwargs)

    @property
    def lov(self):
        return get_lov(self.lov_name)

    def get_bound_field(self, form, field_name):
        # Every form deep-copies its fields, so this state is per form.
        self._form_ref = weakref.ref(form)
        self.widget.lov_prefix = form.prefix or ''
        self.widget.lov_parent_values = self.parent_values()
        self.widget.lov_request = getattr(form, 'request', None)
        return super().get_bound_field(form, field_name)

    def _form(self):
        return self._form_ref() if self._form_ref is not None else None

    def parent_values(self):
        """``{lov parameter: value}`` from the data (or initial) of the form."""
        form = self._form()
        values = {}
        if form is None:
            return values
        for param in self.lov.depends_on:
            name = self.parents.get(param, param)
            if form.is_bound:
                field = form.fields.get(name)
                key = form.add_prefix(name)
                if field is not None:
                    value = field.widget.value_from_datadict(
                        form.data, form.files, key)
                else:
                    value = form.data.get(key)
            else:
                field = form.fields.get(name)
                value = (form.get_initial_for_field(field, name)
                         if field is not None else form.initial.get(name))
            values[param] = _parent_value(value)
        return values

    def valid_value(self, value):
        form = self._form()
        return self.lov.contains(value, self.parent_values(),
                                 getattr(form, 'request', None))

    def _coerce(self, value):
        if self.coerce is None or value in ('', None):
            return value
        try:
            return self.coerce(value)
        except (ValueError, TypeError, ValidationError):
            raise ValidationError(self.error_messages['invalid_choice'],
                                  code='invalid_choice', params={'value': value})


class LOVChoiceField(LOVFieldMixin, forms.Field):
    """A value of the LOV ``lov``, checked against the LOV computed with the
    parent values that came with the form: a canton that does not belong to
    the chosen province is rejected."""

    def to_python(self, value):
        if value in self.empty_values:
            return ''
        return str(value)

    def validate(self, value):
        super().validate(value)
        if value and not self.valid_value(value):
            raise ValidationError(self.error_messages['invalid_choice'],
                                  code='invalid_choice', params={'value': value})

    def clean(self, value):
        return self._coerce(super().clean(value))


class LOVMultipleChoiceField(LOVFieldMixin, forms.Field):
    widget_class = LOVSelectMultiple
    default_error_messages = {
        'invalid_list': _('Enter a list of values.'),
    }

    def to_python(self, value):
        if not value:
            return []
        if not isinstance(value, (list, tuple)):
            raise ValidationError(self.error_messages['invalid_list'],
                                  code='invalid_list')
        return [str(item) for item in value]

    def validate(self, value):
        if self.required and not value:
            raise ValidationError(self.error_messages['required'], code='required')
        for item in value:
            if not self.valid_value(item):
                raise ValidationError(self.error_messages['invalid_choice'],
                                      code='invalid_choice', params={'value': item})

    def clean(self, value):
        return [self._coerce(item) for item in super().clean(value)]

    def has_changed(self, initial, data):
        initial = [str(item) for item in initial or []]
        data = [str(item) for item in data or []]
        return set(initial) != set(data)
