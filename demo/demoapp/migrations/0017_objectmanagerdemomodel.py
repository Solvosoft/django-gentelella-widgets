# Generated by Django 4.2.3 on 2023-10-11 22:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('demoapp', '0016_delete_colors'),
    ]

    operations = [
        migrations.CreateModel(
            name='ObjectManagerDemoModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('float_number', models.FloatField(default=0)),
                ('knob_number', models.IntegerField(default=0)),
                ('born_date', models.DateField()),
                ('last_time', models.DateTimeField()),
                ('livetime_range', models.CharField(max_length=256)),
                ('description', models.TextField()),
                ('simple_archive', models.FileField(upload_to='files')),
                ('chunked_archive', models.FileField(upload_to='chunked_files')),
                ('radio_elements', models.IntegerField(choices=[(1, 'A'), (2, 'B'), (3, 'C'), (4, 'D')])),
                ('taging_list', models.CharField(max_length=256)),
                ('yes_no', models.BooleanField(default=False)),
                ('field_autocomplete', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ct', to='demoapp.country')),
                ('field_select', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='demoapp.community')),
                ('m2m_autocomplete', models.ManyToManyField(related_name='autocomplext', to='demoapp.country')),
                ('m2m_multipleselect', models.ManyToManyField(to='demoapp.a')),
            ],
        ),
    ]