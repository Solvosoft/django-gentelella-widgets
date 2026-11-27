"""Translations of metadata (W34, C20): design pages, menu items and LOVs in
the active language, with the default language and the written text as the
fallback; their cache, export and import, screens and serializers."""

import copy
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from djgentelella import translations as core
from djgentelella.designs import engine, publishing
from djgentelella.designs import translations as design_translations
from djgentelella.designs.data_components import table_columns
from djgentelella.designs.models import Page
from djgentelella.lov import get_lov, register_lov, unregister_lov
from djgentelella.menu import export_tree, import_tree, validate_tree
from djgentelella.models import LOVTranslation, MenuItem
from djgentelella.tests.Designs_Test import design, html, node
from djgentelella.tests.DesignsData_Test import (
    DataDesignTestCase, load, product_form, table)
from djgentelella.translations import store, transfer

LANGUAGES = [('es', 'Español'), ('en', 'English'), ('pt-br', 'Português')]
FAST = ['django.contrib.auth.hashers.MD5PasswordHasher']
COOKIE = 'django_language'


def translated_design(**translations):
    document = design(
        node('stat', 'count', {'model': 'demoapp.Product', 'title': 'Productos',
                               'subtitle': 'en el catálogo'}),
        table(title='Catálogo', list_fields=['name', 'price'],
              column_labels={'name': 'Nombre', 'price': 'Precio'}),
        html('help', '<p>Hola</p>'),
        forms=product_form(), title='Catálogo traducido')
    document['translations'] = translations or {'en': {
        'meta.title': 'Translated catalogue', 'count:title': 'Products',
        'products:title': 'Catalogue', 'products:column_labels.name': 'Name'}}
    return document


@register_lov('w34_status', login_required=False)
def w34_status(request, q=''):
    return [row for row in [('a', 'Activo'), ('i', 'Inactivo'), ('x', 'Otro')]
            if q.lower() in row[1].lower()]


@override_settings(LANGUAGES=LANGUAGES, LANGUAGE_CODE='es')
class ResolutionTests(TestCase):
    def test_pick_follows_the_language_its_base_and_the_default(self):
        texts = {'en': 'Products', 'es': 'Productos'}
        self.assertEqual(core.pick(texts, 'written', 'en'), 'Products')
        self.assertEqual(core.pick(texts, 'written', 'en-us'), 'Products')
        # pt-br has none: the default language's translation.
        self.assertEqual(core.pick(texts, 'written', 'pt-br'), 'Productos')
        self.assertEqual(core.pick({'en': 'Products'}, 'written', 'pt-br'), 'written')
        self.assertEqual(core.pick({'en': '  '}, 'written', 'en'), 'written')
        self.assertEqual(core.pick(None, 'written', 'en'), 'written')
        with translation.override('en'):
            self.assertEqual(core.pick(texts, 'written'), 'Products')

    def test_unknown_languages_are_errors(self):
        self.assertEqual(core.validate_texts({'en': 'A', 'pt-br': 'B'}, '$'), [])
        with translation.override('en'):
            errors = [str(error) for error in core.validate_texts(
                {'fr': 'A', 'EN': 'B', 'en': 3}, '$')]
        self.assertEqual(len(errors), 3, errors)
        self.assertTrue(any('unknown language fr' in error for error in errors))

    @override_settings(GT_TRANSLATION_LANGUAGES=[('en', 'English')])
    def test_the_setting_narrows_the_languages(self):
        self.assertEqual(core.language_codes(), ['en'])
        self.assertTrue(core.validate_language('es', '$'))


