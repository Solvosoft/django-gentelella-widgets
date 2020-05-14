from djgentelella.widgets.core import Select, update_kwargs, SelectMultiple


class TreeSelect(Select):
    """ """
    template_name = 'gentelella/widgets/tree_select.html'
    option_template_name = 'gentelella/widgets/tree_select_option.html'


    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__,
                                  base_class='form-control ')
        super().__init__(attrs,  choices=choices, extraskwargs=False)


class TreeSelectMultiple(SelectMultiple):
    """ """
    template_name = 'gentelella/widgets/tree_select.html'
    option_template_name = 'gentelella/widgets/tree_select_option.html'


    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__,
                                  base_class='form-control ')
        super().__init__(attrs,  choices=choices, extraskwargs=False)



class TreeSelectMultipleWithAdd(TreeSelectMultiple):
    """ """
    template_name = 'gentelella/widgets/addtreeselect.html'
    option_template_name = 'gentelella/widgets/tree_select_option.html'

    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__,
                                  base_class='form-control ')
        if 'add_url' not in attrs:
            raise ValueError('TreeSelectMultipleWithAdd requires add_url in attrs')
        super().__init__(attrs,  choices=choices, extraskwargs=False)


class TreeSelectWithAdd(TreeSelect):
    """ """
    template_name = 'gentelella/widgets/addtreeselect.html'
    option_template_name = 'gentelella/widgets/tree_select_option.html'


    def __init__(self, attrs=None, choices=(), extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__,
                                  base_class='form-control ')
        if 'add_url' not in attrs:
            raise ValueError('TreeSelectMultipleWithAdd requires add_url in attrs')
        super().__init__(attrs,  choices=choices, extraskwargs=False)
