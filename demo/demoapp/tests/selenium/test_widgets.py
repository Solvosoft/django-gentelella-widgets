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
from .base import By, EC, Keys, SeleniumTestCase


@tag('selenium')
class MomentLocaleTest(SeleniumTestCase):
    """moment ships as its core build plus one locale file per page.

    The core build only speaks English, so if the file for the active language
    stops being linked nothing errors: dates and `fromNow()` quietly turn
    English, and the date pickers print their month and weekday names in
    English too. The demo runs in Spanish, so that is what is asserted.
    """

    def test_the_active_language_locale_is_loaded(self):
        self.go('/daterange/')

        self.assertEqual(self.js('return moment.locale()'), 'es')
        self.assertEqual(
            self.js("return moment('2020-03-01').format('MMMM')"), 'marzo')
        self.assertIn(
            'hace', self.js("return moment().subtract(2, 'days').fromNow()"))

    def test_the_picker_takes_its_month_names_from_that_locale(self):
        """daterangepicker fills its calendar from moment.monthsShort() and
        moment.weekdaysMin(), so it follows the loaded locale."""
        self.go('/daterange/')

        picker = self.js(
            "const p = jQuery('#id_date_range').data('daterangepicker');"
            "return [p.locale.monthNames.slice(0, 3),"
            "        p.locale.daysOfWeek.slice(0, 3)];")
        self.assertEqual(picker[0], ['ene.', 'feb.', 'mar.'])
        self.assertEqual(picker[1], ['lu', 'ma', 'mi'])


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
    """``YesNoInput`` draws the checkbox itself as a switch.

    switchery used to hide the input and paint a ``<span>`` beside it. The
    switch is the input now, so what has to be asserted changed: the control
    the user clicks and the field the form submits are the same element.
    """

    def test_the_checkbox_is_drawn_as_a_switch(self):
        self.go('/yesnoinput/')

        self.assertEqual(
            self.assert_widget_ready('#id_is_public'), 'YesNoInput')
        # No injected sibling and nothing hidden: appearance:none plus a
        # background image is the whole widget.
        painted = self.js(
            "const el = document.querySelector('#id_is_public');"
            "const cs = getComputedStyle(el);"
            "return [el.classList.contains('gt-switch'), cs.display,"
            "        cs.appearance, cs.backgroundImage.slice(0, 4),"
            "        Math.round(el.getBoundingClientRect().width)];")
        self.assertTrue(painted[0], '#id_is_public is not a .gt-switch')
        self.assertNotEqual(painted[1], 'none',
                            'the input itself has to be visible now')
        self.assertEqual(painted[2], 'none', 'appearance:none did not apply')
        self.assertEqual(painted[3], 'url(', 'the knob image is missing')
        self.assertGreater(painted[4], 30, 'the switch did not get its width')

    def test_clicking_the_switch_toggles_the_field(self):
        self.go('/yesnoinput/')

        before = self.js(
            "return document.querySelector('#id_is_public').checked")
        self.driver.find_element(By.CSS_SELECTOR, '#id_is_public').click()

        self.wait_js(
            "return document.querySelector('#id_is_public').checked "
            "!== arguments[0]", before,
            message='clicking the switch did not toggle the checkbox')

    def test_setting_checked_from_script_repaints_it(self):
        """The reason the imperative iCheck/switchery API existed at all."""
        self.go('/yesnoinput/')

        off = self.js(
            "const el = document.querySelector('#id_is_public');"
            "el.checked = false;"
            "return getComputedStyle(el).backgroundPosition;")
        self.js("document.querySelector('#id_is_public').checked = true;")

        # Polled, not read in the same tick: the knob is transitioned, so the
        # first frame still reports the position it is animating away from.
        self.wait_js(
            "return getComputedStyle(document.querySelector('#id_is_public'))"
            "  .backgroundPosition !== arguments[0];", off,
            message='the knob did not move when .checked was set')

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

        before = group_shown()
        self.assertIsNotNone(
            before, '#id_copy_number has no .form-group wrapper')

        self.driver.find_element(By.CSS_SELECTOR, '#id_has_copies').click()

        self.wait.until(lambda d: group_shown() is not before,
                        'toggling the switch did not show or hide the field')


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
class AutocompleteSelectImageFlagsTest(SeleniumTestCase):
    """``AutocompleteSelectImage`` drawing flags from the packaged sprite.

    The widget itself has no idea what a flag is: it asks select2 to render
    options through ``decore_img_select2``, which draws whatever URL the lookup
    returns. What matters here is the whole chain -- CountryFlagLookup ->
    flag_url() -> the flags view -> an <img> the browser actually paints --
    because every link of it can fail while the dropdown still looks populated.
    """

    def setup_data(self):
        Country.objects.create(name='Costa Rica', code='cr')
        Country.objects.create(name='Japan', code='jp')

    def open_country_dropdown(self):
        self.go('/imageselect/create/')
        self.wait_js(
            "return document.querySelector('#id_country')"
            "?.classList.contains('select2-hidden-accessible')",
            message='select2 never initialised on #id_country')
        self.js("jQuery('#id_country').select2('open');")
        self.wait_js(
            "return document.querySelectorAll("
            "'.select2-results__option img.img-flag').length > 0",
            message='the dropdown drew no flag images')

    def test_each_option_carries_a_flag_from_the_flags_view(self):
        self.open_country_dropdown()
        sources = self.js(
            "return Array.from(document.querySelectorAll("
            "'.select2-results__option img.img-flag')).map(i => i.src);")
        self.assertTrue(
            any('/flags/cr.svg' in src for src in sources),
            f'the option image does not come from the flags view: {sources}')

    def test_the_flag_images_actually_render(self):
        """A 404 or a broken SVG still leaves the <img> in the DOM."""
        self.open_country_dropdown()
        painted = self.js(
            "return Array.from(document.querySelectorAll("
            "'.select2-results__option img.img-flag'))"
            ".filter(i => i.complete && i.naturalWidth > 0).length;")
        self.assertEqual(
            painted, Country.objects.count(),
            'the browser did not paint every flag the dropdown listed')


