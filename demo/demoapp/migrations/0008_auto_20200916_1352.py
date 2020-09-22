# Generated by Django 3.1 on 2020-09-16 19:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('demoapp', '0007_daterange'),
    ]

    operations = [
        migrations.CreateModel(
            name='gridSlider',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('minimum', models.IntegerField()),
                ('maximum', models.IntegerField()),
                ('datetime', models.DateTimeField()),
                ('age', models.IntegerField()),
            ],
        ),
        migrations.AlterField(
            model_name='daterange',
            name='date_time',
            field=models.CharField(max_length=45),
        ),
    ]