@override_settings(LANGUAGES=LANGUAGES, LANGUAGE_CODE='es', PASSWORD_HASHERS=FAST)
class DesignTranslationTests(DataDesignTestCase):
    def resolved(self, document, language):
        with translation.override(language):
            resolved, errors = engine.resolve(document)
        self.assertEqual([str(error) for error in errors], [])
        return resolved

    def test_the_texts_a_document_may_translate(self):
        keys = [text.key for text in
                design_translations.translatable_texts(translated_design())]
        self.assertEqual(keys, ['meta.title', 'count:subtitle', 'count:title',
                                'products:column_labels.name',
                                'products:column_labels.price', 'products:title'])

    def test_title_and_column_label_in_two_languages_with_fallback(self):
        document = translated_design()
        english = self.resolved(document, 'en')
        self.assertEqual(english.title, 'Translated catalogue')
        self.assertEqual(english.nodes['count'].build.title, 'Products')
        # No translation of the subtitle: the written text.
        self.assertEqual(english.nodes['count'].build.props['subtitle'],
                         'en el catálogo')
        columns = {column['name']: column['title'] for column in
                   table_columns(english.nodes['products'].build)}
        self.assertEqual(columns, {'name': 'Name', 'price': 'Precio'})
        spanish = self.resolved(document, 'es')
        self.assertEqual(spanish.title, 'Catálogo traducido')
        self.assertEqual(spanish.nodes['count'].build.title, 'Productos')
        self.assertEqual({column['name']: column['title'] for column in
                          table_columns(spanish.nodes['products'].build)},
                         {'name': 'Nombre', 'price': 'Precio'})
        # The written document is not changed, and the hash is the page's.
        self.assertNotIn('Products', json.dumps(document['root']))
        self.assertEqual(english.hash, spanish.hash)

    def test_translate_false_keeps_the_written_texts(self):
        with translation.override('en'):
            resolved, errors = engine.resolve(translated_design(), translate=False)
        self.assertEqual(errors, [])
        self.assertEqual(resolved.title, 'Catálogo traducido')

    def test_what_cannot_be_translated(self):
        document = translated_design(
            en={'help:html': '<script>x</script>', 'products:model': 'auth.User',
                'products:column_labels.description': 'Nope', 'meta.url': 'x/'},
            fr={'meta.title': 'Catalogue'})
        with translation.override('en'):
            errors = self.errors(document)
        self.assertEqual(len(errors), 5, errors)
        self.assertTrue(any('unknown language fr' in error for error in errors))
        self.assertTrue(any('no translatable text help:html' in error
                            for error in errors))
        self.assertIsNone(publishing.publish(document)[0])

    def test_a_column_label_of_another_column_is_an_error(self):
        document = translated_design()
        del document['translations']
        document['root']['children'][0]['children'][0]['children'][1]['props'][
            'column_labels'] = {'status': 'Estado'}
        with translation.override('en'):
            errors = self.errors(document)
        self.assertTrue(any('not one of the columns' in error
                            for error in errors), errors)

    def test_a_heading_in_the_language_of_the_request(self):
        document = design(node('heading', 'top', {
            'title': 'Catálogo <b>', 'subtitle': 'Todo', 'level': 3}))
        document['translations'] = {'en': {'top:title': 'Catalogue <b>'}}
        self.publish(document, path='heading')
        url = reverse('gt-design-page', args=['heading'])
        content = self.client.get(url).content.decode()
        self.assertIn('<h3 class="mb-1">Catálogo &lt;b&gt;</h3>', content)
        self.assertIn('<p class="text-muted mb-0">Todo</p>', content)
        self.client.cookies[COOKIE] = 'en'
        content = self.client.get(url).content.decode()
        self.assertIn('<h3 class="mb-1">Catalogue &lt;b&gt;</h3>', content)
        # Untranslated, the subtitle stays as written.
        self.assertIn('Todo', content)

    def test_html_in_a_translation_is_escaped(self):
        self.grant('demoapp.view_product')
        evil = '<img src=x onerror=alert(1)>'
        document = translated_design(en={
            'meta.title': evil, 'count:title': evil, 'count:subtitle': evil,
            'products:title': evil, 'products:column_labels.name': evil})
        self.publish(document, path='translated')
        self.client.cookies[COOKIE] = 'en'
        response = self.client.get(reverse('gt-design-page', args=['translated']))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn(evil, content)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', content)

    def test_the_page_follows_the_language_and_the_cache_keeps_one_per_language(self):
        self.grant('demoapp.view_product')
        page = self.publish(translated_design(), path='translated')
        url = reverse('gt-design-page', args=['translated'])
        content = self.client.get(url).content.decode()
        self.assertIn('Catálogo traducido', content)
        self.client.cookies[COOKIE] = 'en'
        response = self.client.get(url)
        self.assertEqual(response.headers.get('Content-Language'), 'en')
        content = response.content.decode()
        self.assertIn('Translated catalogue', content)
        self.assertIn('Catalogue', content)
        with translation.override('en'):
            english = engine.resolve_page(page)
            self.assertIs(engine.resolve_page(page), english)
        with translation.override('es'):
            spanish = engine.resolve_page(page)
        self.assertIsNot(english, spanish)
        self.assertEqual(english[0].title, 'Translated catalogue')
        self.assertEqual(spanish[0].title, 'Catálogo traducido')

    def test_the_translations_travel_with_the_exported_page(self):
        page = self.publish(translated_design(), path='translated')
        data = publishing.export_page(page)
        self.assertEqual(data['document']['translations']['en']['count:title'],
                         'Products')
        data['document']['translations']['en']['count:title'] = 'Items'
        Page.objects.all().delete()
        imported, errors = publishing.import_page(data)
        self.assertEqual(errors, [])
        self.assertEqual(imported.document['translations']['en']['count:title'],
                         'Items')
        data['document']['translations']['de'] = {'count:title': 'Waren'}
        self.assertTrue(publishing.import_page(data)[1])

    def test_the_demo_page_resolves_in_both_languages(self):
        document = load('translated')
        self.assertEqual(self.resolved(document, 'en').title, 'Translated catalogue')
        self.assertEqual(self.resolved(document, 'es').title, 'Catálogo traducido')


