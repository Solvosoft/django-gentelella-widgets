from djgentelella.widgets.core import update_kwargs, TextInput


class MultiWidgetWidget(TextInput):
    input_type = 'hidden'
    template_name = 'gentelella/widgets/multiwidget_hidden.html'

    @property
    def is_hidden(self):
        return False

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__)
        super().__init__(attrs)

    def get_widget_prop(self, value, attrs):
        value = self.format_value(value)
        return value, attrs, self.template_name

    def get_context(self, name, value, attrs):
        value, attrs, template_name = self.get_widget_prop(value, attrs)
        return {
            "widget": {
                "name": name,
                "is_hidden": self.is_hidden,
                "required": self.is_required,
                "value": value,
                "attrs": self.build_attrs(self.attrs, attrs),
                "template_name": template_name,
            },
        }

    def format_value(self, value):
        """
        Return a value as it should appear when rendered in a template.
        """
        if value == "" or value is None:
            return None
        if 'null' == value:
            return "{'widget': 'Textarea', 'value': '', 'options': {} }"
        return str(value)
