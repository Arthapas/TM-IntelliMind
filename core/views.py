from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta
import json
import os
import threading
import uuid
import logging
from .models import Meeting, Transcript, Insight, AudioChunk
from .utils import transcribe_audio, generate_insights_from_text, generate_meeting_name_and_description
from .audio_chunking import chunk_meeting_audio, cleanup_chunks
from .chunk_transcription import transcribe_meeting_chunks, ChunkTranscriber

logger = logging.getLogger(__name__)


def home(request):
    try:
        # Get recent meetings with their insights
        meetings = Meeting.objects.all().order_by('-created_at')[:10]
        
        # Add summary information for each meeting
        for meeting in meetings:
            try:
                if hasattr(meeting, 'insight') and meeting.insight and meeting.insight.situation:
                    # Create a short summary from the situation
                    meeting.summary = meeting.insight.situation[:150] + '...' if len(meeting.insight.situation) > 150 else meeting.insight.situation
                else:
                    meeting.summary = "Analysis pending..."
            except Exception:
                meeting.summary = "Analysis pending..."
        
        return render(request, 'core/home.html', {'meetings': meetings})
    except Exception as e:
        # If there's an error, show empty meeting list
        return render(request, 'core/home.html', {'meetings': [], 'error': str(e)})


def create_insight(request):
    return render(request, 'core/create_insight.html')


def meeting_detail(request, meeting_id):
    try:
        meeting = get_object_or_404(Meeting, id=meeting_id)
        
        # Get transcript and insight if they exist
        transcript = None
        insight = None
        
        try:
            transcript = getattr(meeting, 'transcript', None)
        except Exception:
            pass
            
        try:
            insight = getattr(meeting, 'insight', None)
        except Exception:
            pass
        
        context = {
            'meeting': meeting,
            'transcript': transcript,
            'insight': insight,
        }
        
        return render(request, 'core/meeting_detail.html', context)
    except Exception as e:
        return render(request, 'core/meeting_detail.html', {
            'error': f"Error loading meeting: {str(e)}"
        })


