import copy

from django import forms
from django.urls import reverse_lazy

from djgentelella.widgets.core import Select, update_kwargs, SelectMultiple


class AutocompleteSelectBase(Select):
    template_name = 'gentelella/widgets/autocomplete_select.html'
    option_template_name = 'gentelella/widgets/select_option.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True, multiple=None):
        if extraskwargs:
            attrs = update_kwargs(attrs, 'AutocompleteSelect', base_class='form-control ')
        if self.baseurl is None:
            raise ValueError('Autocomplete requires baseurl to work')
        else:
            self.baseurl = self.baseurl

        super(AutocompleteSelectBase, self).__init__(attrs,  choices=choices, extraskwargs=False)

    def get_context(self, name, value, attrs):
        context = super().get_context(name,value,attrs)
        context['url'] = reverse_lazy(self.baseurl)
        return context

    def optgroups(self, name, value, attrs=None):
        if value and value != ['']:
            self.choices.queryset = self.choices.queryset.filter(pk__in=value)
        else:
            self.choices.queryset = self.choices.queryset.none()
        return super().optgroups(name, value, attrs=attrs)

class AutocompleteSelectMultipleBase(SelectMultiple):
    template_name = 'gentelella/widgets/autocomplete_select.html'
    option_template_name = 'gentelella/widgets/select_option.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, 'AutocompleteSelectMultiple',  base_class='form-control ')
        if self.baseurl is None:
            raise ValueError('Autocomplete requires baseurl to work')
        else:
            self.baseurl = self.baseurl
        super(AutocompleteSelectMultipleBase, self).__init__(attrs, choices=choices, extraskwargs=False)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['url'] = reverse_lazy(self.baseurl)
        return context

    def optgroups(self, name, value, attrs=None):
        if value and value != ['']:
            self.choices.queryset = self.choices.queryset.filter(pk__in=value)
        else:
            self.choices.queryset = self.choices.queryset.none()
        return super().optgroups(name, value, attrs=attrs)


def AutocompleteSelect(url):
    class AutocompleteSelect(AutocompleteSelectBase):
        baseurl = url

    return AutocompleteSelect

def AutocompleteSelectMultiple(url):
    class AutocompleteSelectMultiple(AutocompleteSelectMultipleBase):
        baseurl = url
    return AutocompleteSelectMultiple
