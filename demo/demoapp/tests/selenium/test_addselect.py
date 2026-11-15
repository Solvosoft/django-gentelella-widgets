"""The "add" button of the catalog widgets in a browser (#116).

With the permission the button opens its modal and loads the form of
``add_url`` -- for the tree widget too, whose button was still on Bootstrap
4's ``data-toggle``. Without it the field is a working select2 with no button.
"""

from django.test import override_settings, tag

from .base import By, SeleniumTestCase

URLCONF = 'demoapp.tests.selenium.addselect_urls'


@tag('selenium')
@override_settings(ROOT_URLCONF=URLCONF)
class AddSelectTest(SeleniumTestCase):

    def open(self, query=''):
        self.go('/addselect/' + query)
        self.wait_js("return !!document.querySelector('#the-form select')")

    def test_the_button_opens_the_modal_with_the_add_form(self):
        self.open()
        for name in ('plain', 'tree'):
            with self.subTest(widget=name):
                self.driver.find_element(By.ID, f'add_{name}_id').click()
                self.wait_js(
                    f"return !!document.querySelector('#modal_{name}_id.show "
                    f"#add-form-body')",
                    message=f'the {name} modal did not open with its form')
                self.js(f"jQuery('#modal_{name}_id').modal('hide');")
                self.wait_js(
                    "return !document.querySelector('.modal.show') && "
                    "!document.querySelector('.modal-backdrop');")

    def test_without_permission_a_bare_working_select(self):
        self.open('?can_add=0')
        for name in ('plain', 'tree'):
            with self.subTest(widget=name):
                self.assertEqual(
                    self.driver.find_elements(By.ID, f'add_{name}_id'), [])
                self.assertEqual(
                    self.driver.find_elements(By.ID, f'modal_{name}_id'), [])
                self.wait_js(
                    f"return jQuery('#id_{name}').hasClass("
                    "'select2-hidden-accessible');",
                    message=f'{name} was not initialized by select2')
        errors = [entry for entry in self.driver.get_log('browser')
                  if entry['level'] == 'SEVERE']
        self.assertEqual(errors, [])
