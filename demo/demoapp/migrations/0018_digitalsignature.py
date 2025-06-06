# Generated by Django 5.1.5 on 2025-02-07 23:12

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('demoapp', '0017_objectmanagerdemomodel'),
    ]

    operations = [
        migrations.CreateModel(
            name='DigitalSignature',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_code', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('filename', models.CharField(blank=True, max_length=50, null=True)),
                ('file', models.FileField(upload_to='digital_signature/')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
