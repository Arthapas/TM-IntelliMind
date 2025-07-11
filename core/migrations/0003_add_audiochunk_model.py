# Generated by Django 4.2.23 on 2025-07-06 09:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_meeting_description'),
    ]

    operations = [
        migrations.CreateModel(
            name='AudioChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chunk_index', models.IntegerField()),
                ('start_time', models.FloatField()),
                ('end_time', models.FloatField()),
                ('duration', models.FloatField()),
                ('file_path', models.CharField(max_length=500)),
                ('file_size', models.BigIntegerField(blank=True, null=True)),
                ('transcript_text', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('progress', models.IntegerField(default=0)),
                ('error_message', models.TextField(blank=True)),
                ('processing_time', models.DurationField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('meeting', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chunks', to='core.meeting')),
            ],
            options={
                'ordering': ['meeting', 'chunk_index'],
                'unique_together': {('meeting', 'chunk_index')},
            },
        ),
    ]
