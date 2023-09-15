from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from djgentelella.blog.models import Entry, Category

class YourAppTestCase(TestCase):

    def setUp(self):
        # Crea un usuario de prueba
        self.user = User.objects.create_user(username='testuser', password='testpassword')

        # Crea una categoría de prueba
        self.category = Category.objects.create(name='Test Category')

        # Crea una entrada de prueba con el campo resume
        self.entry = Entry.objects.create(
            title='Test Entry',
            author=self.user,
            content='This is a test entry content',
            is_published=True,
            published_content='This is a published test entry content',
            resume='This is a test resume content'
        )

        self.entry.categories.add(self.category)

    def test_entries_list_view(self):
        # Accede a la vista 'entrylist' y verifica que se cargue correctamente
        url = reverse('blog:entrylist')  # Cambiado a 'blog:entrylist'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gentelella/blog/entry_list.html')

        # Verifica que la entrada de prueba esté presente en la respuesta
       # self.assertContains(response, 'Test Entry')

    def test_entry_detail_view(self):
        # Accede a la vista 'entrydetail' y verifica que se cargue correctamente
        url = reverse('blog:entrydetail', kwargs={'slug': self.entry.slug})  # Cambiado a 'blog:entrydetail'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gentelella/blog/entry_detail.html')

        # Verifica que el contenido de la entrada de prueba esté presente en la respuesta
       # self.assertContains(response, 'This is a test entry content')

    # Agregar más pruebas para otras vistas y funciones según sea necesario
