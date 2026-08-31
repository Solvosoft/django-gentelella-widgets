"""Browser tests for the datatable + modal CRUD (``ObjectManagement``).

The flow under test is the one a user sees: a DataTable listing rows over the
REST API, a bootstrap modal holding the create/update form, and the table
refreshing itself after each write. None of that is exercised by the API tests,
which post to the viewset directly.

The inline case (``BaseInlineObjectManagement``, new in 0.6.0) additionally has
to keep one parent's children out of another parent's table -- the scoping is
the whole point of the class, and getting it wrong leaks data across objects.

The demo model has two required file fields, and neither needs a real upload to
drive from a test. ``simple_archive`` is a plain file input, so selenium hands
it a path and the form javascript base64s it. ``chunked_archive`` is a
``FileChunkedUpload``: the widget uploads in the background and leaves
``{"token": <upload_id>}`` in its hidden input, which is all the serializer
reads -- so a ``ChunkedUpload`` row in the fixture plus that string in the
hidden input is a completed upload as far as the page is concerned.
"""

import shutil
import tempfile
from pathlib import Path

from django.core.files.base import ContentFile
from django.test import tag
from django.utils import timezone

from demoapp.models import (
    A, Community, Country, ObjectManagerDemoModel, ObjectManagerDemoNote,
)
from djgentelella.chunked_upload.constants import COMPLETE
from djgentelella.models import ChunkedUpload
from .base import By, EC, SeleniumTestCase


def make_demo_object(name, country, community, letter=None):
    """A fully populated ObjectManagerDemoModel -- every field is required."""
    obj = ObjectManagerDemoModel.objects.create(
        name=name,
        float_number=1.5,
        knob_number=10,
        born_date=timezone.now().date(),
        last_time=timezone.now(),
        livetime_range='01/01/2026 - 31/12/2026',
        description='<p>demo</p>',
        simple_archive='files/demo.txt',
        chunked_archive='chunked_files/demo.txt',
        radio_elements=1,
        taging_list='uno,dos',
        yes_no=True,
        field_autocomplete=country,
        field_select=community,
    )
    obj.m2m_autocomplete.add(country)
    if letter is not None:
        obj.m2m_multipleselect.add(letter)
    return obj


@tag('selenium')
class ObjectManagementTableTest(SeleniumTestCase):
    """The list side: DataTable boots and shows what the API returns."""

    def setup_data(self):
        self.country = Country.objects.create(name='Costa Rica')
        self.community = Community.objects.create(name='Guanacaste')
        self.letter = A.objects.create(display='letra a')
        make_demo_object('primero', self.country, self.community, self.letter)
        make_demo_object('segundo', self.country, self.community, self.letter)

    def test_the_datatable_lists_the_existing_rows(self):
        self.go('/object_management')
        self.wait_js(
            "return jQuery.fn.DataTable.isDataTable('#object_table')",
            message='#object_table was never turned into a DataTable')
        self.wait_rows(
            '#object_table', lambda rows: len(rows) >= 2,
            'the table never loaded the two seeded rows')

        rows = ' | '.join(self.rows_of('#object_table'))
        self.assertIn('primero', rows)
        self.assertIn('segundo', rows)

    def test_the_search_box_filters_through_the_api(self):
        self.go('/object_management')
        self.wait_rows('#object_table', lambda rows: len(rows) >= 2)

        # DataTables debounces and re-queries the server; the filtering is not
        # done in the browser, so this covers the viewset's search backend too.
        self.js("jQuery('#object_table').DataTable()"
                ".search('primero').draw();")
        self.wait_rows(
            '#object_table',
            lambda rows: len(rows) == 1 and 'primero' in rows[0],
            'searching never narrowed the table down to one row')

    def test_every_crud_modal_is_present(self):
        self.go('/object_management')
        for modal in ('create_obj_modal', 'update_obj_modal',
                      'detail_obj_modal', 'delete_obj_modal'):
            with self.subTest(modal=modal):
                self.assertIsNotNone(
                    self.js('return document.getElementById(arguments[0])',
                            modal),
                    f'#{modal} is missing from the page')


