"""The uniqueness of a push subscription moves from ``endpoint`` to
``endpoint_hash``, its sha256.

A unique index over ``endpoint`` (1000 characters, 4000 bytes in utf8mb4)
exceeds the 3072 bytes InnoDB allows, so ``0027`` could not run on
MySQL/MariaDB. ``0027`` no longer declares it; a database that already ran the
old ``0027`` keeps an index over ``endpoint`` that changes nothing, and this
migration fills the hash of the rows it has.
"""
import hashlib

from django.db import migrations, models


def fill_hashes(apps, schema_editor):
    subscription_model = apps.get_model('djgentelella', 'PushSubscription')
    for subscription in subscription_model.objects.all().only('pk', 'endpoint'):
        subscription_model.objects.filter(pk=subscription.pk).update(
            endpoint_hash=hashlib.sha256(
                (subscription.endpoint or '').encode('utf-8')).hexdigest())


class Migration(migrations.Migration):

    dependencies = [
        ('djgentelella', '0028_translations'),
    ]

    operations = [
        migrations.AddField(
            model_name='pushsubscription',
            name='endpoint_hash',
            field=models.CharField(editable=False, max_length=64, null=True,
                                   verbose_name='Endpoint hash'),
        ),
        migrations.RunPython(fill_hashes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='pushsubscription',
            name='endpoint_hash',
            field=models.CharField(editable=False, max_length=64, unique=True,
                                   verbose_name='Endpoint hash'),
        ),
    ]
