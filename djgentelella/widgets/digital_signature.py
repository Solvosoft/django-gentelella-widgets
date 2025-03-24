import logging

from django.conf import settings
from django.forms import HiddenInput
from django.templatetags.static import static
from django.urls import reverse

from djgentelella.widgets.core import update_kwargs

logger = logging.getLogger("djgentelella")


class DigitalSignatureInput(HiddenInput):
    template_name = 'gentelella/widgets/digital_signature.html'
    input_type = 'hidden'

    def __init__(self, attrs=None, extraskwargs=True, ws_url=None, cors=None,
                 title=None, render_basename=None, icon_url=None, field_name=None,
                 default_page="first"):
        attrs = attrs or {}
        attrs['data-ws-url'] = ws_url
        attrs['cors'] = cors
        attrs['title'] = title
        attrs['data-field-name'] = field_name

        self.render_basename = render_basename
        self.icon_url = icon_url
        if self.icon_url is None:
            self.icon_url = 'gentelella/images/firmador.ico'
        if self.render_basename is None:
            logger.warning(
                "No base name for DigitalSignatureInput, this will generate a 500 error in the future")
        self.validate_attrs(attrs, ws_url, cors, field_name, default_page)

        if extraskwargs:
            attrs = update_kwargs(
                attrs, self.__class__.__name__, )
        super().__init__(attrs)

    def validate_attrs(self, attrs, ws_url, cors, field_name, default_page):
        if not ws_url:
            if not ws_url and settings.FIRMADOR_WS_URL:
                attrs['data-ws-url'] = settings.FIRMADOR_WS_URL
            else:
                raise ValueError(
                    "Must provide a ws_url in attrs of DigitalSignatureInput.")

        if not cors:
            if not cors and settings.FIRMADOR_CORS:
                attrs['cors'] = settings.FIRMADOR_CORS
            else:
                raise ValueError(
                    "Must provide a cors in attrs of DigitalSignatureInput.")

        if not field_name:
            raise ValueError(
                "Must provide a field_name in attrs of DigitalSignatureInput.")

        if isinstance(default_page, int) and default_page > 0:
            attrs['data-default-page'] = str(
                default_page)
        elif default_page in ["first", "last"]:
            attrs['data-default-page'] = default_page
        else:
            raise ValueError(
                "The default_page attrs in DigitalSignatureInput, must be 'first', 'last' or a positive number.")

    def get_icon_url(self, value):
        return static(self.icon_url)

    def get_context(self, name, value, attrs):
        if value:
            attrs['data-pk'] = value.instance.pk
            attrs['data-applabel'] = value.instance._meta.app_label
            attrs['data-modelname'] = value.instance._meta.model_name
            attrs['data-renderurl'] = reverse(self.render_basename,
                                              args=[value.instance.pk])
            attrs['data-logo'] = self.get_icon_url(value)
        context = super().get_context(name, value, attrs)
        context["widget"]["type"] = self.input_type
        return context
