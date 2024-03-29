# Generated by Django 3.0.2 on 2020-06-12 05:07

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('demoapp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PeopleGroup',
            fields=[
                ('id',
                 models.AutoField(auto_created=True, primary_key=True, serialize=False,
                                  verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('people', models.ManyToManyField(to='demoapp.Person')),
            ],
        ),
    ]
