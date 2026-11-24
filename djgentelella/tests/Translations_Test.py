"""The Spanish catalog is complete and the interface speaks it."""
import gettext as gettext_module
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import mock, skipUnless

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import translation

import djgentelella
from djgentelella.authorization import validate_condition
from djgentelella.designs import engine, format, jsonschema, notifications, registry
from djgentelella.designs.data_components import ChartComponent
from djgentelella.designs.models import Page
from djgentelella.flows.callables import validate_callables
from djgentelella.flows.definitions import build_flow
from djgentelella.flows.taskforms import validate_task_forms
from djgentelella.flows.templatetags.gtflows import OUTCOME_LABELS, outcome_label
from djgentelella.management.commands.gtmakemessages import template_scripts
from djgentelella.tests.Designs_Test import DesignState, design, node
from djgentelella.tests.DesignsData_Test import product_form, table
from djgentelella.tests.FlowsV2_Test import versioned_document

LOCALE = Path(djgentelella.__file__).resolve().parent / 'locale' / 'es' / \
    'LC_MESSAGES'


def entries(path):
    """``(msgid, msgstr, flags)`` of each live entry of a .po file."""
    found, block = [], []
    for line in path.read_text(encoding='utf-8').split('\n') + ['']:
        if line.strip():
            block.append(line)
            continue
        if block and not all(item.startswith('#~') for item in block):
            found.append(_parse(block))
        block = []
    return [entry for entry in found if entry[0]]


def _parse(block):
    flags, parts, current = '', {}, None
    for line in block:
        if line.startswith('#,'):
            flags = line
        elif line.startswith('msg'):
            current, _space, text = line.partition(' ')
            parts[current] = [text]
        elif line.startswith('"') and current:
            parts[current].append(line)
    joined = {key: ''.join(item.strip()[1:-1] for item in value)
              for key, value in parts.items()}
    msgstr = joined.get('msgstr', joined.get('msgstr[0]', ''))
    return joined.get('msgid', ''), msgstr, flags


class CatalogTest(SimpleTestCase):
    def test_every_string_is_translated(self):
        for name in ('django.po', 'djangojs.po'):
            for msgid, msgstr, flags in entries(LOCALE / name):
                self.assertTrue(msgstr, '%s: %r is not translated' % (name, msgid))
                self.assertNotIn('fuzzy', flags, '%s: %r is fuzzy' % (name, msgid))

    #: Strings whose Spanish is the same text: the same word in both
    #: languages, a loanword the catalog uses throughout ("flag", "hash"),
    #: or a format with nothing to translate.
    SAME_IN_SPANISH = {
        'django.po': {'CC', 'Slug', 'Manual', 'Variables', 'No', 'hash',
                      'Error', 'Normal', '%(task)s: %(action)s.', 'Visible',
                      'Flag', 'Global', 'Error 403', 'Color', 'HTML',
                      'Decimal'},
        'djangojs.po': {'Error', 'No', 'Id', 'Slug', 'Total'},
    }

    def test_no_string_is_left_in_english(self):
        for name, same in self.SAME_IN_SPANISH.items():
            for msgid, msgstr, _flags in entries(LOCALE / name):
                if msgid == msgstr:
                    self.assertIn(msgid, same,
                                  '%s: %r is left in English' % (name, msgid))

    def test_typos_are_gone(self):
        text = (LOCALE / 'django.po').read_text(encoding='utf-8')
        for typo in ('Flitros', 'cerrar session', 'inesperado..'):
            self.assertNotIn(typo, text)


