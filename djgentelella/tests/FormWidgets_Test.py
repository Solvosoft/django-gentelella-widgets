"""The form widgets of the catalog (2.1): stars, switch, range, combobox,
popup LOV, Markdown, image crop, QR and geocoded address."""

import importlib.util
import io
import json
import re
import tempfile
from pathlib import Path
from unittest import mock, skipUnless

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from demoapp.formwidgets.forms import WidgetShowcaseForm
from demoapp.models import WidgetShowcase
import djgentelella
from djgentelella import geocoding
from djgentelella.fields.extras import RangePairField, RatingField
from djgentelella.fields.imagecrop import ImageCropField
from djgentelella.fields.lov import LOVChoiceField
from djgentelella.forms import widgetmap
from djgentelella.forms.forms import GTForm
from djgentelella.markdown import render_markdown
from djgentelella.widgets.extras import ComboboxInput, QRCodeInput, \
    RangeInput, RangePairInput, StarRatingInput, SwitchInput
from djgentelella.widgets.geocoding import GeocodedAddressInput
from djgentelella.widgets.imagecrop import ImageCropInput
from djgentelella.widgets.lov import LOVPopupSelect
from djgentelella.widgets.markdown import MarkdownInput

#: The [markdown] extra (test_requirements.txt installs it).
HAS_MARKDOWN = bool(importlib.util.find_spec('markdown')
                    and importlib.util.find_spec('nh3'))
NEEDS_MARKDOWN = skipUnless(HAS_MARKDOWN, 'needs the [markdown] extra')

NEW_WIDGETS = {
    'integer': ['StarRatingInput', 'RangeInput'],
    'decimal': ['RangeInput'],
    'float': ['RangeInput'],
    'boolean': ['SwitchInput'],
    'string': ['ComboboxInput', 'QRCodeInput', 'GeocodedAddressInput'],
    'url': ['QRCodeInput'],
    'text': ['MarkdownInput'],
    'image': ['ImageCropInput'],
}
#: What widget_choices() gave before these widgets: still the start of each list.
DEFAULTS = {
    'integer': 'NumberInput', 'decimal': 'FloatInput', 'float': 'FloatInput',
    'boolean': 'YesNoInput', 'string': 'TextInput', 'url': 'URLInput',
    'text': 'Textarea', 'image': 'ClearableFileInput',
}


def flat(html):
    """``html`` without the line breaks Django puts before a closing ``>``."""
    return re.sub(r'\s+>', '>', str(html))


def image_file(name='photo.png', fmt='PNG', size=(40, 30)):
    buffer = io.BytesIO()
    Image.new('RGB', size, (200, 30, 30)).save(buffer, fmt)
    content_type = {'PNG': 'image/png', 'JPEG': 'image/jpeg',
                    'BMP': 'image/bmp'}[fmt]
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


class WidgetMapTests(SimpleTestCase):
    def test_new_widgets_are_offered_at_the_end(self):
        for kind, keys in NEW_WIDGETS.items():
            choices = widgetmap.widget_choices(kind)
            self.assertEqual(choices[0], DEFAULTS[kind], kind)
            self.assertEqual(choices[-len(keys):], keys, kind)

    def test_each_builds_without_arguments_and_renders(self):
        for keys in NEW_WIDGETS.values():
            for key in keys:
                widget = widgetmap.widget_class(key)()
                html = widget.render('field', None, attrs={'id': 'id_field'})
                self.assertIn('data-widget="%s"' % key, html, key)

    def test_every_new_widget_has_its_javascript(self):
        source = Path(djgentelella.__file__).parent / 'static' / 'gentelella' / \
            'js' / 'widgets.js'
        text = source.read_text()
        for key in ['StarRatingInput', 'RangeInput', 'ComboboxInput', 'QRCodeInput',
                    'QRCodeView', 'GeocodedAddressInput', 'MarkdownInput',
                    'ImageCropInput', 'LOVPopupSelect']:
            self.assertIn('    %s: function' % key, text, key)


