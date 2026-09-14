from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from djgentelella.widgets.core import SelectMultiple, update_kwargs


class FilteredSelectMultiple(SelectMultiple):
    """Two side by side lists, the django admin ``filter_horizontal`` layout.

    Options live either in the widget's own ``choices`` or behind a
    ``BaseSelect2View`` endpoint. Without ``url`` the template renders every
    option inside the real select and the javascript moves the unselected ones
    to the available panel, so the widget degrades to a plain multiple select
    when javascript is off. With ``url`` only the chosen options are rendered
    and the available panel is filled page by page over the same select2 API
    the autocomplete widgets use.
    """

    template_name = 'gentelella/widgets/filteredselectmultiple.html'
    option_template_name = 'gentelella/widgets/select_option.html'
    allow_multiple_selected = True

    def __init__(self, attrs=None, choices=(), verbose_name=None, url=None,
                 url_suffix='-list', url_args=None, url_kwargs=None,
                 add_url=None, is_stacked=False, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(
                attrs,
                self.__class__.__name__,
                base_class='gt-fsm-list gt-fsm-chosen form-control ',
            )
        attrs = attrs or {}
        self.verbose_name = verbose_name
        self.baseurl = url + url_suffix if url else None
        self.extra_url_args = url_args or []
        self.extra_url_kwargs = url_kwargs or {}
        self.add_url = add_url
        self.is_stacked = is_stacked
        super().__init__(attrs, choices=choices, extraskwargs=False)

    def optgroups(self, name, value, attrs=None):
        # With an endpoint the available panel is filled over ajax, so dumping
        # the whole table into the page would be both slow and pointless: keep
        # only what is actually selected, the same way BaseAutocomplete does.
        if self.baseurl and hasattr(self.choices, 'queryset'):
            if value and value != ['']:
                self.choices.queryset = self.choices.queryset.filter(pk__in=value)
            else:
                self.choices.queryset = self.choices.queryset.none()
        return super().optgroups(name, value, attrs=attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs=attrs)
        # These drive markup, so they travel through the context and not as
        # data-* attributes: a django template cannot read widget.attrs.data-url
        # (the hyphen is parsed as a subtraction).
        verbose_name = self.verbose_name or name
        context['url'] = None
        if self.baseurl:
            context['url'] = reverse_lazy(
                self.baseurl, args=self.extra_url_args, kwargs=self.extra_url_kwargs
            )
        context['add_url'] = self.add_url
        context['is_stacked'] = self.is_stacked
        context['verbose_name'] = verbose_name
        context['available_label'] = _('Available %(name)s') % {'name': verbose_name}
        context['chosen_label'] = _('Chosen %(name)s') % {'name': verbose_name}
        return context