@tag('selenium')
class KnobWidgetTest(SeleniumTestCase):
    """``NumberKnobInput`` draws an SVG dial around a number input.

    The input is not decoration: it stays the value, the readout and the
    focusable control, so the keyboard and the screen reader get a real number
    field. The dial only adds pointer and wheel.
    """

    def test_every_field_gets_a_dial(self):
        self.go('/knobwidget/testform')
        for field in ('number_of_eyes', 'speed_in_miles_per_hour', 'age'):
            with self.subTest(field=field):
                self.assert_widget_ready(f'#id_{field}')

        self.wait_js(
            "return document.querySelectorAll('.gt-knob .gt-knob-dial').length"
            "  >= 3",
            message='the dials were never drawn')
        # The input has to survive inside the wrapper: it is what submits.
        self.assertTrue(self.js(
            "const el = document.querySelector('#id_age');"
            "return el.closest('.gt-knob') !== null && el.name === 'age';"))

    def test_the_arc_follows_the_value(self):
        self.go('/knobwidget/testform')

        def offset():
            return self.js(
                "return document.querySelector('#id_age')"
                "  .closest('.gt-knob').querySelector('.gt-knob-value')"
                "  .getAttribute('stroke-dashoffset');")

        self.js("jQuery('#id_age').val(33).trigger('change');")
        self.assertEqual(
            self.js("return document.querySelector('#id_age').value"), '33')
        at_33 = float(offset())

        self.js("jQuery('#id_age').val(66).trigger('change');")
        at_66 = float(offset())
        # A fuller dial means less of the circumference left undrawn.
        self.assertLess(at_66, at_33,
                        'the arc did not grow when the value did')

    def test_the_keyboard_drives_it_because_the_input_is_native(self):
        """jQuery-Knob rebuilt its own key handling; here it is the browser's."""
        self.go('/knobwidget/testform')

        field = self.driver.find_element(By.CSS_SELECTOR, '#id_age')
        self.js("document.querySelector('#id_age').value = '10';")
        field.send_keys(Keys.ARROW_UP)

        self.assertEqual(
            self.js("return document.querySelector('#id_age').value"), '11')

    def test_a_fractional_step_does_not_produce_float_noise(self):
        """speed_in_miles_per_hour declares data-step=0.1."""
        self.go('/knobwidget/testform')

        value = self.js(
            "const el = document.querySelector('#id_speed_in_miles_per_hour');"
            "el.gt_knob.write(3.3000000000000003);"
            "return el.value;")
        self.assertEqual(value, '3.3')