class StarRatingTests(SimpleTestCase):
    def test_renders_the_stars_lit_up_to_the_value(self):
        html = StarRatingInput(stars=4).render('rating', 3, attrs={'id': 'id_r'})
        self.assertEqual(html.count('data-value='), 4)
        self.assertEqual(html.count('gt-rating-star gt-rating-on'), 3)
        self.assertIn('max="4"', html)
        self.assertIn('gt-rating-clear', html)

    def test_the_stars_are_the_range_even_with_a_model_field(self):
        form_field = WidgetShowcase._meta.get_field('rating').formfield(
            widget=StarRatingInput)
        html = form_field.widget.render('rating', 2)
        self.assertIn('max="5"', html)
        self.assertNotIn('32767', html)

    def test_readonly(self):
        html = StarRatingInput(readonly=True).render('rating', 2)
        self.assertIn('data-readonly="true"', html)
        self.assertIn(' readonly', html)
        self.assertNotIn('gt-rating-clear', html)
        self.assertEqual(html.count(' disabled tabindex="-1"'), 5)

    def test_a_bad_value_draws_no_star(self):
        html = StarRatingInput().render('rating', 'abc')
        self.assertNotIn('gt-rating-on', html)

    def test_needs_a_star(self):
        with self.assertRaises(ValueError):
            StarRatingInput(stars=0)

    def test_field_validates_on_the_server(self):
        field = RatingField(stars=5, required=False, empty_value=0)
        self.assertEqual(field.clean('4'), 4)
        self.assertEqual(field.clean(''), 0)
        for bad in ('6', '-1', 'x'):
            with self.assertRaises(forms.ValidationError):
                field.clean(bad)
        self.assertIsNone(RatingField(required=False).clean(''))


class SwitchTests(SimpleTestCase):
    def test_render(self):
        html = SwitchInput(label='On').render('active', True, attrs={'id': 'id_a'})
        self.assertIn('form-check form-switch', html)
        self.assertIn('role="switch"', html)
        self.assertIn('class="form-check-input ', html)
        self.assertIn(' checked', html)
        self.assertIn('<label class="form-check-label" for="id_a">On</label>', html)
        self.assertNotIn(' checked', SwitchInput().render('active', False))

    def test_value(self):
        class Form(forms.Form):
            active = forms.BooleanField(required=False, widget=SwitchInput)

        self.assertTrue(Form({'active': 'on'}).is_valid())
        form = Form({'active': 'on'})
        form.is_valid()
        self.assertIs(form.cleaned_data['active'], True)
        form = Form({})
        form.is_valid()
        self.assertIs(form.cleaned_data['active'], False)


class RangeTests(SimpleTestCase):
    def test_render_shows_the_value(self):
        html = RangeInput(min_value=0, max_value=10, suffix=' %').render(
            'volume', 7, attrs={'id': 'id_v'})
        self.assertIn('type="range"', html)
        self.assertIn('class="form-range ', html)
        self.assertIn('>7 %</output>', html)
        self.assertIn('data-suffix=" %"', html)

    def test_constructor_wins_over_the_model_field(self):
        form_field = WidgetShowcase._meta.get_field('volume').formfield(
            widget=RangeInput(min_value=0, max_value=100))
        html = form_field.widget.render('volume', 5)
        self.assertIn('min="0"', html)
        self.assertIn('max="100"', html)
        self.assertNotIn('2147483647', html)

    def test_field_limits_reach_the_widget(self):
        field = forms.IntegerField(min_value=1, max_value=9, widget=RangeInput)
        html = field.widget.render('x', 3)
        self.assertIn('min="1"', html)
        self.assertIn('max="9"', html)

    def test_server_validation(self):
        class Form(forms.Form):
            volume = forms.IntegerField(min_value=0, max_value=100,
                                        widget=RangeInput)

        self.assertTrue(Form({'volume': '40'}).is_valid())
        self.assertFalse(Form({'volume': '140'}).is_valid())

    def test_pair(self):
        field = RangePairField(min_value=0, max_value=100, required=False)
        self.assertEqual(field.clean(['10', '30']), (10, 30))
        self.assertIsNone(field.clean(['', '']))
        with self.assertRaises(forms.ValidationError) as error:
            field.clean(['50', '20'])
        self.assertEqual(error.exception.code, 'order')
        with self.assertRaises(forms.ValidationError):
            field.clean(['10', '300'])

    def test_pair_decimal(self):
        field = RangePairField(min_value=0, max_value=1, decimal_places=2)
        self.assertEqual([str(v) for v in field.clean(['0.25', '0.5'])],
                         ['0.25', '0.5'])
        self.assertIn('step="0.01"', field.widget.render('p', None))

    def test_pair_widget(self):
        widget = RangePairInput(min_value=0, max_value=10)
        self.assertEqual(widget.decompress('2,8'), ['2', '8'])
        self.assertEqual(widget.decompress((1, 4)), [1, 4])
        self.assertEqual(widget.decompress(None), [None, None])
        html = widget.render('budget', (2, 8), attrs={'id': 'id_budget'})
        self.assertIn('name="budget_0"', html)
        self.assertIn('name="budget_1"', html)
        self.assertIn('>8</output>', html)


