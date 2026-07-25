from django.db import migrations

LEGACY_COLUMNS = ('_resume_rendered', '_content_rendered')


def get_existing_legacy_columns(schema_editor, table):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if table not in connection.introspection.table_names(cursor):
            return []
        columns = {
            field.name
            for field in connection.introspection.get_table_description(cursor, table)
        }
    return [column for column in LEGACY_COLUMNS if column in columns]


def drop_legacy_columns(apps, schema_editor):
    """Drop the companion columns django-markitup's MarkupField used to create.

    ``0001_initial`` no longer creates them, so on a fresh database there is
    nothing to do. Databases created before markitup was removed still carry
    them as NOT NULL columns, which would break every new insert.
    """
    table = apps.get_model('blog', 'Entry')._meta.db_table
    connection = schema_editor.connection
    for column in get_existing_legacy_columns(schema_editor, table):
        schema_editor.execute('ALTER TABLE %s DROP COLUMN %s' % (
            connection.ops.quote_name(table), connection.ops.quote_name(column)))


class Migration(migrations.Migration):
    dependencies = [
        ('blog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(drop_legacy_columns, migrations.RunPython.noop,
                             elidable=True),
    ]
