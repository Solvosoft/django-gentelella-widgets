from django.db import migrations

# markitup's MarkupField kept the source in the visible column and the rendered
# HTML in a companion ``_<field>_rendered`` one. The fields are plain TextFields
# now and hold HTML directly, so the rendered column is the value to keep.
LEGACY_COLUMNS = {'_content_rendered': 'content', '_resume_rendered': 'resume'}


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
    """Keep the rendered HTML and drop the columns markitup used to create.

    ``0001_initial`` no longer creates them, so on a fresh database there is
    nothing to do. Databases created before markitup was removed still carry
    them as NOT NULL columns, which would break every new insert.

    Before dropping, the rendered HTML is moved into the field itself:
    ``content``/``resume`` still hold the markdown *source*, which the editor
    and the templates would now show verbatim (and republishing would copy that
    source over ``published_content``). The rendered column is the only place
    the HTML exists, so this step is what makes the upgrade lossless. It cannot
    be undone, hence the noop reverse.

    Known limitation: the ``DROP COLUMN`` is raw SQL, so SQLite older than 3.35
    (which lacks it) cannot run this migration. Django 5.2 itself only requires
    SQLite 3.31.
    """
    table = apps.get_model('blog', 'Entry')._meta.db_table
    connection = schema_editor.connection
    quote = connection.ops.quote_name
    for column in get_existing_legacy_columns(schema_editor, table):
        target = LEGACY_COLUMNS[column]
        schema_editor.execute(
            "UPDATE %s SET %s = %s WHERE %s IS NOT NULL AND %s <> ''" % (
                quote(table), quote(target), quote(column),
                quote(column), quote(column)))
        schema_editor.execute('ALTER TABLE %s DROP COLUMN %s' % (
            quote(table), quote(column)))


class Migration(migrations.Migration):
    dependencies = [
        ('blog', '0001_initial'),
    ]

    operations = [
        # Not elidable: squashing it away would leave pre-markitup-removal
        # databases with the NOT NULL legacy columns still in place, breaking
        # every insert into blog_entry.
        migrations.RunPython(drop_legacy_columns, migrations.RunPython.noop),
    ]
