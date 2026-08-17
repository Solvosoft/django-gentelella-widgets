"""The upgrade path off django-markitup.

``blog.0002`` only does anything on a database created before markitup was
removed, so on a fresh database -- CI's, and every developer's -- its body never
runs. That is precisely the case worth testing: the legacy columns hold the only
rendered HTML there is, and dropping them without moving it over first leaves
every entry showing its markdown source.
"""
from importlib import import_module

from django.apps import apps
from django.db import connection
from django.test import TransactionTestCase

from djgentelella.blog.models import Entry

migration = import_module(
    'djgentelella.blog.migrations.0002_drop_markitup_rendered_columns')

CONTENT_HTML = '<h2>Titulo</h2>\n<p><strong>negrita</strong></p>'
RESUME_HTML = '<p><strong>corto</strong></p>'


class DropMarkitupColumnsTestCase(TransactionTestCase):
    """Raw DDL, so this cannot run inside the usual test transaction."""

    def setUp(self):
        self.table = Entry._meta.db_table
        self.addCleanup(self.drop_legacy_columns_if_left_over)

    def legacy_columns(self):
        with connection.schema_editor() as schema_editor:
            return migration.get_existing_legacy_columns(schema_editor,
                                                         self.table)

    def drop_legacy_columns_if_left_over(self):
        """A failed assertion must not leave the columns behind for the next
        test in the run."""
        for column in self.legacy_columns():
            with connection.cursor() as cursor:
                cursor.execute('ALTER TABLE %s DROP COLUMN %s' % (
                    connection.ops.quote_name(self.table),
                    connection.ops.quote_name(column)))

    def add_legacy_columns(self):
        """Put the table back the way markitup's MarkupField left it."""
        with connection.cursor() as cursor:
            for column in ('_content_rendered', '_resume_rendered'):
                cursor.execute(
                    "ALTER TABLE %s ADD COLUMN %s text NOT NULL DEFAULT ''" % (
                        connection.ops.quote_name(self.table),
                        connection.ops.quote_name(column)))

    def run_migration(self):
        with connection.schema_editor() as schema_editor:
            migration.drop_legacy_columns(apps, schema_editor)

    def test_the_rendered_html_is_kept_and_the_columns_go(self):
        # markitup stored the markdown source in the visible column and the
        # rendered html in the companion one
        entry = Entry.objects.create(title='Hola',
                                     content='## Titulo\n\n**negrita**',
                                     resume='**corto**')
        self.add_legacy_columns()
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE %s SET _content_rendered = %%s, _resume_rendered = %%s'
                % connection.ops.quote_name(self.table),
                [CONTENT_HTML, RESUME_HTML])

        self.run_migration()

        entry.refresh_from_db()
        self.assertEqual(entry.content, CONTENT_HTML)
        self.assertEqual(entry.resume, RESUME_HTML)
        self.assertEqual(self.legacy_columns(), [])

    def test_an_entry_written_after_the_switch_is_left_alone(self):
        # its rendered columns are empty (the '' default), and overwriting a
        # real body with that would be the same data loss in reverse
        entry = Entry.objects.create(title='Nueva', content='<p>ya es html</p>',
                                     resume='<p>resumen</p>')
        self.add_legacy_columns()

        self.run_migration()

        entry.refresh_from_db()
        self.assertEqual(entry.content, '<p>ya es html</p>')
        self.assertEqual(entry.resume, '<p>resumen</p>')

    def test_a_fresh_database_is_a_no_op(self):
        entry = Entry.objects.create(title='Fresca', content='<p>html</p>')
        self.assertEqual(self.legacy_columns(), [])

        self.run_migration()   # must not raise

        entry.refresh_from_db()
        self.assertEqual(entry.content, '<p>html</p>')
