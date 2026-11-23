"""Browser tests for dynamic actions and cascading LOVs (/dynamic_actions/).

The same DynamicContactForm is driven on a plain page, inside a formset row
added by formset.js and inside the ObjectCRUD create and update modals. It
declares, in Python only: show/hide + require by kind, a total computed on the
server, a confirmation above 50% of discount and the country -> province ->
canton LOVs.
"""

import time
from decimal import Decimal

from django.test import tag

from demoapp.models import DynamicContact

from .base import EC, By, Keys, SeleniumTestCase, WebDriverException


class DynamicActionsBase(SeleniumTestCase):
    prefix = ''

    def fid(self, name, prefix=None):
        prefix = self.prefix if prefix is None else prefix
        return 'id_%s%s' % (prefix + '-' if prefix else '', name)

    # -- reading -------------------------------------------------------------
    def shown(self, name, prefix=None):
        return self.js(
            "return $('#' + arguments[0]).closest('.gtformfield').is(':visible')",
            self.fid(name, prefix))

    def value(self, name, prefix=None):
        return self.js("return $('#' + arguments[0]).val()", self.fid(name, prefix))

    def wait_value(self, name, expected, prefix=None):
        self.wait_js(
            "return $('#' + arguments[0]).val() === arguments[1]",
            self.fid(name, prefix), expected,
            message='%s never became %r (is %r)' % (
                name, expected, self.value(name, prefix)))

    def wait_ready(self, prefix=None):
        """The rules ran: the marker of the form has its runtime object."""
        self.wait_js(
            "var m = $('[data-gt-dynamic-prefix=\"' + arguments[0] + '\"]');"
            "return m.length && !!m.data('gtdynamicform');",
            self.prefix if prefix is None else prefix,
            message='the dynamic actions never initialised')

    # -- writing -------------------------------------------------------------
    def choose(self, name, value, prefix=None):
        """A static select (select2 over the <option>s): the way select2 does."""
        self.js("$('#' + arguments[0]).val(arguments[1]).trigger('change')",
                self.fid(name, prefix), value)

    def type(self, name, text, prefix=None):
        element = self.driver.find_element(By.ID, self.fid(name, prefix))
        # Select and overwrite, not clear(): WebDriver's clear() fires a
        # `change` of its own, with the field empty, that no user produces.
        # TAB blurs the input, which is when the browser fires `change`.
        element.send_keys(Keys.CONTROL, 'a')
        element.send_keys(text + Keys.TAB)

    def options(self, name, prefix=None):
        """Open the LOV select2 and return what the endpoint answered."""
        field = self.fid(name, prefix)
        self.js("$('#' + arguments[0]).select2('open')", field)
        self.wait_js(
            "var r = $('.select2-container--open .select2-results__option');"
            "return r.length && !r.hasClass('loading-results')"
            " && !r.first().text().match(/Searching|Buscando/);",
            message='the %s dropdown never loaded' % name)
        return self.js(
            "return $('.select2-container--open .select2-results__option')"
            ".map(function(){return $(this).text().trim()}).get()")

    def pick(self, name, text, prefix=None):
        """Pick ``text`` in the open-by-us LOV dropdown, clicking it."""
        self.options(name, prefix)
        option = self.driver.find_element(
            By.XPATH,
            "//li[contains(@class,'select2-results__option')][normalize-space()="
            "'%s']" % text)
        self.js("arguments[0].scrollIntoView({block: 'center'})", option)
        try:
            option.click()
        except WebDriverException:
            # The dropdown hangs below the fold of a long formset and the page
            # footer can sit over it: select the way select2 itself listens.
            self.js("$(arguments[0]).trigger('mouseup')", option)
        self.wait_js(
            "return !$('.select2-container--open').length"
            " && $('#' + arguments[0] + ' option:selected').text().trim()"
            " === arguments[1]",
            self.fid(name, prefix), text,
            message='%s was not picked in %s' % (text, name))

    # -- the scenarios, shared by every place the form lives -------------------
    def check_show_hide(self, prefix=None):
        self.assertFalse(self.shown('company_name', prefix))
        self.assertFalse(self.shown('company_id', prefix))
        self.choose('kind', 'company', prefix)
        self.wait_js(
            "return $('#' + arguments[0]).closest('.gtformfield').is(':visible')",
            self.fid('company_id', prefix))
        self.assertTrue(self.shown('company_name', prefix))
        self.assertTrue(self.js("return $('#' + arguments[0]).prop('required')",
                                self.fid('company_id', prefix)))
        self.choose('kind', 'person', prefix)
        self.assertFalse(self.shown('company_name', prefix))
        self.assertFalse(self.js("return $('#' + arguments[0]).prop('required')",
                                 self.fid('company_id', prefix)))

    def check_cascade(self, prefix=None):
        self.pick('country', 'Costa Rica', prefix)
        self.assertEqual(self.options('province', prefix),
                         ['San José', 'Alajuela', 'Cartago'])
        self.pick('province', 'Alajuela', prefix)
        self.assertEqual(self.options('canton', prefix), ['Alajuela', 'San Ramón'])
        self.pick('canton', 'San Ramón', prefix)
        self.assertEqual(self.value('canton', prefix), 'al-02')

        # A new country empties both levels below it.
        self.pick('country', 'Panamá', prefix)
        self.wait_js("return !$('#' + arguments[0]).val()",
                     self.fid('province', prefix),
                     message='the province survived a change of country')
        self.wait_js("return !$('#' + arguments[0]).val()",
                     self.fid('canton', prefix),
                     message='the canton survived a change of country')
        self.assertEqual(self.options('province', prefix), ['Panamá', 'Chiriquí'])
        self.pick('province', 'Chiriquí', prefix)
        self.assertEqual(self.options('canton', prefix), ['David', 'Boquete'])
        self.js("$('#' + arguments[0]).select2('close')", self.fid('canton', prefix))

    def click_checkbox(self, name, prefix=None):
        """A real click on the gt-check checkbox (checks.css, the iCheck
        replacement), so the browser fires the native ``change``."""
        element = self.driver.find_element(By.ID, self.fid(name, prefix))
        self.js("arguments[0].scrollIntoView({block: 'center'})", element)
        try:
            element.click()
        except WebDriverException:
            # The page footer can sit over a long formset (see pick()): a DOM
            # click toggles the input and fires the same native change.
            self.js('arguments[0].click()', element)

    def check_checkbox(self, prefix=None):
        self.assertTrue(self.js(
            "return $('#' + arguments[0]).hasClass('gt-check')",
            self.fid('send_copy', prefix)))
        self.assertFalse(self.shown('copy_email', prefix))
        self.click_checkbox('send_copy', prefix)
        self.wait_js(
            "return $('#' + arguments[0]).closest('.gtformfield').is(':visible')",
            self.fid('copy_email', prefix),
            message='is_checked() did not show copy_email')
        self.assertTrue(self.js("return $('#' + arguments[0]).prop('required')",
                                self.fid('copy_email', prefix)))
        self.click_checkbox('send_copy', prefix)
        self.wait_js(
            "return !$('#' + arguments[0]).closest('.gtformfield').is(':visible')",
            self.fid('copy_email', prefix),
            message='unchecking did not hide copy_email again')
        self.assertFalse(self.js("return $('#' + arguments[0]).prop('required')",
                                 self.fid('copy_email', prefix)))

    def check_server_total(self, prefix=None):
        self.type('quantity', '3', prefix)
        self.type('price', '10', prefix)
        self.wait_value('total', '30.00', prefix)
        self.type('discount', '10', prefix)
        self.wait_value('total', '27.00', prefix)


