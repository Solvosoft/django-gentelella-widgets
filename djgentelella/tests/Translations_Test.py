"""The Spanish catalog is complete and the interface speaks it."""
import gettext as gettext_module
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import skipUnless

from django.test import SimpleTestCase
from django.utils import translation

import djgentelella
from djgentelella.flows.templatetags.gtflows import OUTCOME_LABELS, outcome_label

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
                      'Flag', 'Global', 'Error 403', 'Color'},
        'djangojs.po': {'Error', 'No', 'Id', 'General'},
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
                              # kept by hand: pg_gettext is not extracted
                              'Add row': 'Agregar fila'}.items():
            self.assertEqual(self.es(text, 'djangojs'), spanish)

    def test_the_outcome_labels_are_in_the_catalog(self):
        with translation.override('en'):
            self.assertEqual(outcome_label('approve'), 'Approve')
            self.assertEqual(outcome_label('custom_outcome'), 'Custom_outcome')
            msgids = [str(label) for label in OUTCOME_LABELS.values()]
        for msgid in msgids:
            self.assertNotEqual(self.es(msgid), msgid)