MENU = '{% load gentelellamenu %}{% sidebar_menu %}{% top_menu %}'


@override_settings(LANGUAGES=LANGUAGES, LANGUAGE_CODE='es', PASSWORD_HASHERS=FAST)
class MenuTranslationTests(TestCase):
    def setUp(self):
        self.root = MenuItem.objects.create(
            title='Catálogo', url_name='/', category='sidebar', key='catalogue',
            translations={'en': 'Catalogue'})
        MenuItem.objects.create(
            title='Productos', url_name='/products/', category='sidebar',
            parent=self.root, key='products')
        self.user = User.objects.create_superuser('menu', password='x')

    def render(self, language):
        request = RequestFactory().get('/')
        request.user = self.user
        with translation.override(language):
            return Template(MENU).render(Context({'request': request}))

    def test_the_menu_in_two_languages_with_fallback(self):
        english = self.render('en')
        self.assertIn('Catalogue', english)
        self.assertIn('Productos', english)  # no translation: the title
        spanish = self.render('es')
        self.assertIn('Catálogo', spanish)
        self.assertNotIn('Catalogue', spanish)
        self.assertEqual(self.root.translated_title('en-gb'), 'Catalogue')

    def test_a_translated_title_is_escaped(self):
        MenuItem.objects.create(title='Top', url_name='/top/', category='main',
                                translations={'en': '<script>alert(1)</script>'})
        english = self.render('en')
        self.assertNotIn('<script>alert(1)', english)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', english)

    def test_the_model_validation(self):
        self.root.translations = {'xx': 'Nope'}
        with self.assertRaises(ValidationError) as raised:
            self.root.full_clean()
        self.assertIn('translations', raised.exception.message_dict)

    def test_the_translations_travel_with_the_menu(self):
        data = export_tree()
        self.assertEqual(data[0]['translations'], {'en': 'Catalogue'})
        # An item without translations exports as before.
        self.assertNotIn('translations', data[0]['children'][0])
        data[0]['children'][0]['translations'] = {'en': 'Products'}
        _roots, errors = import_tree(data)
        self.assertEqual(errors, [])
        self.assertEqual(MenuItem.objects.get(key='products').translations,
                         {'en': 'Products'})
        data[0]['translations'] = {'de': 'Katalog', 'en': 5}
        errors = [str(error) for error in validate_tree(data)]
        self.assertEqual(len(errors), 2, errors)
        self.assertIn('$[0].translations.de', errors[0])


