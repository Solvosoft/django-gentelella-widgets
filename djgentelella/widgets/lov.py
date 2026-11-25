import json

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from djgentelella.lov import get_lov
from djgentelella.widgets.core import Select, SelectMultiple, update_kwargs


class LOVSelectBase:
    """A select2 fed by the LOV ``lov`` (``gtapis/lov/<lov>/``).

    ``parents`` maps a parameter of the LOV to the form field that feeds it,
    when the names differ: ``LOVSelect('cantones', parents={'provincia':
    'province'})``. When one of those fields changes the select is emptied and
    reloads (the ``refresh`` dynamic action).

    Only the selected values are rendered as ``<option>``; their label comes
    from the LOV, evaluated with the parent values of the form when the widget
    belongs to a ``LOVChoiceField``.
    """

    def __init__(self, lov, attrs=None, parents=None):
        if not isinstance(lov, str) or not lov:
            raise TypeError('LOVSelect needs the name of a registered LOV')
        self.lov = lov
        self.parents = dict(parents or {})
        # Filled per form by LOVChoiceField.get_bound_field().
        self.lov_prefix = None
        self.lov_parent_values = {}
        self.lov_request = None
        attrs = update_kwargs(attrs, self.widget_name, base_class='form-control ')
        super().__init__(attrs, extraskwargs=False)

    def depends_on(self):
        """``{lov parameter: form field}``."""
        return {name: self.parents.get(name, name)
                for name in get_lov(self.lov).depends_on}

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget_attrs = context['widget']['attrs']
        widget_attrs['data-url'] = reverse('gt-lov', args=[self.lov])
        widget_attrs['data-lov'] = self.lov
        widget_attrs['data-lov-depends'] = json.dumps(self.depends_on())
        if self.lov_prefix is not None:
            widget_attrs['data-lov-prefix'] = self.lov_prefix
        return context

    def label_for(self, value):
        lov = get_lov(self.lov)
        label = lov.label(value, self.lov_parent_values, self.lov_request)
        return str(value) if label is None else label

    def optgroups(self, name, value, attrs=None):
        options = []
        if not self.allow_multiple_selected:
            # The empty option select2 needs for the placeholder and to clear.
            options.append(self.create_option(name, '', '', False, 0, attrs=attrs))
        values = [item for item in value if item not in ('', None)]
        for index, item in enumerate(values, start=len(options)):
            options.append(self.create_option(
                name, item, self.label_for(item), True, index, attrs=attrs))
        return [(None, options, 0)]


class LOVSelect(LOVSelectBase, Select):
    widget_name = 'LOVSelect'


class LOVSelectMultiple(LOVSelectBase, SelectMultiple):
    widget_name = 'LOVSelectMultiple'


class LOVPopupSelect(LOVSelectBase, Select):
    """A LOV searched in a modal, page by page: for lists too long for a
    dropdown.

    Same LOV, endpoint, parents and ``LOVChoiceField`` as :class:`LOVSelect`
    (``LOVChoiceField('products', widget=LOVPopupSelect)``). The value lives in
    a hidden ``<select>`` with only the chosen option; beside it a read-only
    box shows its label, a button opens the search and another clears it.
    """

    widget_name = 'LOVPopupSelect'
    template_name = 'gentelella/widgets/lov_popup.html'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget_attrs = context['widget']['attrs']
        widget_attrs['class'] = (widget_attrs.get('class', '')
                                 + ' gt-lov-popup-value visually-hidden')
        widget_attrs['tabindex'] = '-1'
        widget_attrs['aria-hidden'] = 'true'
        selected = [option['label'] for _group, options, _index
                    in context['widget']['optgroups'] for option in options
                    if option['selected'] and option['value'] not in ('', None)]
        context['selected_label'] = selected[0] if selected else ''
        context['texts'] = {
            'search': _('Search'), 'clear': _('Clear'), 'close': _('Close'),
            'previous': _('Previous'), 'next': _('Next'),
            'title': _('Select an element'), 'empty': _('No results'),
        }
        return context
