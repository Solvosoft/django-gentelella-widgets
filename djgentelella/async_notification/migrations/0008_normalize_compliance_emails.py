from django.db import migrations


def normalize(apps, schema_editor):
    """Lowercase existing suppression/consent emails for case-insensitive
    matching. If a normalized address collides with an already-normalized row,
    the duplicate is dropped (the constraint keeps a single record per address).
    """
    for model_name in ('EmailSuppression', 'EmailConsent'):
        model = apps.get_model('async_notification', model_name)
        seen = set()
        # Oldest first so the earliest record wins a collision.
        for obj in model.objects.order_by('created_at', 'pk'):
            normalized = (obj.email or '').strip().lower()
            if normalized in seen:
                obj.delete()
                continue
            seen.add(normalized)
            if normalized != obj.email:
                obj.email = normalized
                obj.save(update_fields=['email'])


class Migration(migrations.Migration):

    dependencies = [
        ('async_notification', '0007_newslettertask_error_message_and_more'),
    ]

    operations = [
        migrations.RunPython(normalize, migrations.RunPython.noop),
    ]