@override_settings(LANGUAGES=LANGUAGES, LANGUAGE_CODE='es')
class LOVTranslationTests(TestCase):
    def setUp(self):
        LOVTranslation.objects.create(lov='w34_status', value='a', language='en',
                                      label='Active')
        LOVTranslation.objects.create(lov='w34_status', value='i', language='en',
                                      label='Inactive')
        LOVTranslation.objects.create(lov='w34_status', value='i', language='es',
                                      label='Desactivado')

    def test_a_value_in_two_languages_with_fallback(self):
        lov = get_lov('w34_status')
        with translation.override('en'):
            self.assertEqual(lov.page(None)[0], [('a', 'Active'), ('i', 'Inactive'),
                                                 ('x', 'Otro')])
            self.assertEqual(lov.label('i'), 'Inactive')
        with translation.override('pt-br'):
            # The default language's translation, then the label.
            self.assertEqual(lov.page(None)[0], [('a', 'Activo'),
                                                 ('i', 'Desactivado'),
                                                 ('x', 'Otro')])

    def test_the_endpoint_answers_in_the_language_of_the_request(self):
        url = reverse('gt-lov', args=['w34_status'])
        self.client.cookies[COOKIE] = 'en'
        results = self.client.get(url).json()['results']
        self.assertEqual([row['text'] for row in results],
                         ['Active', 'Inactive', 'Otro'])

    def test_the_rows_of_the_translation_screen(self):
        LOVTranslation.objects.create(lov='w34_status', value='gone', language='en',
                                      label='Gone')
        rows = store.lov_rows(get_lov('w34_status'))
        self.assertEqual([row[0] for row in rows], ['a', 'i', 'x', 'gone'])
        self.assertEqual(rows[1][2], {'en': 'Inactive', 'es': 'Desactivado'})

    def test_save_lov(self):
        self.assertEqual(store.save_lov('w34_status', {'a': {'en': ''},
                                                       'x': {'en': 'Other'}}), [])
        self.assertFalse(LOVTranslation.objects.filter(value='a').exists())
        self.assertEqual(LOVTranslation.objects.get(value='x').label, 'Other')
        self.assertTrue(store.save_lov('w34_status', {'x': {'fr': 'Autre'}}))
        self.assertTrue(store.save_lov('nope', {'x': {'en': 'Other'}}))

    def test_all_values_lists_what_needs_parents(self):
        register_lov('w34_child', depends_on=['parent'],
                     all_values=lambda request: [('c1', 'Uno')])(
            lambda request, parent=None, q='': [])
        try:
            self.assertEqual(get_lov('w34_child').values(), [('c1', 'Uno')])
        finally:
            unregister_lov('w34_child')


