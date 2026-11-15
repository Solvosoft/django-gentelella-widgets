from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse


class CategoryAddButtonTest(TestCase):
    """The entry form shows "add category" only to who may create one: the
    same permission ``category_add`` requires (issue #116)."""

    def login(self, *codenames):
        user = User.objects.create_user('writer')
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='blog', codename__in=codenames))
        self.client.force_login(user)

    def page(self):
        response = self.client.get(reverse('blog:entrycreate'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_a_writer_who_cannot_add_categories_gets_no_button(self):
        self.login('add_entry')
        content = self.page()
        self.assertIn('name="categories"', content)
        self.assertNotIn('modal_categories_id', content)

    def test_a_writer_who_can_add_categories_gets_the_button(self):
        self.login('add_entry', 'add_category')
        self.assertIn('id="modal_categories_id"', self.page())