class ComboboxTests(SimpleTestCase):
    class Form(forms.Form):
        category = forms.CharField(max_length=10, required=False,
                                   widget=ComboboxInput(choices=['Red', 'Blue']))

    def test_a_listed_value(self):
        html = flat(self.Form(initial={'category': 'Blue'})['category'])
        self.assertIn('data-tags="true"', html)
        self.assertIn('<option value="Blue" selected>Blue</option>', html)
        self.assertEqual(html.count('selected'), 1)

    def test_a_typed_value_is_kept_and_rendered(self):
        form = self.Form({'category': 'Green'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['category'], 'Green')
        self.assertIn('<option value="Green" selected>Green</option>',
                      flat(form['category']))

    def test_escapes_a_typed_value(self):
        html = flat(self.Form({'category': '<b>x'})['category'])
        self.assertNotIn('<b>x', html)
        self.assertIn('&lt;b&gt;x', html)

    def test_the_length_is_checked(self):
        self.assertFalse(self.Form({'category': 'x' * 11}).is_valid())

    def test_pairs(self):
        widget = ComboboxInput(choices=[('r', 'Red')])
        self.assertIn('<option value="r">Red</option>',
                      flat(widget.render('c', '')))


class LOVPopupTests(TestCase):
    class Form(GTForm, forms.Form):
        product = LOVChoiceField('demo_products', widget=LOVPopupSelect,
                                 required=False)

    def test_render_shows_the_label_of_the_value(self):
        html = flat(self.Form(initial={'product': 'p007'})['product'])
        self.assertIn('data-widget="LOVPopupSelect"', html)
        self.assertIn('data-url="/gtapis/lov/demo_products/"', html)
        self.assertIn('value="Producto 007"', html)
        self.assertIn('<option value="p007" selected>Producto 007</option>', html)
        self.assertIn('class="modal fade gt-lov-popup-modal"', html)

    def test_validates_against_the_lov(self):
        form = self.Form({'product': 'p250'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['product'], 'p250')
        self.assertFalse(self.Form({'product': 'p999'}).is_valid())

    def test_endpoint_pages(self):
        user = get_user_model().objects.create_user('popup', password='x')
        self.client.force_login(user)
        url = reverse('gt-lov', args=['demo_products'])
        data = self.client.get(url, {'page': 2}).json()
        self.assertEqual(len(data['results']), 10)
        self.assertEqual(data['results'][0], {'id': 'p011', 'text': 'Producto 011'})
        self.assertTrue(data['pagination']['more'])
        data = self.client.get(url, {'q': '024'}).json()
        self.assertEqual(data['results'], [{'id': 'p024', 'text': 'Producto 024'}])
        self.assertFalse(data['pagination']['more'])


@NEEDS_MARKDOWN
class MarkdownTests(TestCase):
    ATTACKS = [
        '<script>alert(1)</script>',
        '<img src="x" onerror="alert(1)">',
        '[click](javascript:alert(1))',
        '<a href="javascript:alert(1)">x</a>',
        '<iframe src="https://example.org"></iframe>',
        '<div data-widget="MarkdownInput" onclick="alert(1)">x</div>',
        '<svg onload="alert(1)"></svg>',
    ]

    def assert_safe(self, html):
        lowered = html.lower()
        for needle in ('<script', 'onerror', 'onclick', 'onload', 'javascript:',
                       '<iframe', 'data-widget', '<svg'):
            self.assertNotIn(needle, lowered)

    def test_renders_markdown(self):
        html = render_markdown('# Title\n\n**bold** and _it_\n\n- a\n- b\n\n'
                               '| a | b |\n|---|---|\n| 1 | 2 |')
        self.assertIn('<h1>Title</h1>', html)
        self.assertIn('<strong>bold</strong>', html)
        self.assertIn('<li>a</li>', html)
        self.assertIn('<table>', html)

    def test_no_xss(self):
        for attack in self.ATTACKS:
            self.assert_safe(render_markdown(attack))
        self.assert_safe(render_markdown('\n\n'.join(self.ATTACKS)))

    def test_links_are_kept_safe(self):
        html = render_markdown('[site](https://example.org)')
        self.assertIn('href="https://example.org"', html)
        self.assertIn('rel="noopener noreferrer"', html)

    def test_empty(self):
        self.assertEqual(render_markdown(None), '')

    def test_filter(self):
        html = Template('{% load gtmarkdown %}{{ text|markdown }}').render(
            Context({'text': '**x** <script>alert(1)</script>'}))
        self.assertIn('<strong>x</strong>', html)
        self.assert_safe(html)

    def test_widget(self):
        html = MarkdownInput().render('text', '<b>keep</b>', attrs={'id': 'id_t'})
        self.assertIn('data-preview-url="/gtapis/markdown/preview/"', html)
        self.assertIn('&lt;b&gt;keep&lt;/b&gt;', html)
        self.assertIn('data-md="bold"', html)
        self.assertNotIn('data-md=', MarkdownInput(attrs={'readonly': True}).render(
            'text', ''))

    def test_preview_endpoint(self):
        url = reverse('gt-markdown-preview')
        self.assertEqual(self.client.post(url, {'text': 'x'}).status_code, 302)
        user = get_user_model().objects.create_user('md', password='x')
        self.client.force_login(user)
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, {'text': '**hi** ' + self.ATTACKS[1]})
        self.assertEqual(response.status_code, 200)
        self.assertIn('<strong>hi</strong>', response.json()['html'])
        self.assert_safe(response.json()['html'])
        with override_settings(GT_MARKDOWN_MAX_LENGTH=5):
            self.assertEqual(self.client.post(url, {'text': '123456'}).status_code,
                             413)

    def test_preview_needs_the_csrf_token(self):
        user = get_user_model().objects.create_user('mdcsrf', password='x')
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        response = client.post(reverse('gt-markdown-preview'), {'text': 'x'})
        self.assertEqual(response.status_code, 403)


class ImageCropTests(TestCase):
    class Form(forms.Form):
        photo = ImageCropField(max_size=50 * 1024, aspect_ratio=16 / 9)

    def test_widget_render(self):
        html = self.Form()['photo'].as_widget()
        self.assertIn('type="file"', html)
        self.assertIn('accept="image/*"', html)
        self.assertIn('data-widget="ImageCropInput"', html)
        self.assertIn('data-aspect-ratio="1.7777', html)
        self.assertIn('vendors/cropperjs/cropper.min.js', html)

    def test_accepts_an_image(self):
        form = self.Form({}, {'photo': image_file()})
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_a_file_that_is_not_an_image(self):
        fake = SimpleUploadedFile('photo.png', b'%PDF-1.4 not an image',
                                  content_type='image/png')
        form = self.Form({}, {'photo': fake})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()['photo'][0].code, 'invalid_image')

    def test_rejects_a_format(self):
        form = self.Form({}, {'photo': image_file('photo.bmp', 'BMP')})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()['photo'][0].code, 'format')

    def test_rejects_a_big_file(self):
        form = self.Form({}, {'photo': image_file(size=(800, 800), fmt='BMP',
                                                  name='big.bmp')})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()['photo'][0].code, 'size')

    @override_settings(GT_IMAGE_MAX_SIZE=10)
    def test_the_setting_is_the_default_limit(self):
        self.assertEqual(ImageCropField().max_size, 10)

    def test_edit_shows_the_current_image_and_can_clear_it(self):
        with tempfile.TemporaryDirectory() as media, \
                override_settings(MEDIA_ROOT=media):
            item = WidgetShowcase.objects.create(name='x', photo=image_file())
            html = WidgetShowcaseForm(instance=item)['photo'].as_widget()
            self.assertIn(item.photo.url, html)
            self.assertIn('name="photo-clear"', html)

    def test_plain_widget(self):
        html = ImageCropInput(output_type='image/png').render('p', None)
        self.assertIn('data-output-type="image/png"', html)
        self.assertNotIn('data-aspect-ratio', html)


