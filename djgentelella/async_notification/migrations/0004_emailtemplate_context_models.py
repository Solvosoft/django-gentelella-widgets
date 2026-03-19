from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('async_notification', '0003_emailtemplate_context_code_extend'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='emailtemplate',
            name='context_code',
        ),
        migrations.AddField(
            model_name='emailtemplate',
            name='context_models',
            field=models.ManyToManyField(
                blank=True,
                help_text='Models whose fields are available as template variables',
                to='contenttypes.contenttype',
                verbose_name='Context Models',
            ),
        ),
    ]
