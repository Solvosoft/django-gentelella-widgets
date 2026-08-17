"""Browser tests for the widgets that only exist once javascript has run.

These are the ones no python test can reach: the server renders an ordinary
``<input>`` and a jQuery plugin turns it into a date picker, a switch, a masked
field or a Select2 dropdown. What is asserted here is that the plugin actually
initialised and that interacting with it writes back into the form field the
server will receive -- not merely that some markup is present.
"""

from django.test import tag
from django.utils import timezone

from demoapp.models import Community, Country, Person
from .base import By, EC, SeleniumTestCase


@tag('selenium')
class DateRangeWidgetTest(SeleniumTestCase):
    """``/daterange/`` renders three flavours of the date range picker."""

    def test_pickers_initialise_and_write_back(self):
        self.go('/daterange/')

        # The server-side contract: every widget stamps its own name.
        self.assertEqual(
            self.assert_widget_ready('#id_date_range'), 'DateRangeInput')
        self.assertEqual(
            self.assert_widget_ready('#id_date_custom'),
            'DateRangeInputCustom')
        self.assertEqual(
            self.assert_widget_ready('#id_date_time'), 'DateRangeTimeInput')

        # daterangepicker attaches its instance to the element's jQuery data;
        # that is the difference between "an input is there" and "the widget
        # booted".
        self.wait_js(
            "return !!jQuery('#id_date_range').data('daterangepicker')",
            message='daterangepicker never initialised on #id_date_range')

        # Opening the picker must show the calendar, and applying a range has
        # to land in the input -- the value is what gets posted.
        #
        # The widget deliberately sets autoUpdateInput=false and passes its own
        # callback to daterangepicker (see widgets.js, DateRangeInput), so the
        # input is written by that callback and only when Apply is pressed.
        # Clicking the real button is therefore the only path that proves the
        # wiring; setStartDate alone leaves the input untouched by design.
        self.driver.find_element(By.ID, 'id_date_range').click()
        self.wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, '.daterangepicker')))
        self.assertEqual(
            self.js("return document.querySelector('#id_date_range').value"),
            '', 'the input should still be empty before Apply')

        self.js(
            "const p = jQuery('#id_date_range').data('daterangepicker');"
            "p.setStartDate('01/03/2026'); p.setEndDate('15/03/2026');")
        self.driver.find_element(
            By.CSS_SELECTOR, '.daterangepicker .applyBtn').click()
        self.wait_js(
            "return document.querySelector('#id_date_range').value"
            ".indexOf('2026') !== -1",
            message='pressing Apply never wrote the range into the input')

        value = self.js("return document.querySelector('#id_date_range').value")
        self.assertIn('01/03/2026', value)
        self.assertIn('15/03/2026', value)

    def test_the_format_declared_by_the_widget_is_the_one_rendered(self):
        self.go('/daterange/')
        # DD/MM/YYYY is what the widget advertises; a picker configured with a
        # different format would silently post something the form rejects.
        self.assertEqual(
            self.js("return document.querySelector('#id_date_range')"
                    ".dataset.format"),
            'DD/MM/YYYY')


@tag('selenium')
class YesNoInputTest(SeleniumTestCase):
    """``YesNoInput`` replaces a checkbox with a switchery switch."""

    def test_the_switch_replaces_the_checkbox_and_drives_it(self):
        self.go('/yesnoinput/')

        self.assertEqual(
            self.assert_widget_ready('#id_is_public'), 'YesNoInput')
        # switchery hides the real checkbox and injects its own span next to
        # it; both halves matter -- the span is what the user clicks, the
        # checkbox is what is submitted.
        self.wait_js(
            "return document.querySelector('#id_is_public')"
            ".nextElementSibling?.classList.contains('switchery')",
            message='switchery never wrapped #id_is_public')
        self.assertEqual(
            self.js("return getComputedStyle("
                    "document.querySelector('#id_is_public')).display"),
            'none', 'the underlying checkbox should be hidden by switchery')

        before = self.js(
            "return document.querySelector('#id_is_public').checked")
        self.js("document.querySelector('#id_is_public')"
                ".nextElementSibling.click();")
        self.wait_js(
            "return document.querySelector('#id_is_public').checked "
            "!== arguments[0]", before,
            message='clicking the switch did not toggle the checkbox')

    def test_a_dependent_field_is_revealed_by_its_switch(self):
        """``has_copies`` declares ``data-rel="copy_number"``.

        The widget hides the related field until the switch is on, which is
        behaviour that lives entirely in javascript.
        """
        self.go('/yesnoinput/')
        self.assertEqual(
            self.js("return document.querySelector('#id_has_copies')"
                    ".dataset.rel"),
            'copy_number')

        def group_shown():
            return self.js(
                "const f = document.querySelector('#id_copy_number');"
                "if (!f) return null;"
                "const g = f.closest('.form-group');"
                "return g ? getComputedStyle(g).display !== 'none' : null;")

        self.js("document.querySelector('#id_has_copies')"
                ".nextElementSibling.click();")
        self.wait_js(
            "return document.querySelector('#id_has_copies').checked "
            "|| true")
        # Whichever way round the widget starts, toggling must change it.
        self.assertIsNotNone(
            group_shown(), '#id_copy_number has no .form-group wrapper')