@tag('selenium')
class ObjectManagementWriteTest(SeleniumTestCase):
    """Create, update and delete through the row actions and their modals."""

    def setup_data(self):
        self.country = Country.objects.create(name='Costa Rica')
        self.community = Community.objects.create(name='Guanacaste')
        self.letter = A.objects.create(display='letra a')
        self.obj = make_demo_object('objeto original', self.country,
                                    self.community, self.letter)

        # What a finished resumable upload leaves behind. The widget writes
        # {"token": upload_id} into its hidden input once the last chunk is
        # acknowledged, and the serializer looks the row up by that id.
        self.upload = ChunkedUpload.objects.create(
            user=self.user, filename='subido.txt', offset=4, status=COMPLETE,
            file=ContentFile(b'hola', name='subido.txt'))

        # A real file on disk for the plain file input: selenium types the path
        # into it and the form javascript reads it back as base64.
        self.upload_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.upload_dir, ignore_errors=True)
        self.simple_file = self.upload_dir / 'adjunto.txt'
        self.simple_file.write_text('contenido del adjunto')

    def _open(self):
        self.go('/object_management')
        self.wait_js(
            "return jQuery.fn.DataTable.isDataTable('#object_table')",
            message='#object_table was never turned into a DataTable')
        self.wait_rows('#object_table', lambda rows: len(rows) >= 1)

    def _row_action(self, action):
        """Fire the row action the way its icon's onclick does."""
        self.js(
            "call_obj_crud_event('setmeunique', arguments[0], 0);", action)

    def _fill_scalars(self, prefix, name):
        """Everything that is a value in an input, in one round trip."""
        self.js(
            "const p = arguments[0];"
            "const set = (field, val) => {"
            "  const e = document.querySelector('#id_' + p + '-' + field);"
            "  if (!e) throw new Error('missing field ' + field);"
            "  e.value = val;"
            "  e.dispatchEvent(new Event('change', {bubbles: true})); };"
            "set('name', arguments[1]);"
            "set('float_number', '1.5');"
            "set('knob_number', '10');"
            "set('born_date', '16/08/2026');"
            "set('last_time', '16/08/2026 10:00:00');"
            "set('livetime_range', '01/01/2026 - 31/12/2026');"
            "set('taging_list', 'uno,dos');"
            # The radio group and the switch are read from `checked`, not from
            # `value`, so they cannot go through set().
            "document.querySelector("
            "  '[name=\"' + p + '-radio_elements\"][value=\"1\"]')"
            "  .checked = true;"
            "document.querySelector('#id_' + p + '-yes_no').checked = true;",
            prefix, name)

    def _fill_selects(self, prefix):
        """The four relational fields.

        The two select2 autocompletes start with no options at all -- they are
        filled from the API as the user types -- so an option has to be
        appended before it can be selected, which is what select2 itself does
        on pick.
        """
        self.js(
            "const p = arguments[0];"
            "const pick = (field, pk, label) => {"
            "  const $e = jQuery('#id_' + p + '-' + field);"
            "  $e.append(new Option(label, pk, true, true)).trigger('change');"
            "};"
            "pick('field_autocomplete', arguments[1], arguments[2]);"
            "pick('m2m_autocomplete', arguments[1], arguments[2]);"
            # These two are ordinary selects, rendered with their options.
            "jQuery('#id_' + p + '-field_select').val(arguments[3])"
            "  .trigger('change');"
            "jQuery('#id_' + p + '-m2m_multipleselect').val([arguments[4]])"
            "  .trigger('change');",
            prefix, str(self.country.pk), self.country.name,
            str(self.community.pk), str(self.letter.pk))

    def _fill_editor(self, prefix, html):
        """TinyMCE keeps its content in an iframe, not in the textarea.

        Deliberately *without* calling ``save()``: TinyMCE copies its content
        back only when the form is really submitted, through a hook on the form
        element, and a modal read by javascript never fires that. Saving here
        would hide the bug where the description arrives at the server empty --
        which is what the form serializer has to take care of.
        """
        self.js(
            "const ed = tinymce.get('id_' + arguments[0] + '-description');"
            "ed.setContent(arguments[1]);",
            prefix, html)

    def _attach_files(self, prefix):
        """Both file fields, each the way its own widget delivers a file."""
        self.driver.find_element(
            By.ID, f'id_{prefix}-simple_archive').send_keys(
                str(self.simple_file))
        # The chunked widget's hidden input is the whole contract with the
        # server: an upload id it can look a ChunkedUpload row up by.
        self.js(
            "const e = document.querySelector("
            "  'input[name=\"' + arguments[0] + '-chunked_archive\"]');"
            "e.value = JSON.stringify("
            "  {token: arguments[1], display_name: arguments[2]});"
            "e.dispatchEvent(new Event('change', {bubbles: true}));",
            prefix, self.upload.upload_id, self.upload.filename)

    def test_creating_through_the_modal_persists_every_field(self):
        self._open()
        self.js("new bootstrap.Modal('#create_obj_modal').show();")
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'id_create-name')))

        self._fill_scalars('create', 'objeto nuevo')
        self._fill_selects('create')
        self._fill_editor('create', '<p>creado desde el navegador</p>')
        self._attach_files('create')
        self.driver.find_element(
            By.CSS_SELECTOR, '#create_obj_modal .formadd').click()

        self.wait_rows(
            '#object_table',
            lambda rows: any('objeto nuevo' in r for r in rows),
            'the new object never appeared in the table')

        created = ObjectManagerDemoModel.objects.filter(
            name='objeto nuevo').first()
        self.assertIsNotNone(created, 'the object was not persisted')
        self.assertIn('creado desde el navegador', created.description)
        self.assertEqual(created.radio_elements, 1)
        self.assertTrue(created.yes_no)
        self.assertEqual(created.field_autocomplete_id, self.country.pk)
        self.assertEqual(created.field_select_id, self.community.pk)
        self.assertEqual(
            list(created.m2m_autocomplete.values_list('pk', flat=True)),
            [self.country.pk])
        # Both files have to arrive with their contents, not merely with a
        # name: base64 through the form for one, an upload id for the other.
        self.assertEqual(created.simple_archive.read(),
                         b'contenido del adjunto')
        self.assertEqual(created.chunked_archive.read(), b'hola')

    def test_updating_through_the_modal_keeps_the_files_it_was_not_given(self):
        """An edit that touches no file must not lose the ones on record.

        Both serializer fields fall back to the stored value when the payload
        carries no new file -- an empty list for the base64 one, a value with a
        `url` and no `token` for the chunked one. That fallback is what makes
        editing anything else on the form safe.
        """
        self._open()
        self._row_action('update')
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'id_update-name')))
        self.wait_js(
            "return document.querySelector('#id_update-name').value"
            " === 'objeto original'")

        self._fill_scalars('update', 'objeto renombrado')
        self._fill_selects('update')
        self._fill_editor('update', '<p>editado desde el navegador</p>')
        self.driver.find_element(
            By.CSS_SELECTOR, '#update_obj_modal .formadd').click()

        self.wait_rows(
            '#object_table',
            lambda rows: any('objeto renombrado' in r for r in rows),
            'the renamed object never appeared in the table')

        self.obj.refresh_from_db()
        self.assertEqual(self.obj.name, 'objeto renombrado')
        self.assertIn('editado desde el navegador', self.obj.description)
        self.assertEqual(self.obj.simple_archive.name, 'files/demo.txt')
        self.assertEqual(self.obj.chunked_archive.name,
                         'chunked_files/demo.txt')

    def test_the_update_modal_opens_prefilled(self):
        self._open()
        self._row_action('update')
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'id_update-name')))
        # Prefilling is what makes an edit an edit; an empty form here would
        # silently blank every field the user does not retype.
        self.wait_js(
            "return document.querySelector('#id_update-name').value"
            " === 'objeto original'",
            message='the update modal did not load the current values')

        # The description belongs to TinyMCE, and TinyMCE draws in an iframe:
        # writing it into the textarea alone leaves the editor blank over data
        # that is there, and saving then wipes the field.
        self.wait_js(
            "const ed = tinymce.get('id_update-description');"
            "return ed && ed.getContent().indexOf('demo') !== -1;",
            message='the editor did not load the stored description')
        self.assertIn(
            'demo',
            self.js("return tinymce.get('id_update-description')"
                    "  .getBody().textContent;"),
            'the text is not visible inside the editor')

    def test_deleting_through_the_modal_removes_the_row(self):
        self._open()
        self._row_action('destroy')
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'delete_obj_modal')))
        self.driver.find_element(
            By.CSS_SELECTOR, '#delete_obj_modal .delbtn').click()

        self.wait_rows(
            '#object_table',
            lambda rows: not any('objeto original' in r for r in rows),
            'the deleted object is still listed')
        self.assertFalse(
            ObjectManagerDemoModel.objects.filter(pk=self.obj.pk).exists(),
            'the object was not deleted')

    def test_saving_without_a_name_creates_nothing(self):
        """A rejected form must not silently create a half-built object."""
        self._open()
        before = ObjectManagerDemoModel.objects.count()

        self.js("new bootstrap.Modal('#create_obj_modal').show();")
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'id_create-name')))
        self.driver.find_element(
            By.CSS_SELECTOR, '#create_obj_modal .formadd').click()
        self.wait_js('return true')

        self.assertEqual(
            ObjectManagerDemoModel.objects.count(), before,
            'an invalid form created an object anyway')


