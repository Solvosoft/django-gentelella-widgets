from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('async_notification', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailtemplate',
            name='context_code',
            field=models.CharField(
                blank=True, default='', help_text='Registered context code for variable suggestions',
                max_length=150, verbose_name='Context Code'),
        ),
        migrations.AddField(
            model_name='emailtemplate',
            name='base_template',
            field=models.CharField(
                blank=True, default='', help_text='Base template key from settings to wrap the email content',
                max_length=150, verbose_name='Base Template'),
        ),
    ]
