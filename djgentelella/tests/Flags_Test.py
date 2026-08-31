import gzip
import re
from collections import Counter
from xml.etree import ElementTree

from django.template import Context, Template
from django.test import SimpleTestCase
from django.urls import NoReverseMatch, reverse

from djgentelella import __version__

from djgentelella.flags import (
    flag_url,
    get_flag_codes,
    get_index,
    get_sprite_bytes,
)
from djgentelella.management.commands.buildflagsprite import FLAGS, build_symbol

ID_ATTR = re.compile(r'\bid="([^"]+)"')


class SpriteTest(SimpleTestCase):
    """The sprite is committed, so these guard the file in the repository."""

    def test_every_flag_of_the_source_list_is_present(self):
        self.assertEqual(get_flag_codes(), frozenset(FLAGS))

    def test_sprite_is_well_formed_xml(self):
        raw = gzip.decompress(get_sprite_bytes())
        root = ElementTree.fromstring(raw)
        self.assertEqual(len(root), len(FLAGS))

    def test_every_symbol_has_a_viewbox(self):
        for code, (viewbox, _body) in get_index().items():
            self.assertEqual(len(viewbox.split()), 4, code)

    def test_no_id_is_shared_by_two_symbols(self):
        """The reason buildflagsprite namespaces ids.

        140 of the flags carry internal ids and 137 reference them through
        <use>, clip-path or fill, so a collision makes one flag borrow another's
        gradient -- and it renders, just wrongly.
        """
        raw = gzip.decompress(get_sprite_bytes()).decode('utf-8')
        repeated = [name for name, count in Counter(ID_ATTR.findall(raw)).items()
                    if count > 1]
        self.assertEqual(repeated, [])

    def test_no_reference_dangles(self):
        raw = gzip.decompress(get_sprite_bytes()).decode('utf-8')
        declared = set(ID_ATTR.findall(raw))
        referenced = (set(re.findall(r'url\(#([^)]+)\)', raw))
                      | set(re.findall(r'href="#([^"]+)"', raw)))
        self.assertEqual(sorted(referenced - declared), [])


class BuildSymbolTest(SimpleTestCase):
    def test_internal_ids_are_prefixed_with_the_code(self):
        symbol = build_symbol('cr', (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480">'
            '<defs><clipPath id="a"><path d="M0 0h640v480H0z"/></clipPath></defs>'
            '<g clip-path="url(#a)"><use xlink:href="#a"/></g></svg>'))
        self.assertIn('id="cr-a"', symbol)
        self.assertIn('url(#cr-a)', symbol)
        self.assertIn('href="#cr-a"', symbol)
        self.assertNotIn('id="a"', symbol)

    def test_root_viewbox_is_carried_over(self):
        symbol = build_symbol('xx', '<svg viewBox="0 0 60 40"><path/></svg>')
        self.assertIn('viewBox="0 0 60 40"', symbol)

    def test_a_root_without_viewbox_is_refused(self):
        # An error page saved as a flag looks exactly like this.
        with self.assertRaises(ValueError):
            build_symbol('xx', '<svg><path/></svg>')


