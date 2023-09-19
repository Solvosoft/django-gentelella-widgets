from django.forms import ModelForm
from django.test import TestCase
from django.utils.html import strip_tags  # Agrega esta importación

from djgentelella.blog import models

class TestEntryEditing(TestCase):

    def setUp(self):
        self.entry = models.Entry.objects.create(
            title=u'Welcome!',
            content='### Some Content',
            is_published=False,
            resume='This is a resume',
        )

        class EntryForm(ModelForm):
            class Meta:
                model = models.Entry
                fields = ['title', 'content', 'is_published', 'resume']

        self.form_cls = EntryForm

    def test_form_editing(self):
        """Should be able to properly edit an entry within a model form"""
        update = {
            'title': 'Last Post (Final)',
            'content': '### Goodbye!',
            'is_published': True,
            'resume': 'Last resume',
        }

        form = self.form_cls(update, instance=self.entry)
        form.save()

        actual = models.Entry.objects.get(pk=self.entry.pk)
        self.assertEqual(actual.title, update['title'])
        self.assertEqual(actual.content.raw, update['content'])
        self.assertIsNotNone(actual.published_timestamp)
        self.assertEqual(strip_tags(actual.resume.rendered), update['resume'])  # Comparar con rendered sin etiquetas HTML

class TestEntryCreation(TestCase):

    def setUp(self):
        class EntryForm(ModelForm):
            class Meta:
                model = models.Entry
                fields = ['title', 'content', 'is_published', 'resume']

        self.form_cls = EntryForm

    def test_form_create(self):
        """Should be able to properly create an entry within a model form"""
        create = {
            'title': 'Last Post (Final)',
            'content': '### Goodbye!',
            'is_published': False,
            'resume': 'Last resume',
        }

        form = self.form_cls(create)
        form.save()

        actual = models.Entry.objects.get(slug='last-post-final')
        self.assertEqual(actual.title, create['title'])
        self.assertEqual(actual.content.raw, create['content'])
        self.assertIsNone(actual.published_timestamp)
        self.assertEqual(strip_tags(actual.resume.rendered), create['resume'])  # Comparar con rendered sin etiquetas HTML
