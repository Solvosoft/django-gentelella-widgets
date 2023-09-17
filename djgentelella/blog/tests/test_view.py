from django.forms import ModelForm
from django.test import TestCase
from djgentelella.blog import models

class TestEntryEditing(TestCase):

    def setUp(self):
        # Crea una entrada de prueba sin publicar
        self.entry = models.Entry.objects.create(title='Welcome!',
                                                 content='### Some Content',
                                                 resume='This is a resume',
                                                 is_published=False)

        # Define un formulario basado en el modelo Entry
        class EntryForm(ModelForm):
            class Meta:
                model = models.Entry
                fields = ['title', 'content','resume', 'is_published']

        self.form_cls = EntryForm

    def test_form_editing(self):
        """Prueba la edición de una entrada utilizando el formulario"""
        update = {
            'title': 'Last Post (Final)',
            'content': '### Goodbye!',
            'resume': 'THis is not a resume',
            'is_published': True,
        }

        # Crea una instancia del formulario y la asocia a la entrada existente
        form = self.form_cls(update, instance=self.entry)

        # Guarda los cambios en la entrada
        form.save()

        # Obtiene la entrada actualizada desde la base de datos
        actual = models.Entry.objects.get(pk=self.entry.pk)

        # Verifica que los campos se hayan actualizado correctamente
        self.assertEqual(actual.title, update['title'])
        self.assertEqual(actual.content.raw, update['content'])
        self.assertEqual(actual.resume.raw, update['resume'])
        self.assertIsNotNone(actual.published_timestamp)


class TestEntryCreation(TestCase):

    def setUp(self):
        # Define un formulario basado en el modelo Entry
        class EntryForm(ModelForm):
            class Meta:
                model = models.Entry
                fields = ['title', 'content','resume' ,'is_published']

        self.form_cls = EntryForm

    def test_form_create(self):
        """Prueba la creación de una nueva entrada utilizando el formulario"""
        create = {
            'title': 'Last Post (Final)',
            'content': '### Goodbye!',
            'resume': 'This resume, bye',
            'is_published': False,
        }

        # Crea una instancia del formulario con los datos de creación
        form = self.form_cls(create)

        # Guarda la nueva entrada en la base de datos
        form.save()

        # Obtiene la entrada recién creada desde la base de datos
        actual = models.Entry.objects.get(slug='last-post-final')

        # Verifica que los campos se hayan creado correctamente
        self.assertEqual(actual.title, create['title'])
        self.assertEqual(actual.content.raw, create['content'])
        self.assertEqual(actual.resume.raw, create['resume'])
        self.assertIsNone(actual.published_timestamp)
