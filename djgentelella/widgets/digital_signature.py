import base64
import json
import logging

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.forms import HiddenInput
from django.templatetags.static import static
from django.urls import reverse

from djgentelella.firmador_digital.signvalue_utils import ValueDSParser
from djgentelella.widgets.core import update_kwargs

logger = logging.getLogger("djgentelella")


class DigitalSignatureInput(HiddenInput, ValueDSParser):
    template_name = 'gentelella/widgets/digital_signature.html'
    input_type = 'hidden'

    @property
    def is_hidden(self):
        return True

    def __init__(self, attrs=None, extraskwargs=True, ws_url=None, cors=None,
                 title=None, render_basename=None, icon_url=None,
                 extra_render_args=None,
                 default_page="first"):
        attrs = attrs or {}
        attrs['data-ws-url'] = ws_url
        attrs['cors'] = cors
        attrs['title'] = title

        self.render_basename = render_basename
        self.icon_url = icon_url
        self.extra_render_args = extra_render_args or []

        if self.icon_url is None:
            self.icon_url = 'gentelella/images/firmador.ico'
        if self.render_basename is None:
            logger.warning(
                "No base name for DigitalSignatureInput, this will generate a 500 error in the future")
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
                raise ValueError(
                    "Must provide a ws_url in attrs of DigitalSignatureInput.")

        if not cors:
            if not cors and settings.FIRMADOR_CORS:
                attrs['cors'] = settings.FIRMADOR_CORS
            else:
                raise ValueError(
                    "Must provide a cors in attrs of DigitalSignatureInput.")

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
        valuedata = None
        if value:
            contenttype = ContentType.objects.get_for_model(value.instance).pk
            valuedata = self.get_field_attribute_for_get(value.field.name, value,
                                                         contenttype)
            url_args = self.extra_render_args + [contenttype, value.instance.pk]
            attrs['data-pk'] = value.instance.pk
            attrs['data-cc'] = contenttype
            attrs['data-value'] = valuedata
            attrs['data-renderurl'] = reverse(self.render_basename,
                                              args=url_args)
            attrs['data-renderattr'] = "value=" + valuedata
            attrs['data-logo'] = self.get_icon_url(value)
        context = super().get_context(name, valuedata, attrs)
        context["widget"]["type"] = self.input_type
        return context

    def get_field_attribute_for_get(self, name, value, contenttype):
        attrs = {
            "field_name": name,
            "contenttype": contenttype,
            "pk": value.instance.pk
        }
        b64 = base64.b64encode(json.dumps(attrs).encode()).decode()
        return b64

    def parse_value(self, value):
        return super().parse_value(value)

    def value_from_datadict(self, data, files, name):
        if name in data:
            jsondata = self.get_json_file(data[name])
            if jsondata:
                filefield = self.get_filefield(jsondata)
                return filefield
        return None

    def value_omitted_from_data(self, data, files, name):
        return name not in data