@tag('selenium')
class DynamicActionsPageTest(DynamicActionsBase):
    def setUp(self):
        super().setUp()
        self.go('/dynamic_actions/')
        self.wait_ready()

    def test_show_hide_and_require_by_kind(self):
        self.check_show_hide()

    def test_three_level_cascade(self):
        self.check_cascade()

    def test_total_computed_on_the_server(self):
        self.check_server_total()

    def test_is_checked_on_a_checkbox(self):
        self.check_checkbox()

    def test_confirm_reverts_when_declined(self):
        self.type('discount', '20')
        self.type('discount', '60')
        self.wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, '.gt-dynamic-confirm .swal2-cancel'))).click()
        self.wait_value('discount', '20')
        self.type('discount', '70')
        self.wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, '.gt-dynamic-confirm .swal2-confirm'))).click()
        self.wait.until(EC.invisibility_of_element_located(
            (By.CSS_SELECTOR, '.gt-dynamic-confirm')))
        self.assertEqual(self.value('discount'), '70')
        # The reversible part of a rule: a class while above 30.
        self.assertTrue(self.js("return $('#id_discount').hasClass('is-invalid')"))

    def test_the_form_saves_what_the_cascade_chose(self):
        self.type('name', 'Ana')
        self.check_cascade()
        self.pick('canton', 'Boquete')
        self.check_server_total()
        self.driver.find_element(
            By.CSS_SELECTOR, '#dynamic_form button[type=submit]').click()
        self.wait.until(lambda d: DynamicContact.objects.exists())
        contact = DynamicContact.objects.get()
        self.assertEqual((contact.country, contact.province, contact.canton),
                         ('pa', 'ch', 'ch-02'))
        self.assertEqual(contact.total, Decimal('27.00'))