class QRCodeTests(SimpleTestCase):
    def test_render(self):
        html = QRCodeInput(scan=True).render('code', 'ABC', attrs={'id': 'id_c'})
        self.assertIn('value="ABC"', html)
        self.assertIn('id="id_c_qr"', html)
        self.assertIn('id="id_c_scan"', html)
        self.assertIn('vendors/qrcode/qrcode.js', html)
        self.assertIn('vendors/jsqr/jsQR.js', html)

    def test_readonly_has_no_camera(self):
        html = QRCodeInput(scan=True, readonly=True).render(
            'code', 'ABC', attrs={'id': 'id_c'})
        self.assertIn(' readonly', html)
        self.assertNotIn('_scan', html)
        self.assertNotIn('jsQR', html)

    def test_template_tag_escapes_the_value(self):
        html = Template('{% load gtqrcode %}{% qrcode value 90 %}').render(
            Context({'value': '"><script>alert(1)</script>'}))
        self.assertIn('data-widget="QRCodeView"', html)
        self.assertIn('data-size="90"', html)
        self.assertNotIn('<script>', html)
        self.assertIn('&quot;&gt;&lt;script&gt;', html)


class FakeGeocoder(geocoding.Geocoder):
    def __init__(self, fail=False):
        self.fail = fail

    def search(self, query, limit=5):
        if self.fail:
            raise geocoding.GeocoderError('down')
        return [geocoding.Place('%s %d' % (query, n), 9.9 + n, -84.0)
                for n in range(8)][:limit]


