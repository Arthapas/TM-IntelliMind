# Generated by Django 4.2.23 on 2025-07-06 10:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_add_audiochunk_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='transcription_model',
            field=models.CharField(choices=[('tiny', 'Tiny'), ('base', 'Base'), ('small', 'Small'), ('medium', 'Medium'), ('large', 'Large'), ('large-v2', 'Large V2'), ('large-v3', 'Large V3')], default='medium', max_length=20),
        ),
        migrations.AlterField(
            model_name='meeting',
            name='duration',
            field=models.FloatField(blank=True, help_text='Duration in seconds', null=True),
        ),
    ]
