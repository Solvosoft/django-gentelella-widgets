from django import forms

from demoapp.models import Img
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import selects


class ImageForm(GTForm, forms.ModelForm):
    """The same select2-with-images widget against two sources of pictures.

    ``AutocompleteSelectImage`` draws each option through
    ``decore_img_select2``, which only ever asks the lookup for a URL. Here
    ``imagebasename`` returns an uploaded ``FileField``, while
    ``countryflagbasename`` returns ``flag_url(obj.code)`` -- the flags view,
    which serves one SVG out of the packaged sprite. Neither needs any
    JavaScript of its own.
    """

    class Meta:
        model = Img
        fields = '__all__'
        widgets = {
            'multi_image': selects.AutocompleteSelectMultipleImage('imagebasename'),
            'related_name': selects.AutocompleteSelectImage('imagebasename'),
            'country': selects.AutocompleteSelectImage(
                'countryflagbasename',
                attrs={'data-placeholder': 'Pick a country…'}),
            'countries': selects.AutocompleteSelectMultipleImage(
                'countryflagbasename'),
        }
