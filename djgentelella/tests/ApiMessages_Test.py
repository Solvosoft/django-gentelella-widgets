"""The messages the design and data source APIs answer with speak the
language of the request: English, and Spanish from the ``es`` catalog."""
import json
import shutil
import tempfile
from unittest import skipUnless

from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from rest_framework.exceptions import ValidationError

from djgentelella.designs import factories
from djgentelella.tests.DesignsData_Test import DataDesignTestCase, load
from djgentelella.tests.Translations_Test import compile_catalogs


class ApiMessagesMixin:
    def setUp(self):
        super().setUp()
        self.page = self.publish(load('product_admin'))
        self.grant('demoapp.view_product')

    def detail(self, response, status):
        self.assertEqual(response.status_code, status, response.content)
        return response.json()

    def messages(self):
        table = self.api(self.page, 'products')
        facets = self.api(self.page, 'product_facets') + 'facets/'
        superuser = User.objects.create_superuser('root', password='x')
        found = {
            'json': self.detail(self.client.get(table, {'gtfilters': 'x'}), 400),
            'list': self.detail(self.client.get(table, {'gtfilters': '[1]'}), 400),
            'facet': self.detail(self.client.get(facets, {'columns': 'owner'}), 400),
            'node': self.detail(self.client.get(self.api(self.page, 'nowhere')), 404),
        }
        self.client.force_login(superuser)
        sources = 'gtdatasource-'
        found['source'] = self.detail(self.client.get(
            reverse(sources + 'rows', args=['nowhere'])), 404)
        found['columns'] = self.detail(self.client.get(
            reverse(sources + 'facets', args=['demoapp.person'])), 400)
        found['fmt'] = self.detail(self.client.post(
            reverse(sources + 'export', args=['demoapp.person']),
            json.dumps({'fmt': 3}), content_type='application/json'), 400)
        found['body'] = self.detail(self.client.post(
            reverse(sources + 'rows', args=['demoapp.person']),
            '[1]', content_type='application/json'), 400)
        for message in ('not valid JSON', 'must be a list of filter objects'):
            with self.assertRaises(ValidationError) as raised:
                factories.parse_filters('x' if 'JSON' in message else '[1]')
            found['parse: ' + message] = [str(text) for text in
                                          raised.exception.detail['gtfilters']]
        return found


@override_settings(LANGUAGE_CODE='en')
class ApiMessagesInEnglishTests(ApiMessagesMixin, DataDesignTestCase):
    def test_the_messages(self):
        self.assertEqual(self.messages(), {
            'json': {'gtfilters': ['not valid JSON']},
            'list': {'gtfilters': ['must be a list of filter objects']},
            'facet': {'detail': ['unknown facet column']},
            'node': {'detail': 'Not found.'},
            'source': {'detail': 'No data source nowhere'},
            'columns': {'detail': ['"columns" is required.']},
            'fmt': {'detail': ['"fmt" has to be a string.']},
            'body': {'detail': ['The body has to be a JSON object.']},
            'parse: not valid JSON': ['not valid JSON'],
            'parse: must be a list of filter objects':
                ['must be a list of filter objects'],
        })


@skipUnless(shutil.which('msgfmt'), 'compiling the catalog needs gettext')
class ApiMessagesInSpanishTests(ApiMessagesMixin, DataDesignTestCase):
    """The catalog is compiled into a temporary directory, which wins over
    the .mo of the package (compiled or not)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        compile_catalogs(cls.tmp.name)

    def setUp(self):
        spanish = override_settings(LANGUAGE_CODE='es', LOCALE_PATHS=[self.tmp.name])
        spanish.enable()
        self.addCleanup(spanish.disable)
        super().setUp()

    def test_the_messages(self):
        self.assertEqual(self.messages(), {
            'json': {'gtfilters': ['no es JSON válido']},
            'list': {'gtfilters': ['debe ser una lista de objetos de filtro']},
            'facet': {'detail': ['columna de faceta desconocida']},
            'node': {'detail': 'No encontrado.'},
            'source': {'detail': 'No existe la fuente de datos nowhere'},
            'columns': {'detail': ['"columns" es obligatorio.']},
            'fmt': {'detail': ['"fmt" debe ser una cadena de texto.']},
            'body': {'detail': ['El cuerpo debe ser un objeto JSON.']},
            'parse: not valid JSON': ['no es JSON válido'],
            'parse: must be a list of filter objects':
                ['debe ser una lista de objetos de filtro'],
        })
