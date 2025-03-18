from django.urls import reverse_lazy

from djgentelella.widgets.core import Select, update_kwargs, SelectMultiple


class BaseAutocomplete:
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['url'] = reverse_lazy(self.baseurl, args=self.extra_url_args,
                                      kwargs=self.extra_url_kwargs)
        return context

    def optgroups(self, name, value, attrs=None):
        if value and value != ['']:
            self.choices.queryset = self.choices.queryset.filter(pk__in=value)
        else:
            self.choices.queryset = self.choices.queryset.none()
        return super().optgroups(name, value, attrs=attrs)


class AutocompleteSelectBase(BaseAutocomplete, Select):
    template_name = 'gentelella/widgets/autocomplete_select.html'
    option_template_name = 'gentelella/widgets/select_option.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, 'AutocompleteSelect',
                                  base_class='form-control ')
        if self.baseurl is None:
            raise ValueError('Autocomplete requires baseurl to work')
        else:
            self.baseurl = self.baseurl
        attrsn = {
            'data-start_empty': 'false'
        }
        attrsn.update(attrs)
        attrsn.update(self.extra_attrs)
        super(AutocompleteSelectBase, self).__init__(attrsn, choices=choices,
                                                     extraskwargs=False)


class AutocompleteSelectMultipleBase(BaseAutocomplete, SelectMultiple):
    template_name = 'gentelella/widgets/autocomplete_select.html'
    option_template_name = 'gentelella/widgets/select_option.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, 'AutocompleteSelectMultiple',
                                  base_class='form-control ')
        if self.baseurl is None:
            raise ValueError('Autocomplete requires baseurl to work')
        else:
            self.baseurl = self.baseurl
        attrsn = {
            'data-start_empty': 'false'

        }
        attrsn.update(attrs)
        attrsn.update(self.extra_attrs)
        super(AutocompleteSelectMultipleBase, self).__init__(attrsn, choices=choices,
                                                             extraskwargs=True)


def AutocompleteSelect(url, url_suffix="-list", url_args=[], url_kwargs={}, attrs={}):
    class AutocompleteSelect(AutocompleteSelectBase):
        baseurl = url + url_suffix
        extra_attrs = attrs.copy()
        extra_url_kwargs = url_kwargs.copy()
        extra_url_args = url_args.copy()

    return AutocompleteSelect


def AutocompleteSelectMultiple(url, url_suffix="-list", url_args=[], url_kwargs={},
                               attrs={}):
    class AutocompleteSelectMultiple(AutocompleteSelectMultipleBase):
        baseurl = url + url_suffix
        extra_attrs = attrs.copy()
        extra_url_kwargs = url_kwargs.copy()
        extra_url_args = url_args.copy()

    return AutocompleteSelectMultiple
