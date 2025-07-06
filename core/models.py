from django.db import models
from django.contrib.auth.models import User
import uuid
import os


def upload_audio_path(instance, filename):
    return f'audio/{instance.id}/{filename}'


class Meeting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    audio_file = models.FileField(upload_to=upload_audio_path, blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.BigIntegerField(blank=True, null=True)
    duration = models.DurationField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title or f"Meeting {self.id}"


class Transcript(models.Model):
    WHISPER_MODEL_CHOICES = [
        ('tiny', 'Tiny'),
        ('base', 'Base'),
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
        ('large-v2', 'Large V2'),
        ('large-v3', 'Large V3'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE, related_name='transcript')
    text = models.TextField(blank=True)
    whisper_model = models.CharField(max_length=20, choices=WHISPER_MODEL_CHOICES, default='base')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.IntegerField(default=0)  # 0-100
    error_message = models.TextField(blank=True)
    processing_time = models.DurationField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Transcript for {self.meeting}"


class Insight(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE, related_name='insight')
    situation = models.TextField(blank=True)
    insights = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.IntegerField(default=0)  # 0-100
    error_message = models.TextField(blank=True)
    processing_time = models.DurationField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Insight for {self.meeting}"