class FlagIconViewTest(SimpleTestCase):
    def test_serves_one_flag(self):
        response = self.client.get(reverse('flag_icon', kwargs={'code': 'cr'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/svg+xml')
        self.assertTrue(response.content.startswith(b'<svg '))
        self.assertIn(b'</svg>', response.content)

    def test_hyphenated_and_long_codes_resolve(self):
        for code in ('gb-eng', 'es-ct', 'cefta'):
            with self.subTest(code=code):
                response = self.client.get(
                    reverse('flag_icon', kwargs={'code': code}))
                self.assertEqual(response.status_code, 200)

    def test_unknown_code_is_404_not_a_placeholder(self):
        response = self.client.get('/flags/zz.svg')
        self.assertEqual(response.status_code, 404)

    def test_path_traversal_does_not_match_the_pattern(self):
        for path in ('/flags/../secret.svg', '/flags/a/b.svg', '/flags/CR.svg'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
        with self.assertRaises(NoReverseMatch):
            reverse('flag_icon', kwargs={'code': '../etc/passwd'})

    def test_bare_request_returns_the_indexed_body_untouched(self):
        _viewbox, body = get_index()['cr']
        response = self.client.get('/flags/cr.svg')
        self.assertIn(body.encode('utf-8'), response.content)

    def test_size_sets_width_and_a_proportional_height(self):
        response = self.client.get('/flags/cr.svg?size=64')
        self.assertIn(b'width="64"', response.content)
        self.assertIn(b'height="48"', response.content)

    def test_a_junk_size_is_ignored_rather_than_crashing(self):
        response = self.client.get('/flags/cr.svg?size=huge')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.client.get('/flags/cr.svg').content)

    def test_shape_clips_to_a_square(self):
        response = self.client.get('/flags/cr.svg?shape=circle&size=48')
        body = response.content
        self.assertIn(b'<clipPath id="gtclip-cr-circle">', body)
        self.assertIn(b'<circle ', body)
        self.assertIn(b'viewBox="80 0 480 480"', body)
        self.assertIn(b'width="48"', body)
        self.assertIn(b'height="48"', body)

    def test_an_unknown_shape_is_ignored(self):
        response = self.client.get('/flags/cr.svg?shape=triangle')
        self.assertNotIn(b'clipPath', response.content)

    def test_title_is_escaped(self):
        response = self.client.get('/flags/cr.svg?title=%3Cscript%3Ex')
        self.assertIn(b'<title>&lt;script&gt;x</title>', response.content)
        self.assertNotIn(b'<script>', response.content)

    def test_caching_headers(self):
        response = self.client.get('/flags/cr.svg')
        self.assertEqual(response['Cache-Control'],
                         'public, max-age=31536000, immutable')
        self.assertTrue(response['ETag'])

    def test_etag_follows_the_parameters(self):
        plain = self.client.get('/flags/cr.svg')['ETag']
        sized = self.client.get('/flags/cr.svg?size=64')['ETag']
        self.assertNotEqual(plain, sized)


class FlagSpriteViewTest(SimpleTestCase):
    def test_served_still_gzipped_when_the_client_accepts_it(self):
        response = self.client.get(reverse('flag_sprite'),
                                   headers={'accept-encoding': 'gzip'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Encoding'], 'gzip')
        self.assertEqual(response.content, get_sprite_bytes())

    def test_decompressed_for_a_client_that_does_not(self):
        response = self.client.get(reverse('flag_sprite'),
                                   headers={'accept-encoding': 'identity'})
        self.assertNotIn('Content-Encoding', response)
        self.assertTrue(response.content.startswith(b'<svg '))
        self.assertIn(b'<symbol id="fi-cr"', response.content)


class FlagUrlTest(SimpleTestCase):
    def test_carries_the_package_version(self):
        self.assertEqual(flag_url('cr'), '/flags/cr.svg?v=%s' % __version__)

    def test_extra_parameters_are_encoded(self):
        url = flag_url('cr', size=32, shape='circle', v='x')
        self.assertEqual(url, '/flags/cr.svg?size=32&shape=circle&v=x')

    def test_the_url_it_builds_resolves(self):
        self.assertEqual(self.client.get(flag_url('cr')).status_code, 200)


class FlagTemplateTagTest(SimpleTestCase):
    def render(self, template, **context):
        return Template('{% load gtflags %}' + template).render(Context(context))

    def test_flag_renders_a_use_reference(self):
        html = self.render("{% flag 'cr' %}")
        self.assertIn('class="gt-flag"', html)
        self.assertIn('href="%s#fi-cr"' % reverse('flag_sprite'), html)

    def test_square_adds_its_class(self):
        html = self.render("{% flag 'cr' square=True %}")
        self.assertIn('gt-flag gt-flag-square', html)

    def test_unknown_code_renders_nothing(self):
        self.assertEqual(self.render("{% flag 'zz' %}"), '')

    def test_flag_url_tag_matches_the_helper(self):
        # The template engine escapes the & between parameters, which is what a
        # URL sitting in an HTML attribute should look like.
        self.assertEqual(self.render("{% flag_url 'cr' size=32 %}"),
                         flag_url('cr', size=32).replace('&', '&amp;'))