FAKE = 'djgentelella.tests.FormWidgets_Test.FakeGeocoder'


class GeocodingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('geo', password='x')
        self.client.force_login(self.user)
        self.url = reverse('gt-geocode')

    @override_settings(GT_GEOCODER=None)
    def test_off_by_default(self):
        self.assertIsNone(geocoding.get_geocoder())
        self.assertEqual(self.client.get(self.url, {'q': 'x'}).status_code, 404)
        html = GeocodedAddressInput(point_field='location').render('address', '')
        self.assertNotIn('data-geocode-url', html)
        self.assertNotIn('gt-geocode-search', html)

    def test_default_setting(self):
        with self.settings():
            del settings.GT_GEOCODER
            self.assertIsNone(geocoding.get_geocoder())

    @override_settings(GT_GEOCODER=FAKE)
    def test_search(self):
        response = self.client.get(self.url, {'q': 'San José', 'limit': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'results': [
            {'label': 'San José 0', 'lat': 9.9, 'lng': -84.0,
             'point': '9.900000,-84.000000'},
            {'label': 'San José 1', 'lat': 10.9, 'lng': -84.0,
             'point': '10.900000,-84.000000'}]})
        self.assertEqual(len(self.client.get(self.url, {'q': 'x', 'limit': 99})
                             .json()['results']), 8)
        self.assertEqual(len(self.client.get(self.url, {'q': 'x', 'limit': 'a'})
                             .json()['results']), 5)

    @override_settings(GT_GEOCODER=FAKE)
    def test_errors(self):
        self.assertEqual(self.client.get(self.url, {'q': '  '}).status_code, 400)
        with override_settings(GT_GEOCODER_OPTIONS={'fail': True}):
            self.assertEqual(self.client.get(self.url, {'q': 'x'}).status_code, 502)
        self.assertEqual(Client().get(self.url, {'q': 'x'}).status_code, 302)
        self.assertEqual(self.client.post(self.url, {'q': 'x'}).status_code, 405)

    @override_settings(GT_GEOCODER=FAKE)
    def test_widget(self):
        html = GeocodedAddressInput(point_field='location', replace_text=True).render(
            'address', 'Calle 1', attrs={'id': 'id_address'})
        self.assertIn('data-geocode-url="/gtapis/geocode/"', html)
        self.assertIn('data-point-field="location"', html)
        self.assertIn('data-replace-text="true"', html)
        self.assertIn('id="id_address_geocode"', html)

    @override_settings(GT_GEOCODER='djgentelella.nope.Geocoder')
    def test_a_bad_path(self):
        with self.assertRaises(Exception):
            geocoding.get_geocoder()

    def test_nominatim_parses_without_network(self):
        rows = [{'display_name': 'San José', 'lat': '9.93', 'lon': '-84.08'},
                {'display_name': 'broken'}]
        response = mock.MagicMock()
        response.read.return_value = json.dumps(rows).encode()
        response.__enter__.return_value = response
        with mock.patch('djgentelella.geocoding.urlopen',
                        return_value=response) as urlopen:
            places = geocoding.NominatimGeocoder(
                url='https://geo.invalid/search', user_agent='tests',
                countrycodes='cr').search('San José', limit=3)
        request = urlopen.call_args[0][0]
        self.assertIn('countrycodes=cr', request.full_url)
        self.assertEqual(request.get_header('User-agent'), 'tests')
        self.assertEqual(places, [geocoding.Place('San José', 9.93, -84.08)])

    def test_nominatim_failure_is_a_geocoder_error(self):
        with mock.patch('djgentelella.geocoding.urlopen',
                        side_effect=OSError('no network')):
            with self.assertRaises(geocoding.GeocoderError):
                geocoding.NominatimGeocoder().search('x')