@skipUnless(shutil.which('msgfmt'), 'compiling the catalog needs gettext')
class SpanishInterfaceTest(SimpleTestCase):
    """The .mo files are not committed: the catalogs are compiled into a
    temporary directory, so the run leaves the source tree as it was."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        target = Path(cls.tmp.name) / 'es' / 'LC_MESSAGES'
        target.mkdir(parents=True)
        cls.catalogs = {}
        for domain in ('django', 'djangojs'):
            mo = target / ('%s.mo' % domain)
            # What ``make trans`` (compilemessages) does for this file.
            subprocess.run(['msgfmt', '--check', '-o', str(mo),
                            str(LOCALE / ('%s.po' % domain))], check=True)
            cls.catalogs[domain] = gettext_module.translation(
                domain, cls.tmp.name, ['es'])

    def es(self, text, domain='django'):
        return self.catalogs[domain].gettext(text)

    def test_facets_inbox_and_flags(self):
        expected = {
            'Filters': 'Filtros', 'Task inbox': 'Bandeja de tareas',
            'Claim': 'Tomar', 'Release': 'Liberar', 'Delegate': 'Delegar',
            'Approve': 'Aprobar', 'Reject': 'Rechazar', 'Empty': 'Vacío',
            'Designs': 'Diseños', 'Choose a file': 'Elija un archivo',
            'Feature flags': 'Flags de funcionalidad',
            '%(path)s is not an allowed callable.':
                '%(path)s no es un callable permitido.',
        }
        for text, spanish in expected.items():
            self.assertEqual(self.es(text), spanish)

    def test_the_javascript_catalog(self):
        for text, spanish in {'Clear all': 'Limpiar todo', 'Apply': 'Aplicar',
                              'Export': 'Exportar',
                              # pg_gettext is a keyword of gtmakemessages
                              'Add row': 'Agregar fila',
                              # an inline <script> of a template
                              'Replace content?': '¿Reemplazar el contenido?'}.items():
            self.assertEqual(self.es(text, 'djangojs'), spanish)

    def test_the_outcome_labels_are_in_the_catalog(self):
        with translation.override('en'):
            self.assertEqual(outcome_label('approve'), 'Approve')
            self.assertEqual(outcome_label('custom_outcome'), 'Custom_outcome')
            msgids = [str(label) for label in OUTCOME_LABELS.values()]
        for msgid in msgids:
            self.assertNotEqual(self.es(msgid), msgid)


def compile_catalogs(directory):
    """Compile the Spanish catalogs into ``directory``/es/LC_MESSAGES."""
    target = Path(directory) / 'es' / 'LC_MESSAGES'
    target.mkdir(parents=True)
    for domain in ('django', 'djangojs'):
        subprocess.run(['msgfmt', '--check', '-o', str(target / ('%s.mo' % domain)),
                        str(LOCALE / ('%s.po' % domain))], check=True)


@skipUnless(shutil.which('msgfmt'), 'compiling the catalog needs gettext')
class DocumentMessagesTest(SimpleTestCase):
    """The errors of design and flow documents, and the palette labels, speak
    the language of the request."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        compile_catalogs(cls.tmp.name)

    def setUp(self):
        locale = override_settings(LOCALE_PATHS=[self.tmp.name])
        locale.enable()
        self.addCleanup(locale.disable)
        engine.clear_cache()
        self.addCleanup(engine.clear_cache)

    def messages(self, language):
        document = design(node('no_such_component', 'x'))
        with translation.override(language):
            return {
                'resolve': engine.resolve(document)[1][0].message,
                'schema': jsonschema.validate({}, {'required': ['a']})[0].message,
                'envelope': format.validate_envelope([])[0].message,
                'condition': validate_condition({})[0].message,
                'callable': validate_callables({'transitions': [
                    {'name': 't', 'condition': 'os.system'}]})[0].message,
                'task_form': validate_task_forms({'states': [
                    {'type': 'human_task', 'form': 'os.system'}]})[0].message,
                'label': str(ChartComponent.label),
            }

    def test_in_spanish(self):
        self.assertEqual(self.messages('es'), {
            'resolve': "tipo de componente desconocido 'no_such_component'",
            'schema': "falta 'a', que es obligatorio",
            'envelope': 'un diseño debe ser un objeto JSON',
            'condition': 'condición vacía',
            'callable': 'os.system no es un callable '
                        'permitido (regístralo con register_callable o inclúyelo '
                        'en GT_FLOWS_ALLOWED_CALLABLES)',
            'task_form': 'os.system no es un formulario de tarea '
                         'permitido (regístralo con register_task_form o '
                         'inclúyelo en GT_FLOWS_ALLOWED_CALLABLES)',
            'label': 'Gráfico',
        })

    def test_in_english(self):
        messages = self.messages('en')
        self.assertEqual(messages['resolve'],
                         "unknown component type 'no_such_component'")
        self.assertEqual(messages['label'], 'Chart')

    def test_a_cached_page_keeps_one_resolution_per_language(self):
        document = design(node('no_such_component', 'x'))
        page = Page(path='x', document=document,
                    hash=format.document_hash(document))
        with translation.override('es'):
            spanish = engine.resolve_page(page)[1][0].message
        with translation.override('en'):
            english = engine.resolve_page(page)[1][0].message
        self.assertEqual(spanish, "tipo de componente desconocido 'no_such_component'")
        self.assertEqual(english, "unknown component type 'no_such_component'")


class TemplateScriptsTest(SimpleTestCase):
    def test_only_the_inline_scripts_are_kept_at_their_lines(self):
        source = ('<p>{% trans "Hi" %}</p>\n'
                  '<script src="x.js"></script>\n'
                  '<script>\n'
                  'var a = gettext("Keep"), b = "{% url \'x\' %}";\n'
                  '</script>\n')
        scripts = template_scripts(source)
        lines = scripts.split('\n')
        self.assertEqual(len(lines), len(source.split('\n')))
        self.assertEqual(lines[3].strip(),
                         'var a = gettext("Keep"), b = "0' + ' ' * 12 + '";')
        self.assertEqual(''.join(lines[:3]).strip(), '')
        self.assertNotIn('trans', scripts)

    def test_a_template_without_scripts_gives_nothing(self):
        self.assertEqual(template_scripts('<script src="a.js"></script><p>x</p>'),
                         '')


