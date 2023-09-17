from django.test import TestCase
from djgentelella.blog.forms import EntryForm, CategoryForm
from djgentelella.blog.models import Entry, Category

class EntryFormTest(TestCase):

    def setUp(self):
        # Crear una categoría de prueba y guardarla en la base de datos
        self.category = Category.objects.create(name="Categoría de prueba")

    def test_entry_form_valid(self):
        form_data = {
            'title': 'Título de prueba',
            'content': 'Contenido de prueba',
            'resume': 'Resumen de prueba',
            'is_published': True,
            'categories': [self.category.id],  # Usar el ID de la categoría creada en setUp
            # Otros datos necesarios
        }

        form = EntryForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_entry_form_invalid(self):
        # Crear un formulario inválido (por ejemplo, falta un campo requerido)
        data = {
            'title': 'Título de prueba',
            'content': 'Contenido de prueba',
            # Faltan otros campos requeridos aquí
        }
        form = EntryForm(data=data)
        self.assertFalse(form.is_valid())

class CategoryFormTest(TestCase):

    def test_category_form_valid(self):
        # Crea un formulario válido
        data = {
            'name': 'Categoría de prueba',
            # Agrega otros campos requeridos aquí según sea necesario
        }
        form = CategoryForm(data=data)
        self.assertTrue(form.is_valid())

    def test_category_form_invalid(self):
        # Crea un formulario inválido (por ejemplo, falta un campo requerido)
        data = {
            # Faltan campos requeridos aquí
        }
        form = CategoryForm(data=data)
        self.assertFalse(form.is_valid())
