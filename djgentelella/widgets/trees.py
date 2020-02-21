from djgentelella.widgets.core import Select, update_kwargs, SelectMultiple


class TreeSelect(Select):
    template_name = 'gentelella/widgets/tree_select.html'
    option_template_name = 'gentelella/widgets/tree_select_option.html'


    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__,
                                  base_class='form-control ')
        super().__init__(attrs,  choices=choices, extraskwargs=False)


class TreeSelectMultiple(SelectMultiple):
    template_name = 'gentelella/widgets/tree_select.html'
    option_template_name = 'gentelella/widgets/tree_select_option.html'


    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__,
                                  base_class='form-control ')
        super().__init__(attrs,  choices=choices, extraskwargs=False)

