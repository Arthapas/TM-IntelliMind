from django.contrib import admin
from .models import Meeting, Transcript, Insight, AudioChunk


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_by', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at', 'created_by']
    search_fields = ['title', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'created_by', 'audio_file')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Transcript)
class TranscriptAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'whisper_model', 'status', 'progress', 'created_at']
    list_filter = ['status', 'whisper_model', 'created_at']
    search_fields = ['meeting__title', 'text']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {
            'fields': ('meeting', 'whisper_model', 'status', 'progress')
        }),
        ('Content', {
            'fields': ('text',),
            'classes': ('wide',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'status', 'progress', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['meeting__title', 'situation', 'insights']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {
            'fields': ('meeting', 'status', 'progress')
        }),
        ('Content', {
            'fields': ('situation', 'insights'),
            'classes': ('wide',)
        }),
        ('Errors', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AudioChunk)
class AudioChunkAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'chunk_index', 'start_time', 'end_time', 'duration', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['meeting__title', 'transcript_text']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['meeting', 'chunk_index']
    
    fieldsets = (
        (None, {
            'fields': ('meeting', 'chunk_index', 'status', 'progress')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time', 'duration'),
            'classes': ('wide',)
        }),
        ('File Info', {
            'fields': ('file_path', 'file_size'),
            'classes': ('collapse',)
        }),
        ('Content', {
            'fields': ('transcript_text',),
            'classes': ('wide',)
        }),
        ('Errors', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