@csrf_exempt
@require_http_methods(["POST"])
def upload_audio(request):
    try:
        if 'audio_file' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No audio file provided'})
        
        audio_file = request.FILES['audio_file']
        
        # Validate file type
        allowed_extensions = ['.mp3', '.wav', '.m4a', '.mp4']
        file_extension = os.path.splitext(audio_file.name)[1].lower()
        if file_extension not in allowed_extensions:
            return JsonResponse({'success': False, 'error': 'Invalid file type. Allowed: MP3, WAV, M4A, MP4'})
        
        # Validate file size (500MB limit for chunking support)
        max_size = 500 * 1024 * 1024  # 500MB in bytes
        if audio_file.size > max_size:
            return JsonResponse({'success': False, 'error': 'File too large. Maximum size is 500MB'})
        
        # Create meeting record
        meeting = Meeting.objects.create(
            title=f"Meeting {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            original_filename=audio_file.name,
            file_size=audio_file.size,
            created_by=request.user if request.user.is_authenticated else None
        )
        
        # Save audio file
        file_path = default_storage.save(f'audio/{meeting.id}/{audio_file.name}', audio_file)
        meeting.audio_file = file_path
        meeting.save()
        
        # Create transcript record
        Transcript.objects.create(meeting=meeting)
        
        # Check if file needs chunking and create chunks if necessary
        chunk_threshold = 100 * 1024 * 1024  # 100MB
        is_large_file = audio_file.size > chunk_threshold
        
        if is_large_file:
            # Start chunking in background thread
            def create_chunks():
                try:
                    success = chunk_meeting_audio(meeting)
                    if success:
                        logger.info(f"Successfully created chunks for meeting {meeting.id}")
                    else:
                        logger.error(f"Failed to create chunks for meeting {meeting.id}")
                except Exception as e:
                    logger.error(f"Chunking error for meeting {meeting.id}: {e}")
            
            thread = threading.Thread(target=create_chunks)
            thread.start()
        
        return JsonResponse({
            'success': True,
            'meeting_id': str(meeting.id),
            'message': 'File uploaded successfully',
            'is_large_file': is_large_file,
            'requires_chunking': is_large_file
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_http_methods(["POST"])
def start_transcription(request):
    try:
        data = json.loads(request.body)
        meeting_id = data.get('meeting_id')
        whisper_model = data.get('whisper_model', 'base')
        language = data.get('language', None)  # Support language parameter
        
        meeting = get_object_or_404(Meeting, id=meeting_id)
        transcript = meeting.transcript
        transcript.whisper_model = whisper_model
        transcript.status = 'processing'
        transcript.save()
        
        # Start transcription in background thread
        def run_transcription():
            try:
                # Check if meeting has chunks (large file)
                chunks = meeting.chunks.all()
                
                if chunks.exists():
                    # Process chunks
                    logger.info(f"Processing {chunks.count()} chunks for meeting {meeting.id}")
                    success = transcribe_meeting_chunks(meeting, whisper_model, language)
                    
                    if not success:
                        transcript.status = 'failed'
                        transcript.error_message = "Failed to process audio chunks"
                        transcript.save()
                else:
                    # Process regular file
                    audio_path = meeting.audio_file.path
                    text = transcribe_audio(audio_path, whisper_model, transcript, language)
                    
                    transcript.text = text
                    transcript.status = 'completed'
                    transcript.progress = 100
                    transcript.save()
                
            except Exception as e:
                transcript.status = 'failed'
                transcript.error_message = str(e)
                transcript.save()
        
        thread = threading.Thread(target=run_transcription)
        thread.start()
        
        return JsonResponse({'success': True, 'message': 'Transcription started'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
def transcription_progress(request):
    try:
        meeting_id = request.GET.get('meeting_id')
        meeting = get_object_or_404(Meeting, id=meeting_id)
        transcript = meeting.transcript
        
        # Check if meeting has chunks
        chunks = meeting.chunks.all()
        
        if chunks.exists():
            # Get chunk-based progress
            transcriber = ChunkTranscriber()
            progress_info = transcriber.get_transcription_progress(meeting)
            
            return JsonResponse({
                'progress': progress_info['progress'],
                'status': progress_info['status'],
                'transcript': transcript.text,
                'error': transcript.error_message,
                'is_chunked': True,
                'chunks_info': {
                    'total': progress_info['chunks_total'],
                    'completed': progress_info['chunks_completed'],
                    'processing': progress_info['chunks_processing'],
                    'failed': progress_info['chunks_failed']
                }
            })
        else:
            # Regular progress
            return JsonResponse({
                'progress': transcript.progress,
                'status': transcript.status,
                'transcript': transcript.text,
                'error': transcript.error_message,
                'is_chunked': False
            })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_http_methods(["POST"])
def generate_insights(request):
    try:
        data = json.loads(request.body)
        meeting_id = data.get('meeting_id')
        transcript_text = data.get('transcript_text')
        
        meeting = get_object_or_404(Meeting, id=meeting_id)
        
        # Update transcript text if provided
        if transcript_text:
            transcript = meeting.transcript
            transcript.text = transcript_text
            transcript.save()
        
        # Create or get insight record
        insight, created = Insight.objects.get_or_create(meeting=meeting)
        insight.status = 'processing'
        insight.save()
        
        # Start insights generation in background thread
        def run_insights_generation():
            try:
                situation, insights = generate_insights_from_text(transcript_text, insight)
                
                insight.situation = situation
                insight.insights = insights
                insight.status = 'completed'
                insight.progress = 100
                insight.save()
                
                # Generate meeting name and description
                try:
                    meeting_name, description = generate_meeting_name_and_description(transcript_text, meeting)
                    if meeting_name:
                        meeting.title = meeting_name
                    if description:
                        meeting.description = description
                    meeting.save()
                except Exception as name_error:
                    # Don't fail the whole process if name generation fails
                    pass
                
            except Exception as e:
                insight.status = 'failed'
                insight.error_message = str(e)
                insight.save()
        
        thread = threading.Thread(target=run_insights_generation)
        thread.start()
        
        return JsonResponse({'success': True, 'message': 'Insights generation started'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
def insights_progress(request):
    try:
        meeting_id = request.GET.get('meeting_id')
        meeting = get_object_or_404(Meeting, id=meeting_id)
        insight = meeting.insight
        
        return JsonResponse({
            'progress': insight.progress,
            'status': insight.status,
            'situation': insight.situation,
            'insights': insight.insights,
            'error': insight.error_message
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_http_methods(["POST"])
def save_analysis(request):
    try:
        data = json.loads(request.body)
        meeting_id = data.get('meeting_id')
        
        meeting = get_object_or_404(Meeting, id=meeting_id)
        
        # Update transcript
        if 'transcript_text' in data:
            transcript = meeting.transcript
            transcript.text = data['transcript_text']
            transcript.save()
        
        # Update insights
        if 'situation' in data or 'insights' in data:
            insight = meeting.insight
            if 'situation' in data:
                insight.situation = data['situation']
            if 'insights' in data:
                insight.insights = data['insights']
            insight.save()
        
        return JsonResponse({'success': True, 'message': 'Analysis saved successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["DELETE"])
def delete_meeting(request, meeting_id):
    """
    Delete a meeting and all associated data including files
    """
    try:
        # Get the meeting or return 404
        meeting = get_object_or_404(Meeting, id=meeting_id)
        
        # Store meeting info before deletion
        meeting_title = meeting.title or f"Meeting {str(meeting.id)[:8]}"
        
        # Clean up audio chunks if they exist
        try:
            cleanup_chunks(meeting)
        except Exception as chunk_error:
            logger.warning(f"Could not cleanup chunks for meeting {meeting_id}: {str(chunk_error)}")
        
        # Clean up audio file if it exists
        if meeting.audio_file:
            try:
                # Get the file path
                file_path = meeting.audio_file.path
                
                # Delete the file from filesystem
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                # Also try to remove the directory if it's empty
                dir_path = os.path.dirname(file_path)
                if os.path.exists(dir_path) and not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    
            except Exception as file_error:
                # Log file deletion error but continue with database deletion
                logger.warning(f"Could not delete audio file for meeting {meeting_id}: {str(file_error)}")
        
        # Delete the meeting (CASCADE will handle Transcript, Insight, and AudioChunk)
        meeting.delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'Meeting "{meeting_title}" deleted successfully'
        })
        
    except Meeting.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': 'Meeting not found'
        }, status=404)
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Failed to delete meeting: {str(e)}'
        }, status=500)
