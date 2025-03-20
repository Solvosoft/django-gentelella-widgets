from django.conf import settings
from django.forms import HiddenInput
from djgentelella.widgets.core import update_kwargs


class DigitalSignatureInput(HiddenInput):
    template_name = 'gentelella/widgets/digital_signature.html'
    input_type = 'hidden'

    def __init__(self, attrs=None, extraskwargs=True, ws_url=None, cors=None, title=None,
                 default_page="first"):
        attrs = attrs or {}
        attrs['data-ws-url'] = ws_url
        attrs['cors'] = cors
        attrs['title'] = title

        self.validate_attrs(attrs, ws_url, cors, default_page)

        if extraskwargs:
            attrs = update_kwargs(
                attrs, self.__class__.__name__, )
        super().__init__(attrs)

    def validate_attrs(self, attrs, ws_url, cors, default_page):
        if not ws_url:
            if not ws_url and settings.FIRMADOR_WS_URL:
                attrs['data-ws-url'] = settings.FIRMADOR_WS_URL
            else:
                raise ValueError("Must provide a ws_url in attrs of DigitalSignatureInput.")

        if not cors:
            if not cors and settings.FIRMADOR_CORS:
                attrs['cors'] = settings.FIRMADOR_CORS
            else:
                raise ValueError("Must provide a cors in attrs of DigitalSignatureInput.")

        if isinstance(default_page, int) and default_page > 0:
            attrs['data-default-page'] = str(
                default_page)
        elif default_page in ["first", "last"]:
            attrs['data-default-page'] = default_page
        else:
            raise ValueError(
                "The default_page attrs in DigitalSignatureInput, must be 'first', 'last' or a positive number.")
