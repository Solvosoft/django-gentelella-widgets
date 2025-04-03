from django.forms.widgets import ClearableFileInput
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from djgentelella.widgets.core import update_kwargs


class CleanableFileInput(ClearableFileInput):
    template_name = "gentelella/widgets/cleanable-fileinput.html"
    input_type = "file"

    def __init__(self, attrs=None, extraskwargs=True):

        if extraskwargs:
            attrs = update_kwargs(
                attrs, self.__class__.__name__, )
        super().__init__(attrs)

    def format_value(self, value):
        if value and hasattr(value, "url"):
            return mark_safe(
                f'<a href="{value.url}" title="{_("Download")}" target="_blank" class="custom-file-link"><i class="fa fa-download" aria-hidden="true"></i></a>'
            )
        return ""

    def filename_text(self, value):
        if value and hasattr(value, "url"):
            file_name = value.name.rsplit("/", 1)[-1]
            if file_name:
                return file_name

        return ""

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        # add the values to the context
        context["widget"]["formatted_value"] = self.format_value(value)
        context["widget"]["id"] = attrs.get("id", name)
        context["widget"]["filename_text"] = self.filename_text(value)

        return context
