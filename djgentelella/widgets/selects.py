import copy

from django import forms
from django.db.models import ManyToManyField
from django.urls import reverse_lazy

from djgentelella.widgets.core import Select, update_kwargs

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

        if multiple:
            attrs['multiple']=True
        super(AutocompleteSelectBase, self).__init__(attrs,  choices=choices, extraskwargs=False)

    def get_context(self, name, value, attrs):
        context = super().get_context(name,value,attrs)
        context['url'] = reverse_lazy(self.baseurl)
        return context


class AutocompleteSelectMultipleBase(AutocompleteSelectBase):
    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, 'AutocompleteSelectMultiple',  base_class='form-control ')
        super(AutocompleteSelectMultipleBase, self).__init__(attrs, multiple=True, choices=choices, extraskwargs=False)




class AutocompleteModelSelectMultipleBase(forms.ModelMultipleChoiceField):

    def __init__(self, queryset, **kwargs):
        super().__init__(self, queryset, **kwargs)

    def get_context(self, name, value, attrs):
        attrs['class'] = 'form-control'
        attrs['data-widget'] = 'AutocompleteSelectMultiple'
        context = super().get_context(name,value,attrs)
        context['url'] = reverse_lazy(self.baseurl)
        return context


def AutocompleteSelect(url):
    class AutocompleteSelect(AutocompleteSelectBase):
        baseurl = url

    return AutocompleteSelect

def AutocompleteSelectMultiple(url):
    class AutocompleteSelectMultiple(AutocompleteSelectMultipleBase):
        baseurl = url
    return AutocompleteSelectMultiple

def AutocompleteModelSelectMultiple(url):
    class AutocompleteModelSelectMultiple(AutocompleteModelSelectMultipleBase):
        baseurl = url

    return AutocompleteModelSelectMultiple