# Generated by Django 5.1 on 2024-10-27 16:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('queue_manager', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='queue',
            name='estimated_wait_time_per_turn',
            field=models.FloatField(default=0),
        ),
    ]