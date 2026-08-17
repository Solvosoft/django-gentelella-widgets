"""Browser tests for the trash (soft delete + restore) and history pages.

Both pages are two DataTables talking to a REST API through the ObjectCRUD
javascript. The behaviour that matters here only exists once those tables have
loaded: a deleted row has to leave the live table *and* turn up in the trash
one, and restoring it has to put it back. The API tests cover each endpoint in
isolation; what is checked here is that the page wires them together.
"""

from django.test import tag

from django.contrib.admin.models import CHANGE

from demoapp.models import Customer
from djgentelella.history.utils import add_log
from djgentelella.models import Trash
from .base import By, EC, SeleniumTestCase


@tag('selenium')
class TrashPageTest(SeleniumTestCase):

    def setup_data(self):
        self.alive = Customer.objects.create(
            name='cliente vivo', phone_number='2222-2222',
            email='vivo@example.com')
        self.doomed = Customer.objects.create(
            name='cliente condenado', phone_number='3333-3333',
            email='condenado@example.com')

    def _open(self):
        self.go('/trash/')
        self.wait_js(
            "return jQuery.fn.DataTable.isDataTable('#table-customer')",
            message='#table-customer was never turned into a DataTable')
        self.wait_js(
            "return jQuery.fn.DataTable.isDataTable('#table-trash')",
            message='#table-trash was never turned into a DataTable')

    def test_both_tables_load_and_the_trash_starts_empty(self):
        self._open()
        self.wait_rows(
            '#table-customer', lambda rows: len(rows) >= 2,
            'the customer table never loaded the seeded rows')

        customers = ' | '.join(self.rows_of('#table-customer'))
        self.assertIn('cliente vivo', customers)
        self.assertIn('cliente condenado', customers)
        self.assertEqual(
            self.rows_of('#table-trash'), [],
            'the trash table should start empty')

    def test_a_soft_deleted_customer_moves_to_the_trash_table(self):
        self._open()
        self.wait_rows('#table-customer', lambda rows: len(rows) >= 2)

        # Soft delete goes through the model, exactly as the delete modal
        # does; the page then has to reflect it on reload.
        self.doomed.delete()
        # `objects` filters soft deleted rows out, so the row being gone from
        # it and present in `objects_with_deleted` is the soft delete.
        self.assertFalse(
            Customer.objects.filter(pk=self.doomed.pk).exists(),
            'the default manager still lists a soft deleted customer')
        self.assertTrue(
            Customer.objects_with_deleted.get(pk=self.doomed.pk).is_deleted,
            'delete() did not soft delete the customer')

        self._open()
        self.wait_rows(
            '#table-trash',
            lambda rows: any('condenado' in r for r in rows),
            'the deleted customer never reached the trash table')

        customers = ' | '.join(self.rows_of('#table-customer'))
        self.assertIn('cliente vivo', customers)
        self.assertNotIn(
            'cliente condenado', customers,
            'a soft deleted customer is still listed as live')

    def test_restoring_from_the_trash_puts_the_row_back(self):
        self.doomed.delete()
        self._open()
        self.wait_rows(
            '#table-trash', lambda rows: any('condenado' in r for r in rows))

        entry = Trash.objects.filter(object_id=self.doomed.pk).first()
        self.assertIsNotNone(entry, 'no Trash entry was created')

        # Drive the page's own restore endpoint, the one the button calls.
        self.js(
            "return fetch(arguments[0], {method: 'POST',"
            " headers: {'X-CSRFToken':"
            "   document.querySelector('[name=csrfmiddlewaretoken]').value,"
            "  'Content-Type': 'application/json'}});",
            f'/api/trash/api_trash/{entry.pk}/restore/')
        self.wait.until(
            lambda d: not Customer.objects_with_deleted.get(
                pk=self.doomed.pk).is_deleted,
            'the restore endpoint never undeleted the customer')

        self._open()
        self.wait_rows(
            '#table-customer',
            lambda rows: any('condenado' in r for r in rows),
            'the restored customer never came back to the live table')

    def test_the_delete_modals_are_wired(self):
        self._open()
        for modal in ('create_obj_modal', 'update_obj_modal',
                      'delete_obj_modal', 'delete_trash_modal'):
            with self.subTest(modal=modal):
                self.assertIsNotNone(
                    self.js('return document.getElementById(arguments[0])',
                            modal),
                    f'#{modal} is missing from the trash page')


