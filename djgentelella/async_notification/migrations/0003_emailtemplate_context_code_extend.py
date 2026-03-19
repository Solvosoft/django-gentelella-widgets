from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('async_notification', '0002_emailtemplate_context_code_base_template'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailtemplate',
            name='context_code',
            field=models.CharField(
                blank=True, default='',
                help_text='Comma-separated registered context codes for variable suggestions',
                max_length=1000, verbose_name='Context Code'),
        ),
    ]