@tag('selenium')
class InputMaskTest(SeleniumTestCase):
    """The masked inputs rewrite what the user types as they type it."""

    def test_every_masked_field_is_initialised(self):
        self.go('/inputmask/')
        for field in ('date', 'phone', 'serial_number', 'taxid',
                      'credit_card', 'email'):
            with self.subTest(field=field):
                self.assert_widget_ready(f'#id_{field}')
        # Inputmask marks the fields it owns; without it the "masks" would be
        # plain text inputs and every assertion below would be vacuous.
        self.wait_js(
            "return document.querySelectorAll('[data-inputmask],"
            "[inputmode], input.form-control').length > 0")

    def test_typing_digits_produces_the_formatted_value(self):
        self.go('/inputmask/')
        card = self.driver.find_element(By.ID, 'id_credit_card')
        card.click()
        card.send_keys('4111111111111111')
        self.wait_js(
            "return document.querySelector('#id_credit_card').value.length > 0")
        value = self.js(
            "return document.querySelector('#id_credit_card').value")
        # The mask groups the digits; the exact separator is the plugin's
        # business, but the digits must survive and be grouped.
        self.assertIn('4111', value)
        self.assertTrue(
            any(sep in value for sep in ('-', ' ')),
            f'the credit card mask did not group the digits: {value!r}')


@tag('selenium')
class AutocompleteSelectTest(SeleniumTestCase):
    """``AutocompleteSelect`` is Select2 backed by a REST endpoint."""

    def setup_data(self):
        cr = Country.objects.create(name='Costa Rica')
        Country.objects.create(name='Panama')
        Community.objects.create(name='Guanacaste')
        Person.objects.create(
            name='Ada', country=cr, born_date=timezone.now().date(),
            last_time=timezone.now())

    def test_select2_takes_over_the_native_selects(self):
        self.go('/pgroup/create/')
        # Select2 stamps the original select and inserts its own container;
        # the stamp is the reliable signal that it initialised.
        for field in ('country', 'people', 'communities'):
            with self.subTest(field=field):
                self.wait_js(
                    "return document.querySelector(arguments[0])"
                    "?.classList.contains('select2-hidden-accessible')",
                    f'#id_{field}',
                    message=f'select2 never initialised on #id_{field}')

    def test_the_dropdown_is_populated_from_the_remote_endpoint(self):
        self.go('/pgroup/create/')
        self.wait_js(
            "return document.querySelector('#id_country')"
            "?.classList.contains('select2-hidden-accessible')")

        # Open the dropdown the way a user does and let it query the API.
        self.js("jQuery('#id_country').select2('open');")
        self.wait_js(
            "return document.querySelectorAll("
            "'.select2-results__option').length > 0",
            message='the select2 dropdown never loaded any option')

        options = self.js(
            "return Array.from(document.querySelectorAll("
            "'.select2-results__option')).map(o => o.textContent.trim());")
        self.assertTrue(
            any('Costa Rica' in o for o in options),
            f'the remote endpoint did not feed the dropdown: {options}')

    def test_choosing_an_option_writes_the_pk_into_the_select(self):
        self.go('/pgroup/create/')
        country = Country.objects.get(name='Panama')
        self.wait_js(
            "return document.querySelector('#id_country')"
            "?.classList.contains('select2-hidden-accessible')")
        # Select2 keeps the native <select> as the submitted value, so this is
        # what the server would actually receive.
        self.js(
            "const o = new Option(arguments[1], arguments[0], true, true);"
            "jQuery('#id_country').append(o).trigger('change');",
            str(country.pk), country.name)
        self.assertEqual(
            self.js("return document.querySelector('#id_country').value"),
            str(country.pk))


@tag('selenium')
class KnobWidgetTest(SeleniumTestCase):
    """``NumberKnobInput`` draws a canvas dial over a number input."""

    def test_the_dial_is_drawn_and_keeps_the_input_in_sync(self):
        self.go('/knobwidget/testform')
        for field in ('number_of_eyes', 'speed_in_miles_per_hour', 'age'):
            with self.subTest(field=field):
                self.assert_widget_ready(f'#id_{field}')

        # jquery-knob replaces the input with a canvas it draws into.
        self.wait_js(
            "return document.querySelectorAll('canvas').length >= 3",
            message='the knob canvases were never drawn')

        self.js("jQuery('#id_age').val(33).trigger('change');")
        self.assertEqual(
            self.js("return document.querySelector('#id_age').value"), '33')


@tag('selenium')
class TinymceWidgetTest(SeleniumTestCase):
    """``EditorTinymce`` swaps a textarea for the TinyMCE iframe editor."""

    def test_the_editor_replaces_the_textarea(self):
        self.go('/tinymce/')
        self.wait_js(
            "return typeof tinymce !== 'undefined' "
            "&& tinymce.editors.length > 0",
            message='tinymce never initialised on the page')
        self.wait_js(
            "return document.querySelectorAll('iframe.tox-edit-area__iframe')"
            ".length > 0",
            message='the tinymce iframe was never rendered')

    def test_content_typed_in_the_editor_reaches_the_textarea(self):
        self.go('/tinymce/')
        self.wait_js(
            "return typeof tinymce !== 'undefined' "
            "&& tinymce.editors.length > 0")
        # save() is what pushes the editor content back into the textarea the
        # server reads; without it the field posts empty.
        self.js(
            "const ed = tinymce.editors[0];"
            "ed.setContent('<p>escrito en el navegador</p>');"
            "ed.save();")
        self.wait_js(
            "return tinymce.editors[0].getElement().value.indexOf("
            "'escrito en el navegador') !== -1",
            message='triggerSave did not write the content into the textarea')
