from django import forms
from django.db import models

class GTForeignKey(models.ForeignKey):

    def __init__(self, *args, **kwargs):
        self.key_name = kwargs.pop('key_name') if 'key_name' in kwargs else None
        self.key_value = kwargs.pop('key_value') if 'key_value' in kwargs else None
        self.extra_filters = kwargs.pop('extra_filters') if 'extra_filters' in kwargs else {}
        return super().__init__(*args, **kwargs)

    def formfield(self, *, using=None, **kwargs):
        if isinstance(self.remote_field.model, str):
            raise ValueError("Cannot create form field for %r yet, because "
                             "its related model %r has not been loaded yet" %
                             (self.name, self.remote_field.model))

        queryset = self.remote_field.model._default_manager.using(using)
        if self.key_name:
            queryset = queryset.filter(**{
                self.key_name:self.key_value,
                **self.extra_filters
            })
        return super().formfield(**{
            'form_class': forms.ModelChoiceField,
            'queryset': queryset,
            'to_field_name': self.remote_field.field_name,
            **kwargs,
        })

class GTOneToOneField(GTForeignKey, models.OneToOneField):
    pass

class GTManyToManyField(models.ManyToManyField):

    def __init__(self, *args, **kwargs):
        self.key_name = kwargs.pop('key_name') if 'key_name' in kwargs else None
        self.key_value = kwargs.pop('key_value') if 'key_value' in kwargs else None
        self.extra_filters = kwargs.pop('extra_filters') if 'extra_filters' in kwargs else {}

        return super().__init__(*args, **kwargs)


    def formfield(self, *, using=None, **kwargs):

        queryset = self.remote_field.model._default_manager.using(using)
        if self.key_name:
            queryset = queryset.filter(**{
                self.key_name:self.key_value,
                **self.extra_filters
            })
        defaults = {
            'form_class': forms.ModelMultipleChoiceField,
            'queryset': queryset,
            **kwargs,
        }
        # If initial is passed in, it's a list of related objects, but the
        # MultipleChoiceField takes a list of IDs.
        if defaults.get('initial') is not None:
            initial = defaults['initial']
            if callable(initial):
                initial = initial()
            defaults['initial'] = [i.pk for i in initial]
        return super().formfield(**defaults)
