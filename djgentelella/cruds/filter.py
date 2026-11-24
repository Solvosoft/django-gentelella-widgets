from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.forms.models import modelform_factory


class FormFilter:
    form = None

    def __init__(self, request, form=None):
        if form:
            self.form = form
        self.request = request
        self.form_instance = self.form(request.GET)
        for key in self.form_instance.fields:
            self.form_instance.fields[key].required = False
        self.form_instance.is_valid()
        self.form_instance._errors = {}

    def get_cleaned_fields(self):
        values = {}
        for value in self.form_instance.cleaned_data:
            rq_value = self.request.GET.get(value, '')
            if value and rq_value:
                data_value = self.form_instance.cleaned_data[value]
                # isinstance, not type(...) == QuerySet: a model with a custom
                # manager hands back a QuerySet subclass, and the exact-type
                # check skipped it, so its multiple-choice filters never got
                # the "__in" suffix and matched nothing.
                if isinstance(data_value, models.QuerySet):
                    if data_value.count() == 1:
                        data_value = data_value.first()
                    elif '__in' not in value:
                        value = value + '__in'
                values[value] = data_value
        return values

    def render(self):
        return self.form_instance

    def get_filter(self, queryset):
        clean_value = self.get_cleaned_fields()
        if clean_value:
            queryset = queryset.filter(**clean_value)
        return queryset

    def get_build_param(self, value, data, params):
        if isinstance(data, models.base.Model):
            data = str(data.pk)
        params.append('%s=%s' % (value, str(data)))
        return params

    def get_params(self, exclude=[]):
        params = []
        for value in self.form_instance.cleaned_data:
            if value in exclude:
                continue
            rq_value = self.request.GET.get(value, '')
            if rq_value:
                data = self.form_instance.cleaned_data[value]
                if isinstance(data, models.QuerySet):
                    for q in data:
                        params = self.get_build_param(value, q, params)
                else:
                    params = self.get_build_param(value, data, params)
        return params

    def hide(self, hidden):
        """Drop the fields over a ``hidden`` column (``price``,
        ``price__gte``...): they neither show nor filter."""
        for name in list(self.form_instance.fields):
            if name.split('__')[0] in hidden:
                del self.form_instance.fields[name]
                self.form_instance.cleaned_data.pop(name, None)


def get_filters(model, list_filter, request, hidden=()):
    """The filters of ``list_filter`` (model field names or ``FormFilter``
    classes) for ``request``, without those over a ``hidden`` column: a
    filter on a column the user cannot see would tell its values apart."""
    fields = []
    forms = []
    for field in list_filter:
        if isinstance(field, str):
            # this is a model field
            if field in hidden:
                continue
            try:
                model._meta.get_field(field)
                fields.append(field)
            except FieldDoesNotExist:
                pass
        else:
            filter_form = field(request)
            if hidden:
                filter_form.hide(hidden)
            forms.append(filter_form)

    if fields:
        form = modelform_factory(model, fields=fields)
        forms.insert(0, FormFilter(request, form=form))

    return forms