@tag('selenium')
class DynamicActionsCycleTest(SeleniumTestCase):
    """Two rules that feed each other values that never converge: the
    cascade stops after MAX_DEPTH (10) changes, also when a change comes
    from a promise."""

    def test_a_cycle_of_rules_stops(self):
        self.go('/dynamic_actions/')
        self.js("""
            var calls = window.gtCycleCalls = {count: 0};
            document.gtdynamic.register('gt_cycle_bump', function (ctx) {
                calls.count++;
                // Async on purpose: the cascade goes on from a promise.
                return Promise.resolve().then(function () {
                    ctx.setValue('b', Number(ctx.value('a') || 0) + 1);
                });
            });
            var rules = [
                {when: ['a'], trigger: 'changes',
                 actions: [{action: 'call', name: 'gt_cycle_bump'}]},
                {when: ['b'], trigger: 'changes',
                 actions: [{action: 'set_value', fields: ['a'], from: 'b'}]}
            ];
            var form = $('<form id="gt-cycle"><input name="a"><input name="b">'
                         + '<div hidden></div></form>');
            form.find('div').attr('data-gt-dynamic', JSON.stringify(rules))
                .attr('data-gt-dynamic-fields', JSON.stringify(['a', 'b']));
            $('body').append(form);
            document.gtdynamic.initialize(form[0]);
            form.find('[name=a]').val('1').trigger('change');
        """)
        self.wait_js('return window.gtCycleCalls.count > 0')
        counts = []
        for _ in range(3):
            time.sleep(0.5)
            counts.append(self.js('return window.gtCycleCalls.count'))
        # It settled, after a handful of rounds (unbounded, it keeps growing).
        self.assertEqual(counts[-1], counts[0], counts)
        self.assertLessEqual(counts[-1], 10, counts)
        self.assertEqual(self.js("return $('#gt-cycle [name=a]').val()"),
                         str(counts[-1] + 1))


@tag('selenium')
class DynamicActionsFormsetTest(DynamicActionsBase):
    prefix = 'contacts-0'

    def setUp(self):
        super().setUp()
        self.go('/dynamic_actions/formset/')
        self.wait_ready()
        # A second row, cloned by formset.js from the empty form.
        self.driver.find_element(By.CSS_SELECTOR, '.formsetadd').click()
        self.wait_ready('contacts-1')

    def test_rows_are_independent(self):
        self.check_show_hide('contacts-1')
        self.choose('kind', 'company', 'contacts-1')
        self.assertTrue(self.shown('company_name', 'contacts-1'))
        self.assertFalse(self.shown('company_name', 'contacts-0'))

    def test_is_checked_in_a_cloned_row(self):
        self.check_checkbox('contacts-1')
        self.click_checkbox('send_copy', 'contacts-1')
        self.assertFalse(self.shown('copy_email', 'contacts-0'))

    def test_cascade_in_a_cloned_row(self):
        self.check_cascade('contacts-1')
        self.assertFalse(self.value('country', 'contacts-0'))

    def test_server_total_in_both_rows(self):
        self.check_server_total('contacts-1')
        self.check_server_total('contacts-0')
        self.assertEqual(self.value('total', 'contacts-1'), '27.00')


@tag('selenium')
class DynamicActionsModalTest(DynamicActionsBase):
    def setup_data(self):
        self.contact = DynamicContact.objects.create(
            kind='company', name='Acme', company_name='Acme SA', company_id='3-101',
            country='cr', province='al', canton='al-02', quantity=2, price=5,
            total=10)

    def open_page(self):
        self.go('/dynamic_actions/crud/')
        self.wait_js(
            "return jQuery.fn.DataTable.isDataTable('#dynamic_contact_table')",
            message='the table never became a DataTable')
        self.wait_rows('#dynamic_contact_table',
                       lambda rows: any('Acme' in r for r in rows))

    def test_create_modal(self):
        self.prefix = 'create'
        self.open_page()
        self.js("new bootstrap.Modal('#create_contact_modal').show();")
        self.wait.until(EC.visibility_of_element_located((By.ID, 'id_create-name')))
        self.check_show_hide()
        self.check_checkbox()
        self.check_cascade()
        self.check_server_total()

    def test_update_modal_is_evaluated_with_the_loaded_values(self):
        self.prefix = 'update'
        self.open_page()
        self.js("call_obj_crud_event('dynamiccontact', 'update', 0);")
        self.wait.until(EC.visibility_of_element_located((By.ID, 'id_update-name')))
        self.wait_value('name', 'Acme')
        # Loaded without a `change`: the modal opening is what re-evaluates.
        self.wait_js("return $('#id_update-company_id').closest('.gtformfield')"
                     ".is(':visible')",
                     message='the company fields stayed hidden for a company')
        self.wait_value('province', 'al')
        self.wait_value('canton', 'al-02')
        self.assertEqual(self.options('canton'), ['Alajuela', 'San Ramón'])
        self.js("$('#id_update-canton').select2('close')")
        self.type('quantity', '4')
        self.wait_value('total', '20.00')
        self.driver.find_element(By.CSS_SELECTOR, '#update_contact_modal .formadd') \
            .click()
        self.wait.until(lambda d: DynamicContact.objects.get().quantity == 4)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.total, Decimal('20.00'))
        self.assertEqual(self.contact.canton, 'al-02')
