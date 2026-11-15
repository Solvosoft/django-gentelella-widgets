from djgentelella.widgets.core import (
    AddPermissionMixin,
    Select,
    SelectMultiple,
    js_widget_name,
    update_kwargs,
)


class TreeSelect(Select):
    """ """
    template_name = 'gentelella/widgets/tree_select.html'
    option_template_name = 'gentelella/widgets/tree_select_option.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self),
                                  base_class='form-control ')
        super().__init__(attrs, choices=choices, extraskwargs=False)


class TreeSelectMultiple(SelectMultiple):
    """ """
    template_name = 'gentelella/widgets/tree_select.html'
    option_template_name = 'gentelella/widgets/tree_select_option.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self),
                                  base_class='form-control ')
        super().__init__(attrs, choices=choices, extraskwargs=False)


class TreeSelectMultipleWithAdd(AddPermissionMixin, TreeSelectMultiple):
    """ """
    template_name = 'gentelella/widgets/addtreeselect.html'
    option_template_name = 'gentelella/widgets/tree_select_option.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True, add_perms=None):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self),
                                  base_class='form-control ')
        if 'add_url' not in attrs:
            raise ValueError('TreeSelectMultipleWithAdd requires add_url in attrs')
        attrs = self.set_add_perms(attrs, add_perms)
        super().__init__(attrs, choices=choices, extraskwargs=False)


class TreeSelectWithAdd(AddPermissionMixin, TreeSelect):
    """ """
    template_name = 'gentelella/widgets/addtreeselect.html'
    option_template_name = 'gentelella/widgets/tree_select_option.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True, add_perms=None):
        if extraskwargs:
            attrs = update_kwargs(attrs, js_widget_name(self),
                                  base_class='form-control ')
        if 'add_url' not in attrs:
            raise ValueError('TreeSelectWithAdd requires add_url in attrs')
        attrs = self.set_add_perms(attrs, add_perms)
        super().__init__(attrs, choices=choices, extraskwargs=False)