@override_settings(LANGUAGES=LANGUAGES, LANGUAGE_CODE='es', PASSWORD_HASHERS=FAST)
class TransferTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.site = Site.objects.create(domain='ventas.example.com', name='Ventas')
        self.page = self.publish(translated_design(), path='translated',
                                 site=self.site, user=self.user)
        self.item = MenuItem.objects.create(title='Catálogo', url_name='/',
                                            key='catalogue',
                                            translations={'en': 'Catalogue'})
        MenuItem.objects.create(title='Sin clave', url_name='/')
        LOVTranslation.objects.create(lov='w34_status', value='a', language='en',
                                      label='Active')

    def test_export(self):
        data = transfer.export_translations(languages=['en'])
        self.assertEqual(data['format'], 'djgentelella.translations')
        page = data['pages'][0]
        self.assertEqual((page['site'], page['path']),
                         ('ventas.example.com', 'translated'))
        texts = {text['key']: text for text in page['texts']}
        self.assertEqual(texts['count:title']['translations'], {'en': 'Products'})
        self.assertEqual(texts['count:subtitle'],
                         {'key': 'count:subtitle', 'original': 'en el catálogo',
                          'translations': {}})
        self.assertEqual(data['menus'], [{'site': None, 'key': 'catalogue',
                                          'original': 'Catálogo',
                                          'translations': {'en': 'Catalogue'}}])
        status = [row for row in data['lovs'] if row['lov'] == 'w34_status']
        self.assertEqual(status[0], {'lov': 'w34_status', 'value': 'a',
                                     'original': 'Activo',
                                     'translations': {'en': 'Active'}})
        only = transfer.export_translations(languages=['en'], empty=False)
        self.assertEqual([text['key'] for text in only['pages'][0]['texts']],
                         ['meta.title', 'count:title',
                          'products:column_labels.name', 'products:title'])

    def test_export_and_import_again(self):
        data = transfer.export_translations(languages=['en'])
        texts = {text['key']: text for text in data['pages'][0]['texts']}
        texts['count:subtitle']['translations'] = {'en': 'in the catalogue'}
        texts['count:title']['translations'] = {'en': ''}  # removed
        data['menus'][0]['translations'] = {'en': 'Catalog', 'pt-br': 'Catálogo'}
        for row in data['lovs']:
            if row['lov'] == 'w34_status' and row['value'] == 'i':
                row['translations'] = {'en': 'Inactive'}
        updated_by, written_hash = self.page.updated_by_id, self.page.hash
        summary, errors = transfer.import_translations(data)
        self.assertEqual(errors, [])
        self.assertEqual(summary['pages'], 1)
        self.page.refresh_from_db()
        english = self.page.document['translations']['en']
        self.assertEqual(english['count:subtitle'], 'in the catalogue')
        self.assertNotIn('count:title', english)
        self.assertEqual(english['meta.title'], 'Translated catalogue')
        # The publisher, and its trust, stay; the hash follows the document.
        self.assertEqual(self.page.updated_by_id, updated_by)
        self.assertNotEqual(self.page.hash, written_hash)
        self.item.refresh_from_db()
        self.assertEqual(self.item.translations, {'en': 'Catalog', 'pt-br': 'Catálogo'})
        self.assertEqual(LOVTranslation.objects.get(lov='w34_status', value='i').label,
                         'Inactive')

    def test_an_error_writes_nothing(self):
        data = transfer.export_translations(languages=['en'])
        data['menus'][0]['translations'] = {'en': 'Catalog'}
        data['lovs'].append({'lov': 'nope', 'value': 'a', 'translations': {}})
        data['pages'].append({'site': None, 'path': 'missing', 'texts': []})
        data['pages'][0]['texts'][0]['translations'] = {'fr': 'Catalogue'}
        with translation.override('en'):
            summary, errors = transfer.import_translations(data)
        self.assertIsNone(summary)
        messages = ' '.join(str(error) for error in errors)
        for expected in ('no LOV nope', 'no page missing', 'unknown language fr'):
            self.assertIn(expected, messages)
        self.item.refresh_from_db()
        self.assertEqual(self.item.translations, {'en': 'Catalogue'})
        # A key the page does not have is caught when it is saved, and
        # rolls the rest back too.
        data = transfer.export_translations(languages=['en'])
        data['menus'][0]['translations'] = {'en': 'Catalog'}
        data['pages'][0]['texts'].append({'key': 'help:html',
                                          'translations': {'en': '<b>x</b>'}})
        summary, errors = transfer.import_translations(data)
        self.assertIsNone(summary)
        self.assertIn('help:html', str(errors[0]))
        self.item.refresh_from_db()
        self.assertEqual(self.item.translations, {'en': 'Catalogue'})

    def test_dry_run(self):
        data = transfer.export_translations(languages=['en'])
        data['menus'][0]['translations'] = {'en': 'Catalog'}
        summary, errors = transfer.import_translations(data, dry_run=True)
        self.assertEqual(errors, [])
        self.assertEqual(summary['menus'], 1)
        self.item.refresh_from_db()
        self.assertEqual(self.item.translations, {'en': 'Catalogue'})
        self.assertTrue(transfer.validate_translations_data({'format': 'x'}))

    def test_the_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'translations.json'
            call_command('gttranslations_export', '--language', 'en', '--output',
                         str(path))
            data = json.loads(path.read_text(encoding='utf-8'))
            data['menus'][0]['translations'] = {'en': 'Catalog'}
            path.write_text(json.dumps(data), encoding='utf-8')
            output = StringIO()
            call_command('gttranslations_import', str(path), stdout=output)
            self.assertIn('Imported', output.getvalue())
            data['menus'][0]['translations'] = {'xx': 'Catalog'}
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(CommandError):
                call_command('gttranslations_import', str(path))
        with self.assertRaises(CommandError):
            call_command('gttranslations_export', '--language', 'xx')
        self.item.refresh_from_db()
        self.assertEqual(self.item.translations, {'en': 'Catalog'})