@NEEDS_MARKDOWN
class DemoPageTests(TestCase):
    """/formwidgets/: every widget of the catalog in one form, saved."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('demo', password='x')
        self.client.force_login(self.user)
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        override = override_settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)

    def test_page_renders_every_widget(self):
        html = self.client.get(reverse('formwidgets')).content.decode()
        for name in ('StarRatingInput', 'SwitchInput', 'RangeInput', 'ComboboxInput',
                     'LOVPopupSelect', 'MarkdownInput', 'ImageCropInput',
                     'QRCodeInput', 'GeocodedAddressInput', 'MapPointInput'):
            self.assertIn('data-widget="%s"' % name, html, name)
        self.assertIn('formwidgets.css', html)

    def test_save_and_edit(self):
        data = {
            'name': 'Demo', 'rating': '4', 'active': 'on', 'volume': '70',
            'budget_0': '100', 'budget_1': '600', 'category': 'Robots',
            'product': 'p042', 'description': '**hola** <script>x</script>',
            'code': 'https://example.org', 'address': 'San José, Costa Rica',
            'location': '9.932700,-84.087500', 'photo': image_file(),
        }
        response = self.client.post(reverse('formwidgets'), data)
        self.assertEqual(response.status_code, 302)
        item = WidgetShowcase.objects.get()
        self.assertEqual((item.rating, item.active, item.volume, item.budget_min,
                          item.budget_max, item.category, item.product),
                         (4, True, 70, 100, 600, 'Robots', 'p042'))
        self.assertTrue(item.photo.name.startswith('showcase/'))
        self.assertEqual(item.location, '9.932700,-84.087500')

        page = self.client.get(reverse('formwidgets')).content.decode()
        self.assertIn('<strong>hola</strong>', page)
        self.assertNotIn('<script>x</script>', page)

        edit = self.client.get(reverse('formwidgets-edit', args=[item.pk]))
        html = flat(edit.content.decode())
        self.assertIn('value="Producto 042"', html)
        self.assertIn('<option value="Robots" selected>Robots</option>', html)
        self.assertIn('value="600"', html)

    def test_invalid_values_are_rejected(self):
        data = {'name': 'Bad', 'rating': '9', 'volume': '50', 'product': 'zzz',
                'budget_0': '900', 'budget_1': '100',
                'photo': SimpleUploadedFile('x.png', b'nope', 'image/png')}
        response = self.client.post(reverse('formwidgets'), data)
        self.assertEqual(response.status_code, 200)
        errors = response.context['form'].errors
        self.assertEqual(set(errors), {'rating', 'product', 'budget', 'photo'})
        self.assertFalse(WidgetShowcase.objects.exists())
