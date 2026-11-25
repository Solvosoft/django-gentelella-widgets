"""Browser tests for the form widgets of the catalog (/formwidgets/).

Every widget is used the way a person would and the form is saved: stars,
switch, range and range pair, combobox, popup LOV, Markdown with its preview,
image crop, QR and the geocoded address (with the demo's offline geocoder).
"""

import io
import shutil
import tempfile

from django.test import override_settings, tag
from PIL import Image

from demoapp.models import WidgetShowcase

from .base import EC, By, Keys, SeleniumTestCase

MEDIA = tempfile.mkdtemp(prefix='gt-formwidgets-')


def png(size=(300, 200)):
    buffer = io.BytesIO()
    Image.new('RGB', size, (20, 120, 200)).save(buffer, 'PNG')
    return buffer.getvalue()


@tag('selenium')
@override_settings(MEDIA_ROOT=MEDIA)
class FormWidgetsTest(SeleniumTestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def open(self):
        self.go('/formwidgets/')
        for name in ('StarRatingInput', 'RangeInput', 'ComboboxInput',
                     'LOVPopupSelect', 'MarkdownInput', 'ImageCropInput',
                     'QRCodeInput', 'GeocodedAddressInput'):
            self.assertEqual(
                self.assert_widget_ready('[data-widget="%s"]' % name), name)
        # The stars replace the number input once the javascript ran.
        self.wait_js("return !document.querySelector('#id_rating_rating "
                     ".gt-rating-stars').classList.contains('d-none')")

    def set_range(self, element_id, value):
        self.js("const e = document.getElementById(arguments[0]);"
                "e.value = arguments[1];"
                "e.dispatchEvent(new Event('input', {bubbles: true}));",
                element_id, value)

    def click(self, css):
        element = self.driver.find_element(By.CSS_SELECTOR, css)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", element)
        self.wait.until(EC.element_to_be_clickable(element))
        element.click()
        return element

    def test_fill_every_widget_and_save(self):
        self.open()
        d = self.driver
        d.find_element(By.ID, 'id_name').send_keys('Everything')

        # Stars: the fourth one.
        self.click('#id_rating_rating .gt-rating-star[data-value="4"]')
        self.assertEqual(self.js("return document.getElementById('id_rating').value"),
                         '4')
        self.assertEqual(len(d.find_elements(
            By.CSS_SELECTOR, '#id_rating_rating .gt-rating-on')), 4)

        # Switch: on by default, turned off.
        self.click('#id_active')
        self.assertFalse(self.js("return document.getElementById('id_active').checked"))

        # Range: the value beside it follows.
        self.set_range('id_volume', '80')
        self.assertEqual(d.find_element(By.ID, 'id_volume_value').text, '80 %')
        self.set_range('id_budget_0', '200')
        self.set_range('id_budget_1', '750')
        self.assertEqual(d.find_element(By.ID, 'id_budget_1_value').text, '750 $')

        # Combobox: a value that is not in the list, typed.
        self.click('#id_category + .select2')
        search = self.wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, '.select2-container--open .select2-search__field')))
        search.send_keys('Robots')
        self.wait_js("return [...document.querySelectorAll("
                     "'.select2-results__option')]"
                     ".some(o => o.textContent === 'Robots')")
        search.send_keys(Keys.ENTER)
        self.wait_js("return document.getElementById('id_category').value === 'Robots'")

        # Popup LOV: page 2, then a search, then a row.
        self.click('#id_product_open')
        self.wait_js("return document.querySelectorAll("
                     "'#id_product_results .gt-lov-popup-row').length === 10")
        self.click('#id_product_modal .gt-lov-popup-next')
        self.wait_js("return document.querySelector('#id_product_results "
                     ".gt-lov-popup-row').textContent === 'Producto 011'")
        d.find_element(By.ID, 'id_product_search').send_keys('042')
        self.wait_js("return document.querySelectorAll("
                     "'#id_product_results .gt-lov-popup-row').length === 1")
        self.click('#id_product_results .gt-lov-popup-row')
        self.wait_js("return !document.getElementById('id_product_modal')"
                     ".classList.contains('show')")
        self.assertEqual(self.js("return document.getElementById('id_product').value"),
                         'p042')
        self.assertEqual(d.find_element(By.ID, 'id_product_label')
                         .get_attribute('value'), 'Producto 042')
        self.wait_js("return !document.querySelector('.modal-backdrop')")

        # Markdown: the toolbar and the preview of the server.
        text = d.find_element(By.ID, 'id_description')
        text.send_keys('Some ')
        self.click('#id_description_markdown [data-md="bold"]')
        self.click('#id_description_previewtab')
        self.wait_js("return !!document.querySelector("
                     "'#id_description_preview strong')")
        self.assertEqual(d.find_element(
            By.CSS_SELECTOR, '#id_description_preview strong').text, 'texto en negrita')
        self.click('#id_description_write')
        self.assertTrue(text.is_displayed())

        # Image: crop to a square before it is sent.
        d.find_element(By.ID, 'id_photo').send_keys(
            self.write_temp_file('wide.png', png()))
        self.wait_js("return !!document.querySelector("
                     "'#id_photo_crop .cropper-container')")
        self.click('#id_photo_crop .gt-image-crop-apply')
        self.wait_js("return !document.querySelector('#id_photo_crop "
                     ".gt-image-crop-result').classList.contains('d-none')")
        self.assertEqual(self.js(
            "return document.getElementById('id_photo').files[0].type"), 'image/jpeg')

        # QR: drawn while typing.
        d.find_element(By.ID, 'id_code').send_keys('https://example.org/42')
        self.wait_js("return document.getElementById('id_code_qr').width > 0")

        # Address: the offline geocoder of the demo fills the map point.
        d.find_element(By.ID, 'id_address').send_keys('heredia')
        self.click('#id_address_geocode')
        self.wait_js("return !!document.querySelector('#id_address_places "
                     ".gt-geocode-place')")
        self.click('#id_address_places .gt-geocode-place')
        self.assertEqual(self.js("return document.getElementById('id_location').value"),
                         '9.998200,-84.116500')

        # requestSubmit(), not a click: at the bottom of a long page the
        # button can sit under the footer, and the browser still validates.
        self.js("document.getElementById('showcase_form').requestSubmit();")
        self.wait_js("return !!document.querySelector('#showcase_table tr[data-pk]')")

        item = WidgetShowcase.objects.get()
        self.assertEqual(
            (item.name, item.rating, item.active, item.volume, item.budget_min,
             item.budget_max, item.category, item.product, item.address,
             item.location),
            ('Everything', 4, False, 80, 200, 750, 'Robots', 'p042', 'heredia',
             '9.998200,-84.116500'))
        self.assertIn('**', item.description)
        self.assertEqual(item.code, 'https://example.org/42')
        with Image.open(item.photo.path) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertEqual(image.width, image.height)
            self.assertEqual(image.width, 200)

        # The list shows the Markdown cleaned and the code as a QR.
        self.wait_js("return !!document.querySelector('.showcase-description strong')")
        self.wait_js("return document.querySelector("
                     "'#showcase_table canvas[data-widget=\"QRCodeView\"]').width > 0")

    def test_the_qr_drawn_is_the_text(self):
        """The canvas decodes back to its text: the drawing is right, and jsQR
        (the fallback of the camera scan) reads it."""
        self.open()
        self.driver.find_element(By.ID, 'id_code').send_keys('Hola, ñandú 123')
        self.wait_js("return document.getElementById('id_code_qr').width > 0")
        self.js("gt_load_script(document.getElementById('id_code')"
                ".getAttribute('data-jsqr-lib')).then(() => window.__jsqr = true)")
        self.wait_js('return window.__jsqr === true')
        decoded = self.js(
            "const c = document.getElementById('id_code_qr');"
            "const data = c.getContext('2d').getImageData(0, 0, c.width, c.height);"
            "const code = jsQR(data.data, c.width, c.height);"
            "return code ? code.data : null;")
        self.assertEqual(decoded, 'Hola, ñandú 123')

    def test_the_preview_is_clean(self):
        self.open()
        self.js("const t = document.getElementById('id_description');"
                "t.value = arguments[0];",
                '**x** <img src="x" onerror="window.__xss = 1">'
                '<script>window.__xss = 2</script> [a](javascript:window.__xss=3)')
        self.click('#id_description_previewtab')
        self.wait_js("return !!document.querySelector("
                     "'#id_description_preview strong')")
        self.assertIsNone(self.js('return window.__xss || null'))
        self.assertEqual(self.js(
            "return document.querySelectorAll('#id_description_preview script,"
            " #id_description_preview [onerror], #id_description_preview "
            "a[href^=\"javascript\"]').length"), 0)

    def test_a_star_is_cleared_and_validation_is_on_the_server(self):
        self.open()
        self.click('#id_rating_rating .gt-rating-star[data-value="2"]')
        self.click('#id_rating_rating .gt-rating-clear')
        self.assertEqual(self.js("return document.getElementById('id_rating').value"),
                         '0')
        # Out of range by hand: the server says no.
        self.js("document.getElementById('id_rating').value = '9';")
        self.driver.find_element(By.ID, 'id_name').send_keys('Bad')
        # submit() skips the browser's own check of max="5".
        self.js("document.getElementById('showcase_form').submit();")
        self.wait_js("return !!document.querySelector('#id_rating_rating')"
                     " && !!document.querySelector('.errorlist')")
        self.assertEqual(self.js("return document.getElementById('id_name').value"),
                         'Bad')
        self.assertFalse(WidgetShowcase.objects.exists())
