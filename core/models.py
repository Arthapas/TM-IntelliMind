from django.db import models
from django.contrib.auth.models import User
import uuid
import os


def upload_audio_path(instance, filename):
    return f'audio/{instance.id}/{filename}'


class Meeting(models.Model):
    WHISPER_MODEL_CHOICES = [
        ('tiny', 'Tiny'),
        ('base', 'Base'),
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
        ('large-v2', 'Large V2'),
        ('large-v3', 'Large V3'),
    ]
    
    TRANSCRIPTION_PROVIDER_CHOICES = [
        ('local', 'Local Whisper Models'),
        ('openai', 'OpenAI Whisper API'),
        ('assemblyai', 'AssemblyAI'),
        ('deepgram', 'Deepgram'),
        ('custom', 'Custom API Endpoint'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    audio_file = models.FileField(upload_to=upload_audio_path, blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.BigIntegerField(blank=True, null=True)
    duration = models.FloatField(blank=True, null=True, help_text="Duration in seconds")
    
    # Transcription configuration
    transcription_provider = models.CharField(max_length=20, choices=TRANSCRIPTION_PROVIDER_CHOICES, default='local')
    transcription_model = models.CharField(max_length=50, choices=WHISPER_MODEL_CHOICES, default='medium', 
                                         help_text="For local provider: Whisper model. For APIs: provider-specific model")
    api_endpoint = models.URLField(blank=True, null=True, help_text="Custom API endpoint URL")
    api_model = models.CharField(max_length=50, blank=True, help_text="API-specific model name")
    api_credentials = models.TextField(blank=True, help_text="Encrypted API credentials")
    
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


class AudioChunk(models.Model):
    """
    Model for managing chunks of large audio files (>100MB)
    Enables processing large files by splitting them into manageable segments
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField()  # Order of this chunk in the sequence
    start_time = models.FloatField()     # Start time in seconds
    end_time = models.FloatField()       # End time in seconds
    duration = models.FloatField()       # Duration in seconds
    file_path = models.CharField(max_length=500)  # Path to chunk file
    file_size = models.BigIntegerField(blank=True, null=True)
    transcript_text = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.IntegerField(default=0)  # 0-100
    error_message = models.TextField(blank=True)
    processing_time = models.DurationField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['meeting', 'chunk_index']
        unique_together = ['meeting', 'chunk_index']
    
    def __str__(self):
        return f"Chunk {self.chunk_index} for {self.meeting}"


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
