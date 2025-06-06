# Generated by Django 5.2 on 2025-05-01 13:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0006_alter_aiassistant_options_remove_aiassistant_name_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aiassistant',
            name='config',
            field=models.JSONField(blank=True, default=dict, help_text='Configuration settings for the assistant'),
        ),
    ]
