from django.forms import Textarea
from djgentelella.widgets.core import update_kwargs

class TextareaWysiwyg(Textarea):
    template_name = 'gentelella/widgets/wysiwygtwo.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__,base_class='froala-editor form-control')
        super().__init__(attrs)