@tag('selenium')
class InlineObjectManagementTest(SeleniumTestCase):
    """``BaseInlineObjectManagement`` scopes the table to one parent."""

    def setup_data(self):
        self.country = Country.objects.create(name='Costa Rica')
        self.community = Community.objects.create(name='Guanacaste')
        self.first = make_demo_object('padre uno', self.country,
                                      self.community)
        self.second = make_demo_object('padre dos', self.country,
                                       self.community)
        ObjectManagerDemoNote.objects.create(
            demo_object=self.first, title='nota del primero', body='a')
        ObjectManagerDemoNote.objects.create(
            demo_object=self.second, title='nota del segundo', body='b')

    def test_each_parent_only_shows_its_own_notes(self):
        self.go(f'/object_management/{self.first.pk}/notes')
        self.wait_rows(
            '#note_table',
            lambda rows: any('nota del primero' in r for r in rows),
            "the first parent's note never appeared")

        rows = ' | '.join(self.rows_of('#note_table'))
        self.assertIn('nota del primero', rows)
        self.assertNotIn(
            'nota del segundo', rows,
            "the other parent's note leaked into this table")

    def test_the_other_parent_shows_the_other_note(self):
        self.go(f'/object_management/{self.second.pk}/notes')
        self.wait_rows(
            '#note_table',
            lambda rows: any('nota del segundo' in r for r in rows))

        rows = ' | '.join(self.rows_of('#note_table'))
        self.assertIn('nota del segundo', rows)
        self.assertNotIn('nota del primero', rows)

    def test_a_note_created_inline_is_attached_to_its_parent(self):
        self.go(f'/object_management/{self.first.pk}/notes')
        self.wait_js("return jQuery.fn.DataTable.isDataTable('#note_table')")

        self.js("new bootstrap.Modal('#create_note_modal').show();")
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'id_create-title')))
        self.js(
            "const set = (sel, val) => {"
            "  const e = document.querySelector(sel);"
            "  e.value = val;"
            "  e.dispatchEvent(new Event('change', {bubbles: true})); };"
            "set('#id_create-title', 'nota nueva');"
            "set('#id_create-body', 'creada desde el navegador');")
        self.driver.find_element(
            By.CSS_SELECTOR, '#create_note_modal .formadd').click()

        self.wait_rows(
            '#note_table',
            lambda rows: any('nota nueva' in r for r in rows),
            'the inline note never appeared in the table')

        note = ObjectManagerDemoNote.objects.filter(title='nota nueva').first()
        self.assertIsNotNone(note, 'the note was not persisted')
        # The parent comes from the url, never from the form -- that is what
        # makes the inline viewset safe.
        self.assertEqual(note.demo_object_id, self.first.pk)
