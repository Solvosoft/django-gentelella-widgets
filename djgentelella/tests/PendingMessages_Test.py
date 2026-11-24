"""
The messages left in English after W13 speak the language of the request
(W19): async_notification's views, the calendar serializer, the flags view
and the inline object management.
"""
import json
import shutil
import tempfile
from unittest import skipUnless

from django.contrib.auth.models import User
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, force_authenticate

from demoapp.models import Country
from djgentelella.async_notification.models import (
    EmailNotification, NewsLetter, NewsLetterTask,
)
from djgentelella.objectmanagement import BaseInlineObjectManagement
from djgentelella.serializers.calendar import EventSerializer
from djgentelella.tests.Translations_Test import compile_catalogs
from djgentelella.views.flags import FlagIconView


class InlineCountries(BaseInlineObjectManagement):
    queryset = Country.objects.all()
    parent_model = Country
    parent_field = 'pk'


class PendingMessagesMixin:
    def setUp(self):
        super().setUp()
        self.superuser = User.objects.create_superuser('root', password='x')
        self.client.force_login(self.superuser)

    def detail(self, response, status, key='detail'):
        self.assertEqual(response.status_code, status)
        if hasattr(response, 'render'):
            response.render()
            return json.loads(response.content)[key]
        return response.json()[key]

    def raised(self, exception, call):
        with self.assertRaises(exception) as caught:
            call()
        error = caught.exception
        return str(error.detail[0] if hasattr(error, 'detail') else error)

    def messages(self):
        sent = EmailNotification.objects.create(
            subject='S', message='M', recipients='a@b.com', status='sent')
        task = NewsLetterTask.objects.create(
            newsletter=NewsLetter.objects.create(subject='N'), status='sent',
            send_date=timezone.now())
        api = 'async_notification:api-'
        view = InlineCountries.as_view({'get': 'list'})
        request = APIRequestFactory().get('/')
        force_authenticate(request, self.superuser)
        return {
            'already sent': self.detail(self.client.post(reverse(
                api + 'emailnotification-send-email', args=[sent.pk])), 400),
            'none selected': self.detail(self.client.post(
                reverse(api + 'emailnotification-send-selected'), {'pks': []},
                content_type='application/json'), 400),
            'processed': self.detail(self.client.post(
                reverse(api + 'emailnotification-send-selected'), {'pks': [0]},
                content_type='application/json'), 200),
            'task': self.detail(self.client.post(reverse(
                api + 'newslettertask-send-now', args=[task.pk])), 400),
            'post': self.detail(self.client.get(reverse(
                'async_notification:reassociate_files')), 405, 'error'),
            'no file': self.detail(self.client.post(reverse(
                'async_notification:async_upload_image')), 400, 'error'),
            'code': self.detail(self.client.get(reverse(
                'async_notification:model_fields')), 400, 'error'),
            'unknown code': self.detail(self.client.get(reverse(
                'async_notification:model_fields'), {'code': 'x'}), 404, 'error'),
            'params': self.detail(self.client.post(reverse(
                'async_notification:reassociate_files')), 400, 'error'),
            'content_type': self.detail(self.client.post(reverse(
                'async_notification:reassociate_files'), {
                    'upload_session': 's', 'object_id': '1',
                    'content_type': 'auth.user'}), 400, 'error'),
            'object': self.detail(self.client.post(reverse(
                'async_notification:reassociate_files'), {
                    'upload_session': 's', 'object_id': '999',
                    'content_type': 'async_notification.emailnotification'}),
                404, 'error'),
            'empty events': self.raised(serializers.ValidationError,
                                        lambda: EventSerializer([])),
            'flag': self.raised(Http404, lambda: FlagIconView().get(
                RequestFactory().get('/'), 'nowhere')),
            'inline': self.detail(view(request), 404),
        }


@override_settings(LANGUAGE_CODE='en')
class PendingMessagesInEnglishTests(PendingMessagesMixin, TestCase):
    def test_the_messages(self):
        self.assertEqual(self.messages(), {
            'already sent': 'Already sent',
            'none selected': 'No notifications selected',
            'processed': '1 notification processed',
            'task': 'Task already sent',
            'post': 'POST required',
            'no file': 'No file provided',
            'code': 'code parameter required',
            'unknown code': 'Unknown context code',
            'params': 'upload_session, object_id, and content_type required',
            'content_type': 'Invalid content_type',
            'object': 'Object not found',
            'empty events': 'Empty event parameter.',
            'flag': "Unknown flag 'nowhere'",
            'inline': 'No parent_pk given for the inline objects',
        })


@skipUnless(shutil.which('msgfmt'), 'compiling the catalog needs gettext')
class PendingMessagesInSpanishTests(PendingMessagesMixin, TestCase):
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
        with translation.override('es'):
            messages = self.messages()
        self.assertEqual(messages, {
            'already sent': 'Ya se envió',
            'none selected': 'No se seleccionó ninguna notificación',
            'processed': '1 notificación procesada',
            'task': 'La tarea ya está en estado sent',
            'post': 'Se requiere POST',
            'no file': 'No se envió ningún archivo',
            'code': 'El parámetro code es obligatorio',
            'unknown code': 'Código de contexto desconocido',
            'params': 'upload_session, object_id y content_type son obligatorios',
            'content_type': 'content_type inválido',
            'object': 'Objeto no encontrado',
            'empty events': 'El parámetro de eventos está vacío.',
            'flag': "Bandera desconocida 'nowhere'",
            'inline': 'No se indicó parent_pk para los objetos en línea',
        })
