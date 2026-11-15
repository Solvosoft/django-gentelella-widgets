"""``0022_site_scoping`` refuses duplicated global settings instead of
deleting them."""
from importlib import import_module

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

migration = import_module('djgentelella.migrations.0022_site_scoping')

BEFORE = [('djgentelella', '0021_flows')]
TABLE = 'djgentelella_gentelellasettings'
KEYS = ['theme', 'single']


class SiteScopingMigrationTest(TransactionTestCase):
    """Migrates the app back, so it cannot run in the usual transaction."""

    def migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return executor

    def latest(self):
        executor = MigrationExecutor(connection)
        return [key for key in executor.loader.graph.leaf_nodes()
                if key[0] == 'djgentelella']

    def columns(self):
        with connection.cursor() as cursor:
            return [column.name for column in connection.introspection
                    .get_table_description(cursor, TABLE)]

    def setUp(self):
        self.addCleanup(self.restore)
        executor = self.migrate(BEFORE)
        old = executor.loader.project_state(BEFORE).apps
        settings_model = old.get_model('djgentelella', 'GentelellaSettings')
        settings_model.objects.create(key='theme', value='dark')
        settings_model.objects.create(key='theme', value='light')
        settings_model.objects.create(key='single', value='1')

    def restore(self):
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM %s WHERE %s IN (%%s, %%s)' % (
                connection.ops.quote_name(TABLE), connection.ops.quote_name('key')),
                KEYS)
        self.migrate(self.latest())

    def rows(self):
        """The rows of this test: the demo seeds settings of its own."""
        with connection.cursor() as cursor:
            cursor.execute('SELECT %s, value FROM %s WHERE %s IN (%%s, %%s) '
                           'ORDER BY id' % (connection.ops.quote_name('key'),
                                            connection.ops.quote_name(TABLE),
                                            connection.ops.quote_name('key')),
                           KEYS)
            return [tuple(row) for row in cursor.fetchall()]

    def test_duplicates_stop_the_migration_and_nothing_is_deleted(self):
        with self.assertRaises(migration.DuplicateGlobalSettings) as raised:
            self.migrate([('djgentelella', '0022_site_scoping')])
        message = str(raised.exception)
        self.assertIn("key='theme'", message)
        self.assertIn("value='dark'", message)
        self.assertIn("value='light'", message)
        self.assertNotIn("key='single'", message)
        self.assertEqual(self.rows(), [('theme', 'dark'), ('theme', 'light'),
                                       ('single', '1')])
        # Rolled back as a whole: the column it added first is gone too.
        self.assertNotIn('site_id', self.columns())

    def test_once_resolved_it_migrates(self):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM %s WHERE value = 'light'"
                           % connection.ops.quote_name(TABLE))
        self.migrate([('djgentelella', '0022_site_scoping')])
        self.assertIn('site_id', self.columns())
        self.assertEqual(self.rows(), [('theme', 'dark'), ('single', '1')])
