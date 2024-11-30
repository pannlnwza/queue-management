# Generated by Django 5.1.3 on 2024-11-30 14:13

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('manager', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Participant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30)),
                ('email', models.EmailField(blank=True, max_length=50, null=True)),
                ('phone', models.CharField(blank=True, max_length=20, null=True)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('position', models.PositiveIntegerField(blank=True, null=True)),
                ('note', models.TextField(blank=True, max_length=150, null=True)),
                ('code', models.CharField(editable=False, max_length=12, unique=True)),
                ('state', models.CharField(choices=[('waiting', 'Waiting'), ('serving', 'Serving'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('removed', 'Removed'), ('no_show', 'No Show')], default='waiting', max_length=10)),
                ('service_started_at', models.DateTimeField(blank=True, null=True)),
                ('service_completed_at', models.DateTimeField(blank=True, null=True)),
                ('waited', models.PositiveIntegerField(default=0)),
                ('visits', models.PositiveIntegerField(default=1)),
                ('resource_assigned', models.CharField(blank=True, max_length=20, null=True)),
                ('is_notified', models.BooleanField(default=False)),
                ('created_by', models.CharField(choices=[('guest', 'Guest'), ('staff', 'Staff')], default='guest', max_length=10)),
                ('status_qr_code', models.ImageField(blank=True, null=True, upload_to='qrcodes/')),
                ('number', models.CharField(editable=False, max_length=4)),
                ('announcement_audio', models.TextField(null=True)),
                ('qrcode_url', models.CharField(blank=True, max_length=500, null=True)),
                ('queue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='manager.queue')),
                ('resource', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='manager.resource')),
            ],
            options={
                'unique_together': {('number', 'queue')},
            },
        ),
        migrations.CreateModel(
            name='BankParticipant',
            fields=[
                ('participant_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='participant.participant')),
                ('service_type', models.CharField(choices=[('account_services', 'Account Services'), ('loan_services', 'Loan Services'), ('investment_services', 'Investment Services'), ('customer_support', 'Customer Support')], default='account_services', max_length=20)),
                ('participant_category', models.CharField(choices=[('individual', 'Individual'), ('business', 'Business'), ('corporate', 'Corporate'), ('government', 'Government')], default='individual', max_length=20)),
            ],
            bases=('participant.participant',),
        ),
        migrations.CreateModel(
            name='HospitalParticipant',
            fields=[
                ('participant_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='participant.participant')),
                ('medical_field', models.CharField(choices=[('cardiology', 'Cardiology'), ('neurology', 'Neurology'), ('orthopedics', 'Orthopedics'), ('dermatology', 'Dermatology'), ('pediatrics', 'Pediatrics'), ('general', 'General Medicine'), ('emergency', 'Emergency'), ('psychiatry', 'Psychiatry'), ('surgery', 'Surgery'), ('oncology', 'Oncology')], default='general', max_length=50)),
                ('priority', models.CharField(choices=[('urgent', 'Urgent'), ('normal', 'Normal'), ('low', 'Low')], default='normal', max_length=10)),
            ],
            bases=('participant.participant',),
        ),
        migrations.CreateModel(
            name='RestaurantParticipant',
            fields=[
                ('participant_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='participant.participant')),
                ('party_size', models.PositiveIntegerField(default=1)),
                ('service_type', models.CharField(choices=[('dine_in', 'Dine-in'), ('takeout', 'Takeout'), ('delivery', 'Delivery')], default='dine_in', max_length=20)),
            ],
            bases=('participant.participant',),
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_read', models.BooleanField(default=False)),
                ('played_sound', models.BooleanField(default=False)),
                ('participant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='participant.participant')),
                ('queue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='manager.queue')),
            ],
        ),
    ]
