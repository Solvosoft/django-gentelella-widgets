from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    """``CREATE EXTENSION IF NOT EXISTS pg_trgm`` on PostgreSQL; nothing on
    other databases. Reversing it drops the extension."""

    dependencies = []

    operations = [TrigramExtension()]
