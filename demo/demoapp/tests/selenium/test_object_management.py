"""Browser tests for the datatable + modal CRUD (``ObjectManagement``).

The flow under test is the one a user sees: a DataTable listing rows over the
REST API, a bootstrap modal holding the create/update form, and the table
refreshing itself after each write. None of that is exercised by the API tests,
which post to the viewset directly.

The inline case (``BaseInlineObjectManagement``, new in 0.6.0) additionally has
to keep one parent's children out of another parent's table -- the scoping is
the whole point of the class, and getting it wrong leaks data across objects.
"""

from django.test import tag
from django.utils import timezone

from demoapp.models import (
    A, Community, Country, ObjectManagerDemoModel, ObjectManagerDemoNote,
)
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
                    self.js("return document.getElementById(arguments[0])",
                            modal),
                    f'#{modal} is missing from the page')


@tag('selenium')
class ObjectManagementWriteTest(SeleniumTestCase):
    """Update and delete through the row actions and their modals.

    Creation is covered by the inline notes below instead: the demo model has
    two required FileFields (``simple_archive``, ``chunked_archive``), and the
    chunked one only accepts an upload id produced by a prior resumable upload,
    which is a fixture problem rather than anything about the modal.
    """

    def setup_data(self):
        self.country = Country.objects.create(name='Costa Rica')
        self.community = Community.objects.create(name='Guanacaste')
        self.obj = make_demo_object('objeto original', self.country,
                                    self.community)

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

    # Updating this model through the modal is not covered here: the API
    # rejects a PUT that omits `simple_archive`/`chunked_archive`, which the
    # modal cannot resend (a file input cannot be prefilled, and the chunked
    # one wants an upload id). The full create + update cycle is covered on the
    # Customer page instead, whose form is three plain fields --
    # see test_trash_history.CustomerModalCrudTest.

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
        self.wait_js("return true")

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
