# Generated by Django 3.2.25 on 2024-09-23 10:43

from django.db import migrations, models
import django.utils.timezone
import encrypted_model_fields.fields


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0004_customer_special_recipient'),
    ]

    operations = [
        migrations.CreateModel(
            name='ErrorLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('error', encrypted_model_fields.fields.EncryptedTextField()),
                ('time', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name': 'Log Error',
                'verbose_name_plural': 'Log Error',
            },
        ),
    ]
