"""``assets.css`` is cleaned, and ``design_endpoint`` follows the Site rule."""
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.test import RequestFactory, TestCase

from djgentelella.designs import engine
from djgentelella.designs.css import clean_css
from djgentelella.designs.models import Page
from djgentelella.tests.Designs_Test import design, node
from djgentelella.tests.DesignsData_Test import (
    ALL_PRODUCT_PERMS,
    DataDesignTestCase,
    product_form,
    table,
)

PAYLOADS = {
    '@import url(https://evil.example/x.css); p { color: red }': '@import',
    '@IMPORT "https://evil.example/x.css";': '@import',
    '@\\69mport "https://evil.example/x.css";': 'mport',
    '@im/**/port "x.css";': 'port',
    'p { width: expression(alert(1)) }': 'expression',
    'p { width: expr/* */ession(alert(1)) }': 'ession(',
    'p { width: \\65xpression(alert(1)) }': 'xpression',
    'p { background: url(javascript:alert(1)) }': 'javascript:',
    'p { background: url("JavaScript:alert(1)") }': 'javascript:',
    'p { background: url(java\tscript:alert(1)) }': 'script:',
    'p { background: url(\\6a avascript:alert(1)) }': 'avascript:',
    'p { background: url(vbscript:msgbox(1)) }': 'vbscript:',
    'p { background: url(javascript\\3a alert(1)) }': 'javascript',
    'p { width: expression\\28 alert(1)) }': 'expression',
    '\\40 import "x.css";': 'import',
    'p { -moz-binding: url(x.xml#xss) }': '-moz-binding',
    'p { behavior: url(x.htc) }': 'behavior',
}


class CleanCssTest(TestCase):
    def test_payloads_are_neutralized(self):
        for css, mark in PAYLOADS.items():
            cleaned = clean_css(css).lower()
            self.assertNotIn(mark, cleaned.replace('blocked', ''), css)
            self.assertNotIn('@import', cleaned, css)

    def test_nested_payloads_do_not_rejoin(self):
        # Removing a rule joins the text around it; the cleaning repeats.
        nested = [
            '@im@import x;port url(//evil.css);',
            '@imp@import a;ort "//evil.css";',
            '@im@im@import a;port b;port url(//evil.css);',
            '@\\69m@import a;port "//evil.css";',
            '@im/**/@import a;port "//evil.css";',
            '@im@\\69mport a;port "//evil.css";',
            '@i@import a;m@import b;port "//evil.css";',
            'p { background: url(java@import a;script:alert(1)) }',
            'p { width: expr@import a;ession(alert(1)) }',
        ]
        for css in nested:
            cleaned = clean_css(css).lower()
            self.assertNotIn('@import', cleaned, css)
            self.assertNotIn('evil', cleaned, css)
            self.assertNotIn('javascript:', cleaned, css)
            self.assertNotIn('expression(', cleaned, css)
            self.assertEqual(clean_css(cleaned), cleaned, css)

    def test_plain_css_is_kept(self):
        css = ('.card > .title::before { content: "\\f00c"; color: #fff; '
               'background: url(/static/x.png) no-repeat; }\n'
               '@media (max-width: 600px) { .md\\:flex { display: flex } }')
        self.assertEqual(clean_css(css), css)

    def test_what_is_not_a_string_gives_nothing(self):
        self.assertEqual(clean_css(None), '')
        self.assertEqual(clean_css({'a': 1}), '')

    def render(self, css, allow_js=False):
        document = design()
        document['assets'] = {'css': css, 'js': 'window.page_js = 1;'}
        resolved, errors = engine.resolve(document, allow_js=allow_js)
        self.assertEqual(errors, [])
        request = RequestFactory().get('/designs/sample')
        request.user = User.objects.create_user('viewer%d' % allow_js)
        return engine.render(resolved, request).content.decode()

    def test_the_page_serves_the_cleaned_css(self):
        content = self.render('@import "https://evil.example/x.css"; '
                              'p { width: expression(alert(1)) } </style><script>')
        self.assertNotIn('evil.example', content)
        self.assertNotIn('expression(', content)
        self.assertIn('<\\/style><script>', content)
        self.assertIn('p { width: blocked(alert(1)) }', content)

    def test_a_page_trusted_with_js_gets_its_css_as_written(self):
        content = self.render('@import "https://fonts.example/x.css";', allow_js=True)
        self.assertIn('@import "https://fonts.example/x.css";', content)
        self.assertIn('window.page_js = 1;', content)


class DesignEndpointSiteTest(DataDesignTestCase):
    """The pk of a page is not a way around the Site rule."""

    def setUp(self):
        super().setUp()
        self.grant(*ALL_PRODUCT_PERMS)
        self.site = Site.objects.create(domain='testserver', name='current')
        self.other = Site.objects.create(domain='other.example', name='other')

    def page(self, path, site=None):
        return self.publish(design(table(list_fields=['name']), forms=product_form()),
                            path=path, site=site)

    def get(self, page):
        return self.client.get(self.api(page, 'products'),
                               {'draw': 1, 'limit': 10, 'offset': 0})

    def test_a_page_of_another_site_is_not_served_by_its_pk(self):
        page = self.page('products', site=self.other)
        self.assertEqual(self.get(page).status_code, 404)

    def test_a_page_of_the_current_site_is_served(self):
        page = self.page('products', site=self.site)
        self.assertEqual(self.get(page).status_code, 200)

    def test_a_global_page_is_served(self):
        page = self.page('products')
        self.assertEqual(self.get(page).status_code, 200)

    def test_a_global_page_the_site_overrides_is_not_served(self):
        shadowed = self.page('products')
        own = self.page('products', site=self.site)
        self.assertEqual(self.get(shadowed).status_code, 404)
        self.assertEqual(self.get(own).status_code, 200)
        # Another global page, not overridden, still is.
        self.assertEqual(self.get(self.page('others')).status_code, 200)

    def test_without_a_site_the_global_page_is_served(self):
        page = self.page('products')
        self.page('products', site=self.other)
        Site.objects.filter(pk=self.site.pk).delete()
        Site.objects.clear_cache()
        self.assertEqual(self.get(page).status_code, 200)
        self.assertEqual(Page.objects.filter(path='products').count(), 2)