@skipUnless(shutil.which('xgettext') and shutil.which('msgmerge'),
            'makemessages needs gettext')
class MakeMessagesTest(SimpleTestCase):
    def test_javascript_strings_of_templates_and_pg_gettext_are_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'locale' / 'es' / 'LC_MESSAGES').mkdir(parents=True)
            (root / 'templates').mkdir()
            (root / 'templates' / 'page.html').write_text(
                '<h1>{% trans "Title" %}</h1>\n<script>\n'
                'alert(gettext("From a template"));\n</script>\n')
            (root / 'grid.js').write_text('pg_gettext("From a wrapper");\n')
            ignored = root / 'tests' / 'templates'
            ignored.mkdir(parents=True)
            (ignored / 'case.html').write_text(
                '<script>gettext("From an ignored template");</script>\n')
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                call_command('gtmakemessages', domain='djangojs', locale=['es'],
                             no_obsolete=True, ignore_patterns=['tests/*'],
                             verbosity=0)
            finally:
                os.chdir(cwd)
            catalog = (root / 'locale' / 'es' / 'LC_MESSAGES' /
                       'djangojs.po').read_text()
            self.assertFalse((root / 'gt_template_scripts').exists())
        self.assertIn('#: templates/page.html:3\nmsgid "From a template"', catalog)
        self.assertIn('msgid "From a wrapper"', catalog)
        self.assertNotIn('Title', catalog)
        self.assertNotIn('From an ignored template', catalog)


@skipUnless(shutil.which('msgfmt'), 'compiling the catalog needs gettext')
class NotificationMessagesTest(DesignState, TestCase):
    """The errors of a table's ``notify`` prop and of a flow's activities
    speak the language of the request."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        compile_catalogs(cls.tmp.name)

    def setUp(self):
        super().setUp()
        locale = override_settings(LOCALE_PATHS=[self.tmp.name])
        locale.enable()
        self.addCleanup(locale.disable)
        registry.get_components()  # exposes demoapp.Product

    def notify_errors(self, language, **kwargs):
        document = design(table(notify=[
            {'on': 'create', 'kind': 'notice', 'message': 'x',
             'to': ['field:name']},
            {'on': 'create', 'kind': 'notice', 'message': 'x', 'to': ['a@b.c']},
            {'on': 'create', 'kind': 'email', 'to': ['actor']},
            {'on': 'create', 'kind': 'email', 'to': ['actor'], 'code': 'one',
             'subject': 's', 'message': 'm'},
            {'on': 'update', 'kind': 'email', 'to': ['actor'], 'code': 'one',
             'subject': 's', 'message': '{{ object.name|no_such_filter }}'},
            {'on': 'update', 'kind': 'notice', 'to': ['actor']},
            {'on': 'update', 'kind': 'notice', 'to': ['actor'],
             'message': '{% load static %}'},
        ]), forms=product_form())
        with translation.override(language):
            return sorted(error.message for error in
                          engine.resolve(document, **kwargs)[1])

    def test_notify_errors_in_spanish(self):
        errors = self.notify_errors('es')
        self.assertEqual(len(errors), 7)
        for expected in (
                "'field:name' no es un usuario",
                'un aviso va a "actor" o a un "field:" que apunte a un usuario',
                'un correo necesita code, subject, message',
                "el código de correo 'one' se usa dos veces",
                'un aviso necesita un mensaje',
                'las etiquetas de plantilla ({% %}) necesitan un publicador de '
                'confianza para plantillas (GT_DESIGNS_ALLOW_TEMPLATES); usa solo '
                '{{ variables }}'):
            self.assertIn(expected, errors)
        self.assertTrue(any(error.startswith('error de plantilla: ')
                            for error in errors), errors)

    def test_notify_errors_in_english(self):
        errors = self.notify_errors('en')
        self.assertIn("email code 'one' is used twice", errors)
        self.assertIn('a notice needs a message', errors)
        self.assertTrue(any(error.startswith('template tags ({% %}) need')
                            for error in errors), errors)

    def test_email_without_async_notification_in_spanish(self):
        document = design(table(notify=[
            {'on': 'create', 'kind': 'email', 'to': ['actor'], 'code': 'one',
             'subject': 's', 'message': 'm'}]), forms=product_form())
        with mock.patch.object(notifications, 'async_notification_installed',
                               return_value=False), translation.override('es'):
            errors = [error.message for error in engine.resolve(document)[1]]
        self.assertEqual(errors, ['el correo necesita '
                                  'djgentelella.async_notification en '
                                  'INSTALLED_APPS'])

    def test_an_activity_with_unknown_keys_in_spanish(self):
        document = versioned_document('b')
        document['states'][1]['branches'] = ['a', 'b']
        with translation.override('es'), self.assertRaisesMessage(
                ImproperlyConfigured,
                "La actividad 'b' (state) no admite branches"):
            build_flow(document)