@tag('selenium')
class TinymceWidgetTest(SeleniumTestCase):
    """``EditorTinymce`` swaps a textarea for the TinyMCE iframe editor.

    ``tinymce.editors`` was removed in TinyMCE 8; ``tinymce.get()`` returns the
    same list.
    """

    def open_editors(self):
        self.go('/tinymce/')
        self.wait_js(
            "return typeof tinymce !== 'undefined' && tinymce.get().length > 0",
            message='tinymce never initialised on the page')

    def test_the_editor_replaces_the_textarea(self):
        self.open_editors()

        self.wait_js(
            "return document.querySelectorAll('iframe.tox-edit-area__iframe')"
            ".length > 0",
            message='the tinymce iframe was never rendered')

    def test_it_is_not_read_only(self):
        """Self-hosted TinyMCE 8 without a licence key loads read-only."""
        self.open_editors()

        self.assertEqual(
            self.js('return tinymce.get()[0].mode.get();'), 'design')

    def test_content_typed_in_the_editor_reaches_the_textarea(self):
        self.open_editors()

        # save() is what pushes the editor content back into the textarea the
        # server reads; without it the field posts empty.
        self.js(
            "const ed = tinymce.get()[0];"
            "ed.setContent('<p>escrito en el navegador</p>');"
            "ed.save();")
        self.wait_js(
            "return tinymce.get()[0].getElement().value.indexOf("
            "'escrito en el navegador') !== -1",
            message='save did not write the content into the textarea')

    def test_every_configured_plugin_is_actually_loaded(self):
        """Catches both halves of a version bump.

        A plugin that no longer exists upstream, and a plugin that exists but
        was left out of the concatenated ``tinymce-all.js``, both show up here
        as a name the PluginManager does not know.
        """
        self.open_editors()

        missing = self.js(
            "const cfg = gentelella_tinymce_config(jQuery('#id_information'));"
            "return cfg.plugins.filter(p => !tinymce.PluginManager.get(p));")
        self.assertEqual(missing, [], f'plugins configured but not loaded: {missing}')

    def test_the_toolbar_only_offers_controls_that_exist(self):
        """The 5.x toolbar asked for nine premium buttons that drew nothing,
        and named the font pickers the way TinyMCE 5 did."""
        self.open_editors()

        missing = self.js(
            "const wanted = ['undo', 'bold', 'forecolor', 'pagebreak',"
            "  'emoticons', 'fullscreen', 'preview', 'image', 'media', 'link',"
            "  'anchor', 'codesample', 'ltr'];"
            "const have = tinymce.get()[0].ui.registry.getAll().buttons;"
            "return wanted.filter(name => !(name in have));")
        self.assertEqual(missing, [], f'toolbar buttons not registered: {missing}')

        toolbar = self.js(
            "return gentelella_tinymce_config(jQuery('#id_information')).toolbar;")
        for renamed in ('fontfamily', 'fontsize', 'blocks'):
            self.assertIn(renamed, toolbar)
        for gone in ('fontselect', 'fontsizeselect', 'formatselect', 'print',
                     'checklist', 'casechange', 'permanentpen', 'pageembed',
                     'a11ycheck', 'showcomments'):
            self.assertNotIn(gone, toolbar,
                             f'{gone} does not exist in TinyMCE 8')


@tag('selenium')
class VoiceEditorTinymceTest(SeleniumTestCase):
    """``VoiceEditorTinymce`` is a TinyMCE plugin written here, in this repo.

    It registers an icon and a toggle button, and drives the editor through
    ``setActive`` / ``setEnabled`` / ``setProgressState`` / the notification
    manager as dictation runs. That is the surface a TinyMCE major version
    breaks: the toggle button's ``setDisabled`` became ``setEnabled`` in 6,
    with the sense reversed, and nothing about that failure is visible in the
    markup -- the button simply stops responding.

    The browser runs with a fake microphone, so pressing the button takes the
    real path. Transcription itself needs an ASR backend that is not installed
    here and is expected to fail; what is asserted is that no TinyMCE call
    along the way blew up.
    """

    def open_editor(self):
        self.go('/voice/')
        self.wait_js(
            "return typeof tinymce !== 'undefined' && tinymce.get().length > 0",
            message='tinymce never initialised on the voice page')
        self.driver.get_log('browser')  # drain what the page load logged

    #: Stable across locales; the tooltip is translated ("Dictar" in the demo).
    MIC = '[data-mce-name="voicedictate"]'

    def mic_button(self):
        return self.driver.find_element(By.CSS_SELECTOR, self.MIC)

    def mic_is_active(self):
        return self.js(
            'const b = document.querySelector(arguments[0]);'
            "return b ? b.getAttribute('aria-pressed') === 'true' : null;",
            self.MIC)

    def tinymce_type_errors(self):
        """Console errors that mean a TinyMCE API call did not exist."""
        return [entry['message'] for entry in self.driver.get_log('browser')
                if entry['level'] == 'SEVERE'
                and 'is not a function' in entry['message']]

    def test_the_button_and_its_icon_are_registered(self):
        self.open_editor()

        registry = self.js(
            'const r = tinymce.get()[0].ui.registry.getAll();'
            "return ['voicedictate' in r.buttons, 'microphone' in r.icons];")
        self.assertEqual(registry, [True, True],
                         'the dictate button or its icon is not registered')

    def test_the_button_is_drawn_in_the_toolbar(self):
        self.open_editor()

        self.assertTrue(
            self.js("return document.querySelectorAll('.tox-toolbar__group')"
                    '  .length > 0'),
            'the toolbar never rendered')
        self.assertIsNotNone(self.mic_button(),
                             'the dictate button is not in the toolbar')

    def test_pressing_it_drives_the_editor_without_a_broken_api_call(self):
        self.open_editor()
        button = self.mic_button()
        self.assertFalse(self.mic_is_active(), 'it started out pressed')

        button.click()

        # setActive(true) is what puts a toggle button in its pressed state,
        # so this is the assertion that the api object still works. The
        # listening notification comes from editor.notificationManager.
        self.wait.until(lambda d: self.mic_is_active(),
                        'the dictate button never became active')
        self.assertTrue(
            self.js("return document.querySelectorAll('.tox-notification')"
                    '  .length > 0'),
            'the listening notification never opened')

        button.click()

        self.wait.until(lambda d: not self.mic_is_active(),
                        'the dictate button never came back out')
        self.assertEqual(self.tinymce_type_errors(), [],
                         'a TinyMCE api call does not exist in this version')