@tag('selenium')
class CustomerModalCrudTest(SeleniumTestCase):
    """The create + update half of the modal CRUD, on a three field form.

    The trash page is an ordinary ObjectCRUD page, so this covers the same
    javascript the object management page uses, without that page's required
    file fields getting in the way.
    """

    def setup_data(self):
        self.customer = Customer.objects.create(
            name='cliente existente', phone_number='2222-2222',
            email='existente@example.com')

    def _open(self):
        self.go('/trash/')
        self.wait_js(
            "return jQuery.fn.DataTable.isDataTable('#table-customer')")
        self.wait_rows('#table-customer', lambda rows: len(rows) >= 1)

    def _fill(self, prefix, name, phone, email):
        self.js(
            "const set = (sel, val) => {"
            "  const e = document.querySelector(sel);"
            "  e.value = val;"
            "  e.dispatchEvent(new Event('change', {bubbles: true})); };"
            "set('#id_' + arguments[0] + '-name', arguments[1]);"
            "set('#id_' + arguments[0] + '-phone_number', arguments[2]);"
            "set('#id_' + arguments[0] + '-email', arguments[3]);",
            prefix, name, phone, email)

    def test_creating_through_the_modal_adds_the_row(self):
        self._open()
        self.js("new bootstrap.Modal('#create_obj_modal').show();")
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'id_create-name')))

        self._fill('create', 'cliente nuevo', '8888-8888',
                   'nuevo@example.com')
        self.driver.find_element(
            By.CSS_SELECTOR, '#create_obj_modal .formadd').click()

        # The row landing in the table proves the POST succeeded and the table
        # reloaded itself from the API.
        self.wait_rows(
            '#table-customer',
            lambda rows: any('cliente nuevo' in r for r in rows),
            'the new customer never appeared in the table')
        created = Customer.objects.filter(name='cliente nuevo').first()
        self.assertIsNotNone(created, 'the customer was not persisted')
        self.assertEqual(created.email, 'nuevo@example.com')

    def test_updating_through_the_modal_changes_the_row(self):
        self._open()
        self.js("call_obj_crud_event('crudobj', 'update', 0);")
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'id_update-name')))
        self.wait_js(
            "return document.querySelector('#id_update-name').value"
            " === 'cliente existente'",
            message='the update modal did not load the current values')

        self._fill('update', 'cliente renombrado', '2222-2222',
                   'existente@example.com')
        self.driver.find_element(
            By.CSS_SELECTOR, '#update_obj_modal .formadd').click()

        self.wait_rows(
            '#table-customer',
            lambda rows: any('cliente renombrado' in r for r in rows),
            'the renamed customer never appeared in the table')
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, 'cliente renombrado')

    def test_an_invalid_email_creates_nothing(self):
        self._open()
        before = Customer.objects.count()
        self.js("new bootstrap.Modal('#create_obj_modal').show();")
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'id_create-name')))

        self._fill('create', 'cliente malo', '7777-7777', 'esto-no-es-un-mail')
        self.driver.find_element(
            By.CSS_SELECTOR, '#create_obj_modal .formadd').click()
        self.wait_js('return true')

        self.assertEqual(
            Customer.objects.count(), before,
            'an invalid email was accepted')


@tag('selenium')
class HistoryPageTest(SeleniumTestCase):

    def setup_data(self):
        self.customer = Customer.objects.create(
            name='cliente auditado', phone_number='4444-4444',
            email='audit@example.com')

    def test_the_history_table_loads(self):
        self.go('/history/')
        self.wait_js(
            "return jQuery.fn.DataTable.isDataTable('#table-history')",
            message='#table-history was never turned into a DataTable')

    def test_the_category_filter_is_a_select2(self):
        """The filter drives the table through ``select2:select``.

        A plain ``<select>`` would never fire that event, so the table would
        stop refreshing when the category changes.
        """
        self.go('/history/')
        self.wait_js(
            "return document.querySelector('#id_category')"
            "?.classList.contains('select2-hidden-accessible')",
            message='select2 never initialised on the category filter')

        options = self.js(
            "return Array.from(document.querySelectorAll("
            "'#id_category option')).map(o => o.textContent.trim());")
        self.assertTrue(options, 'the category filter has no options')

    def test_an_edit_shows_up_in_the_audit_trail(self):
        # add_log builds its own change_message from the model and the action;
        # object_repr is the field an author controls, so that is what the row
        # is matched on.
        add_log(self.user, self.customer, CHANGE,
                object_repr='cliente auditado renombrado')

        self.go('/history/')
        self.wait_js(
            "return jQuery.fn.DataTable.isDataTable('#table-history')")
        self.wait_rows(
            '#table-history',
            lambda rows: any('cliente auditado renombrado' in r
                             for r in rows),
            'the logged change never appeared in the history table')

        row = next(r for r in self.rows_of('#table-history')
                   if 'cliente auditado renombrado' in r)
        # Who and what happened: an audit trail that loses either is useless.
        # (The model name is only shown in the message add_log builds itself;
        # passing object_repr replaces it, so it is not asserted here.)
        self.assertIn('admin', row, 'the row does not name the author')
        self.assertIn('modificar', row.lower(),
                      'the row does not name the action')