@override_settings(LANGUAGES=LANGUAGES, LANGUAGE_CODE='en', PASSWORD_HASHERS=FAST)
class ScreenTests(DataDesignTestCase):
    def setUp(self):
        super().setUp()
        self.page = self.publish(translated_design(), path='translated',
                                 user=self.user)
        self.item = MenuItem.objects.create(title='Catálogo', url_name='/',
                                            key='catalogue')

    def test_permissions(self):
        for name, args in (('gt_translations', []), ('gt_translations_menu', []),
                           ('gt_translations_page', [self.page.pk]),
                           ('gt_translations_lov', ['w34_status']),
                           ('gt_translations_missing', ['en']),
                           ('gt_translations_export', [])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code,
                             403, name)
        self.grant('djgentelella.change_menuitem')
        response = self.client.get(reverse('gt_translations'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'w34_status')
        self.assertEqual(self.client.get(reverse(
            'gt_translations_page', args=[self.page.pk])).status_code, 403)
        # A file with pages needs the page permission.
        upload = SimpleUploadedFile('t.json', json.dumps({
            'format': 'djgentelella.translations', 'version': 1,
            'pages': [{'path': 'translated', 'texts': []}]}).encode())
        self.assertEqual(self.client.post(reverse('gt_translations_import'),
                                          {'file': upload}).status_code, 403)

    def test_the_page_screen(self):
        self.grant('gtdesigns.change_page')
        url = reverse('gt_translations_page', args=[self.page.pk])
        response = self.client.get(url)
        self.assertContains(response, 'value="Products"')
        texts = design_translations.translatable_texts(self.page.document)
        data = {'count': len(texts)}
        for index, text in enumerate(texts):
            data['k%d' % index] = text.key
            data['v%d_en' % index] = '<b>%s</b>' % text.key \
                if text.key == 'count:subtitle' else ''
            data['v%d_pt-br' % index] = 'Produtos' if text.key == 'count:title' else ''
        response = self.client.post(url, data)
        self.assertRedirects(response, url, fetch_redirect_response=False)
        self.page.refresh_from_db()
        self.assertEqual(self.page.document['translations'], {
            'en': {'count:subtitle': '<b>count:subtitle</b>'},
            'pt-br': {'count:title': 'Produtos'}})
        self.assertEqual(self.page.updated_by_id, self.user.pk)
        # Shown escaped in the screen too.
        response = self.client.get(url)
        self.assertContains(response, 'value="&lt;b&gt;count:subtitle&lt;/b&gt;"')
        # A key the page does not have is refused, nothing saved.
        data['k0'] = 'help:html'
        data['v0_en'] = 'Nope'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.page.refresh_from_db()
        self.assertNotIn('help:html', json.dumps(self.page.document['translations']))

    def test_the_menu_and_lov_screens(self):
        self.grant('djgentelella.change_menuitem',
                   'djgentelella.change_lovtranslation')
        url = reverse('gt_translations_menu')
        self.assertContains(self.client.get(url), 'Catálogo')
        self.client.post(url, {'count': 1, 'k0': str(self.item.pk),
                               'v0_en': 'Catalogue', 'v0_es': ''})
        self.item.refresh_from_db()
        self.assertEqual(self.item.translations, {'en': 'Catalogue'})
        url = reverse('gt_translations_lov', args=['w34_status'])
        self.assertContains(self.client.get(url), 'Inactivo')
        self.client.post(url, {'count': 1, 'k0': 'i', 'v0_en': 'Inactive'})
        self.assertEqual(LOVTranslation.objects.get(lov='w34_status').label,
                         'Inactive')
        self.assertEqual(self.client.get(reverse(
            'gt_translations_lov', args=['nope'])).status_code, 404)

    def test_missing_export_and_import(self):
        self.grant('gtdesigns.change_page', 'djgentelella.change_menuitem',
                   'djgentelella.change_lovtranslation')
        response = self.client.get(reverse('gt_translations_missing', args=['en']))
        self.assertContains(response, 'count:subtitle')
        self.assertNotContains(response, '<code>count:title</code>')
        self.assertContains(response, 'Catálogo')
        self.assertEqual(self.client.get(reverse(
            'gt_translations_missing', args=['xx'])).status_code, 404)
        response = self.client.get(reverse('gt_translations_export') +
                                   '?language=en')
        self.assertEqual(response['Content-Type'], 'application/json; charset=utf-8')
        data = json.loads(response.content)
        data['menus'][0]['translations'] = {'en': 'Catalogue'}
        upload = SimpleUploadedFile('t.json', json.dumps(data).encode())
        response = self.client.post(reverse('gt_translations_import'),
                                    {'file': upload})
        self.assertRedirects(response, reverse('gt_translations'),
                             fetch_redirect_response=False)
        self.item.refresh_from_db()
        self.assertEqual(self.item.translations, {'en': 'Catalogue'})
        bad = copy.deepcopy(data)
        bad['menus'][0]['translations'] = {'xx': 'Nope'}
        upload = SimpleUploadedFile('t.json', json.dumps(bad).encode())
        response = self.client.post(reverse('gt_translations_import'),
                                    {'file': upload}, follow=True)
        self.assertContains(response, 'unknown language xx')
        upload = SimpleUploadedFile('t.json', b'not json')
        response = self.client.post(reverse('gt_translations_import'),
                                    {'file': upload}, follow=True)
        self.assertContains(response, 'not valid JSON')


@register_lov('w34_secret', perms=['auth.view_user'])
def w34_secret(request, q=''):
    return [('s', 'Secreto')]


def translations_file(**sections):
    return SimpleUploadedFile('t.json', json.dumps(dict(
        {'format': 'djgentelella.translations', 'version': 1},
        **sections)).encode())


@override_settings(LANGUAGES=LANGUAGES, LANGUAGE_CODE='es')
class ScreenScopeTests(DataDesignTestCase):
    """The screens see the LOVs the user may open and the objects of the
    request's Site (and the global ones), as the design pages do (D22)."""

    def setUp(self):
        super().setUp()
        self.other = Site.objects.create(domain='otro.example.com', name='Otro')
        self.page = self.publish(translated_design(), path='translated',
                                 user=self.user)
        self.foreign_page = self.publish(translated_design(), path='foreign',
                                         site=self.other, user=self.user)
        self.item = MenuItem.objects.create(title='Catálogo', url_name='/',
                                            key='catalogue')
        self.foreign_item = MenuItem.objects.create(
            title='Ajeno', url_name='/ajeno', key='foreign', site=self.other)

    def test_import_needs_the_permission_of_each_lov(self):
        # The reproduction: the screen of w34_secret is a 403, but its labels
        # were rewritten through the import.
        self.grant('djgentelella.change_lovtranslation')
        self.assertEqual(self.client.get(reverse(
            'gt_translations_lov', args=['w34_secret'])).status_code, 403)
        response = self.client.post(reverse('gt_translations_import'), {
            'file': translations_file(lovs=[{
                'lov': 'w34_secret', 'value': 's',
                'translations': {'en': 'Hacked'}}])}, follow=True)
        self.assertContains(response, 'w34_secret')
        self.assertFalse(LOVTranslation.objects.filter(lov='w34_secret').exists())
        request = RequestFactory().get('/')
        request.user = self.user
        summary, errors = transfer.import_translations({
            'format': 'djgentelella.translations', 'version': 1,
            'lovs': [{'lov': 'w34_secret', 'value': 's',
                      'translations': {'en': 'Hacked'}}]}, request=request)
        self.assertIsNone(summary)
        self.assertEqual([error.path for error in errors], ['$.lovs[0]'])
        # Without a request (the command), every LOV, as before.
        summary, errors = transfer.import_translations({
            'format': 'djgentelella.translations', 'version': 1,
            'lovs': [{'lov': 'w34_secret', 'value': 's',
                      'translations': {'en': 'Secret'}}]})
        self.assertEqual(errors, [])
        self.assertEqual(LOVTranslation.objects.get(lov='w34_secret').label,
                         'Secret')

    def test_the_menu_screen_shows_and_saves_only_this_site(self):
        self.grant('djgentelella.change_menuitem')
        url = reverse('gt_translations_menu')
        response = self.client.get(url)
        self.assertContains(response, 'Catálogo')
        self.assertNotContains(response, 'Ajeno')
        self.client.post(url, {'count': 2, 'k0': str(self.foreign_item.pk),
                               'v0_en': 'Hacked', 'k1': str(self.item.pk),
                               'v1_en': 'Catalogue'})
        self.foreign_item.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(self.foreign_item.translations, {})
        self.assertEqual(self.item.translations, {'en': 'Catalogue'})

    def test_a_page_of_another_site_is_not_found(self):
        self.grant('gtdesigns.change_page')
        self.assertEqual(self.client.get(reverse(
            'gt_translations_page', args=[self.foreign_page.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse(
            'gt_translations_page', args=[self.page.pk])).status_code, 200)
        response = self.client.get(reverse('gt_translations'))
        self.assertContains(response, 'translated')
        self.assertNotContains(response, 'foreign')

    def test_missing_export_and_import_of_this_site(self):
        self.grant('gtdesigns.change_page', 'djgentelella.change_menuitem')
        MenuItem.objects.create(title='Sin clave ajeno', url_name='/x',
                                site=self.other)
        response = self.client.get(reverse('gt_translations_missing', args=['en']))
        self.assertContains(response, 'Catálogo')
        self.assertNotContains(response, 'Ajeno')
        self.assertNotContains(response, 'Sin clave ajeno')
        self.assertNotContains(response, 'foreign')
        data = json.loads(self.client.get(reverse('gt_translations_export')).content)
        self.assertEqual([entry['key'] for entry in data['menus']], ['catalogue'])
        self.assertEqual([entry['path'] for entry in data['pages']], ['translated'])
        response = self.client.post(reverse('gt_translations_import'), {
            'file': translations_file(menus=[{
                'site': 'otro.example.com', 'key': 'foreign',
                'translations': {'en': 'Hacked'}}])}, follow=True)
        self.assertContains(response, 'foreign')
        self.foreign_item.refresh_from_db()
        self.assertEqual(self.foreign_item.translations, {})
        # The command still exports every Site.
        data = transfer.export_translations()
        self.assertEqual(sorted(entry['key'] for entry in data['menus']),
                         ['catalogue', 'foreign'])


@override_settings(LANGUAGES=LANGUAGES, LANGUAGE_CODE='es')
class MalformedSaveTests(DataDesignTestCase):
    """``save_lov`` and ``save_page`` called from code with what is not
    ``{key: {language: text}}``: errors, never an exception."""

    def test_save_lov(self):
        # The reproduction: {'a': None} passed validation and crashed.
        for update in ({'a': None}, {'a': 'Active'}, {'a': ['en']}):
            errors = store.save_lov('w34_status', update)
            self.assertTrue(errors, update)
        self.assertEqual(store.save_lov('w34_status', {'a': {'en': 5}})[0].path,
                         "$['a'].en")
        self.assertFalse(LOVTranslation.objects.exists())

    def test_save_page(self):
        # The reproduction: a translation 5 raised AttributeError in merge().
        page = self.publish(translated_design(), path='malformed', user=self.user)
        before = copy.deepcopy(page.document)
        for update in ({'en': {'count:title': 5}}, {'en': {'count:title': ['x']}}):
            with translation.override('en'):
                errors = store.save_page(page, update)
                self.assertEqual([str(error.message) for error in errors],
                                 ['a translation is a text'], update)
        page.refresh_from_db()
        self.assertEqual(page.document, before)
