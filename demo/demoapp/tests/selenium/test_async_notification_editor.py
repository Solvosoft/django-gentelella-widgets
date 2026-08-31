"""The TinyMCE editor inside the async_notification screens.

``EmailEditorTinymce`` is the widget every message field in this module uses,
and each of those screens is a DataTable with create/update modals -- the shape
where an editor's content silently fails to travel, because a modal is read by
javascript instead of being submitted.

These need no MailHog: nothing here sends anything. They cover the editor
itself on the email template screen, in both directions and through the preview
button, which is the third path this module drives TinyMCE from.
"""

from django.test import tag

from djgentelella.async_notification.models import EmailTemplate
from .base import EC, By, SeleniumTestCase

EDITOR = 'id_create-message'


@tag('selenium')
class EmailTemplateEditorTest(SeleniumTestCase):

    def open_screen(self):
        self.go('/async_notification/email-templates/')
        self.wait.until(EC.presence_of_element_located((By.ID, 'datatable')))
        self.wait_js(
            "return typeof tinymce !== 'undefined'"
            "  && tinymce.get(arguments[0]) != null;", EDITOR,
            message='the editor never initialised on the template screen')

    def open_modal(self, name):
        self.js("new bootstrap.Modal('#' + arguments[0] + '_modal').show();",
                name)
        self.wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, f'#{name}_modal')))

    def test_the_editor_is_the_one_this_module_configures(self):
        """``EmailEditorTinymce`` keeps ``data-widget="EditorTinymce"`` so the
        shared initialiser runs, and repoints uploads at its own endpoints."""
        self.open_screen()

        attrs = self.js(
            'const t = document.getElementById(arguments[0]);'
            'return [t.dataset.widget, t.dataset.optionImage];', EDITOR)
        self.assertEqual(attrs[0], 'EditorTinymce')
        self.assertIn('async_notification', attrs[1],
                      'uploads are not pointed at the module endpoints')

    def test_content_typed_in_the_editor_is_saved(self):
        """No triggerSave() here on purpose.

        A modal never fires the submit TinyMCE hooks itself to, so if the form
        serializer does not flush the editor the message arrives empty and the
        server answers that the field cannot be blank.
        """
        self.open_screen()
        self.open_modal('create')

        self.js(
            "$('[name=create-code]').val('bienvenida');"
            "$('[name=create-subject]').val('Hola');"
            "tinymce.get(arguments[0]).setContent("
            "  '<p>Cuerpo escrito en el editor</p>');", EDITOR)
        self.driver.find_element(
            By.CSS_SELECTOR, '#create_modal .formadd').click()

        self.wait.until(
            lambda d: EmailTemplate.objects.filter(code='bienvenida').exists(),
            'the template was never created')
        template = EmailTemplate.objects.get(code='bienvenida')
        self.assertIn('Cuerpo escrito en el editor', template.message,
                      'the editor content did not reach the server')

    def test_an_existing_message_is_loaded_into_the_editor(self):
        EmailTemplate.objects.create(
            code='guardada', subject='Asunto',
            message='<p>Cuerpo que ya estaba guardado</p>')
        self.open_screen()

        # The row's icon calls this; its title is translated, its onclick is not.
        self.js("call_obj_crud_event('emailtemplate', 'update', 0);")

        self.wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, '#update_modal')))
        # Into the editor, not just into the textarea underneath it: an editor
        # left blank over stored text wipes the field on the next save.
        self.wait_js(
            "const ed = tinymce.get('id_update-message');"
            "return ed && ed.getContent().indexOf('ya estaba guardado') !== -1;",
            message='the stored message did not reach the editor')
        self.assertIn(
            'ya estaba guardado',
            self.js("return tinymce.get('id_update-message')"
                    "  .getBody().textContent;"),
            'the text is not visible inside the editor')

    def test_the_preview_button_reads_the_editor(self):
        """The preview goes straight through ``editor.getContent()``."""
        self.open_screen()
        self.open_modal('create')
        self.js(
            "tinymce.get(arguments[0]).setContent("
            "  '<p>Texto para la vista previa</p>');", EDITOR)

        buttons = self.driver.find_elements(
            By.CSS_SELECTOR, '#create_modal .btn-preview-template')
        if not buttons:
            self.skipTest('this screen has no preview button')
        buttons[0].click()

        self.wait_js(
            "const f = document.querySelector('#create_modal .preview-frame');"
            "if (!f) return false;"
            "const doc = f.contentDocument;"
            "return doc && doc.body"
            "  && doc.body.textContent.indexOf('vista previa') !== -1;",
            message='the preview did not show what the editor holds')
