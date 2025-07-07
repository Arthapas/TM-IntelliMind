"""
Chunk-based Transcription and Reassembly

This module handles transcription of chunked audio files and reassembles
the results into a complete transcript.
"""

import logging
import threading
import time
from typing import List, Optional
from django.utils import timezone
from .models import Meeting, AudioChunk, Transcript
from .utils import transcribe_audio

logger = logging.getLogger(__name__)


def transcribe_audio_with_timeout(audio_path, whisper_model, chunk, language, timeout=300):
    """
    Transcribe audio with timeout to prevent hanging threads
    
    Args:
        audio_path: Path to audio file
        whisper_model: Whisper model to use
        chunk: AudioChunk object for progress tracking
        language: Language code or None for auto-detection
        timeout: Timeout in seconds (default: 5 minutes)
        
    Returns:
        tuple: (success: bool, text: str or None, timed_out: bool)
    """
    result = [None]
    exception = [None]
    
    def transcribe_worker():
        try:
            text = transcribe_audio(audio_path, whisper_model, chunk, language)
            result[0] = text
        except Exception as e:
            exception[0] = e
    
    # Start transcription in a separate thread
    thread = threading.Thread(target=transcribe_worker, daemon=True)
    thread.start()
    
    # Wait for completion or timeout
    thread.join(timeout=timeout)
    
    if thread.is_alive():
        logger.error(f"Transcription timed out after {timeout}s for chunk {chunk.chunk_index}")
        # Thread is still running, mark as timeout
        return (False, None, True)
    
    if exception[0]:
        logger.error(f"Transcription failed for chunk {chunk.chunk_index}: {exception[0]}")
        return (False, None, False)
    
    return (True, result[0], False)


class ChunkTranscriber:
    """
    Handles transcription of audio chunks and reassembly
    """
    
    def __init__(self):
        self.overlap_threshold = 3.0  # 3 seconds to detect overlap
    
    def transcribe_chunk(self, chunk: AudioChunk, whisper_model: str = 'large-v2', 
                        language: Optional[str] = None) -> bool:
        """
        Transcribe a single audio chunk
        
        Args:
            chunk: AudioChunk instance to transcribe
            whisper_model: Whisper model to use
            language: Language code (optional)
            
        Returns:
            True if successful
        """
        try:
            chunk.status = 'processing'
            chunk.save()
            
            logger.info(f"Starting transcription for chunk {chunk.chunk_index} of meeting {chunk.meeting.id}")
            
            # Transcribe the chunk file with timeout protection (reduced timeout for faster detection)
            success, text, timed_out = transcribe_audio_with_timeout(chunk.file_path, whisper_model, chunk, language, timeout=90)
            
            if success and text:
                chunk.transcript_text = text
                chunk.status = 'completed'
                chunk.progress = 100
                logger.info(f"Completed transcription for chunk {chunk.chunk_index}")
            elif timed_out:
                chunk.status = 'failed'
                chunk.error_message = f"Transcription timed out after 180 seconds"
                logger.error(f"Transcription timeout for chunk {chunk.chunk_index}")
            else:
                chunk.status = 'failed'
                chunk.error_message = "No transcription text generated or error occurred"
                logger.warning(f"No text generated for chunk {chunk.chunk_index}")
            
            chunk.save()
            return chunk.status == 'completed'
            
        except Exception as e:
            chunk.status = 'failed'
            chunk.error_message = str(e)
            chunk.save()
            logger.error(f"Transcription failed for chunk {chunk.chunk_index}: {e}")
            return False
    
    def remove_overlap_text(self, previous_text: str, current_text: str, 
                           overlap_duration: float) -> str:
        """
        Remove overlapping text between consecutive chunks
        
        Args:
            previous_text: Text from previous chunk
            current_text: Text from current chunk
            overlap_duration: Overlap duration in seconds
            
        Returns:
            Current text with overlap removed
        """
        if not previous_text or not current_text or overlap_duration <= 0:
            return current_text
        
        try:
            # Split texts into words
            prev_words = previous_text.strip().split()
            curr_words = current_text.strip().split()
            
            if len(prev_words) < 5 or len(curr_words) < 5:
                return current_text
            
            # Estimate overlap based on duration (rough approximation)
            # Assume average 2-3 words per second
            estimated_overlap_words = int(overlap_duration * 2.5)
            
            if estimated_overlap_words <= 0:
                return current_text
            
            # Look for matching sequences at the end of previous and start of current
            max_check = min(estimated_overlap_words + 5, len(prev_words) // 2, len(curr_words) // 2)
            
            best_match_length = 0
            for i in range(1, max_check + 1):
                prev_suffix = prev_words[-i:]
                curr_prefix = curr_words[:i]
                
                # Check for exact match or partial match
                if prev_suffix == curr_prefix:
                    best_match_length = i
                elif len(prev_suffix) == len(curr_prefix):
                    # Check for partial match (70% similarity)
                    matches = sum(1 for a, b in zip(prev_suffix, curr_prefix) if a.lower() == b.lower())
                    if matches / len(prev_suffix) >= 0.7:
                        best_match_length = i
            
            # Remove overlapping words from current text
            if best_match_length > 0:
                remaining_words = curr_words[best_match_length:]
                result = ' '.join(remaining_words).strip()
                logger.debug(f"Removed {best_match_length} overlapping words")
                return result
            
            return current_text
            
        except Exception as e:
            logger.warning(f"Failed to remove overlap: {e}")
            return current_text
    
    def reassemble_transcript(self, meeting: Meeting) -> str:
        """
        Reassemble transcript from completed chunks
        
        Args:
            meeting: Meeting instance
            
        Returns:
            Complete transcript text
        """
        try:
            chunks = meeting.chunks.filter(status='completed').order_by('chunk_index')
            
            if not chunks.exists():
                logger.warning(f"No completed chunks found for meeting {meeting.id}")
                return ""
            
            transcript_parts = []
            previous_text = ""
            
            for chunk in chunks:
                if not chunk.transcript_text:
                    continue
                
                current_text = chunk.transcript_text.strip()
                
                if previous_text and chunk.chunk_index > 0:
                    # Calculate overlap duration between this chunk and previous
                    prev_chunk = chunks.filter(chunk_index=chunk.chunk_index - 1).first()
                    if prev_chunk:
                        overlap_duration = max(0, prev_chunk.end_time - chunk.start_time)
                        current_text = self.remove_overlap_text(previous_text, current_text, overlap_duration)
                
                if current_text:
                    transcript_parts.append(current_text)
                    previous_text = current_text
            
            complete_transcript = ' '.join(transcript_parts)
            logger.info(f"Reassembled transcript with {len(chunks)} chunks, total length: {len(complete_transcript)} characters")
            
            return complete_transcript
            
        except Exception as e:
            logger.error(f"Failed to reassemble transcript: {e}")
            return ""
    
    def get_transcription_progress(self, meeting: Meeting) -> dict:
        """
        Get overall transcription progress for a meeting with chunks
        
        Args:
            meeting: Meeting instance
            
        Returns:
            Progress information dictionary
        """
        try:
            chunks = meeting.chunks.all()
            
            if not chunks.exists():
                # No chunks, use regular transcript progress
                transcript = meeting.transcript
                return {
                    'progress': transcript.progress,
                    'status': transcript.status,
                    'chunks_total': 0,
                    'chunks_completed': 0,
                    'chunks_processing': 0,
                    'chunks_failed': 0
                }
            
            total_chunks = chunks.count()
            completed_chunks = chunks.filter(status='completed').count()
            processing_chunks = chunks.filter(status='processing').count()
            failed_chunks = chunks.filter(status='failed').count()
            
            # Calculate overall progress
            overall_progress = int((completed_chunks / total_chunks) * 100) if total_chunks > 0 else 0
            
            # Determine overall status
            if failed_chunks == total_chunks:
                overall_status = 'failed'
            elif completed_chunks == total_chunks:
                overall_status = 'completed'
            elif processing_chunks > 0 or completed_chunks > 0:
                overall_status = 'processing'
            else:
                overall_status = 'pending'
            
            return {
                'progress': overall_progress,
                'status': overall_status,
                'chunks_total': total_chunks,
                'chunks_completed': completed_chunks,
                'chunks_processing': processing_chunks,
                'chunks_failed': failed_chunks,
                'chunk_details': [
                    {
                        'index': chunk.chunk_index,
                        'status': chunk.status,
                        'progress': chunk.progress,
                        'start_time': chunk.start_time,
                        'end_time': chunk.end_time,
                        'duration': chunk.duration
                    }
                    for chunk in chunks.order_by('chunk_index')
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get transcription progress: {e}")
            return {
                'progress': 0,
                'status': 'failed',
                'error': str(e)
            }


def transcribe_meeting_chunks(meeting: Meeting, whisper_model: str = 'large-v2', 
                             language: Optional[str] = None) -> bool:
    """
    Transcribe all chunks for a meeting in parallel
    
    Args:
        meeting: Meeting instance
        whisper_model: Whisper model to use
        language: Language code (optional)
        
    Returns:
        True if all chunks processed successfully
    """
    try:
        chunks = meeting.chunks.filter(status='pending')
        
        if not chunks.exists():
            logger.info(f"No pending chunks found for meeting {meeting.id}")
            return True
        
        transcriber = ChunkTranscriber()
        
        # Process chunks in parallel (limit concurrent threads)
        max_workers = min(4, chunks.count())  # Limit to 4 concurrent transcriptions
        success_count = 0
        
        def transcribe_worker(chunk):
            nonlocal success_count
            if transcriber.transcribe_chunk(chunk, whisper_model, language):
                success_count += 1
        
        threads = []
        chunk_list = list(chunks)
        
        # Process in batches to avoid overwhelming the system
        batch_size = max_workers
        for i in range(0, len(chunk_list), batch_size):
            batch = chunk_list[i:i + batch_size]
            batch_threads = []
            
            for chunk in batch:
                thread = threading.Thread(target=transcribe_worker, args=(chunk,))
                thread.start()
                batch_threads.append(thread)
            
            # Wait for batch to complete
            for thread in batch_threads:
                thread.join()
            
            threads.extend(batch_threads)
        
        # Update meeting transcript with reassembled text
        if success_count > 0:
            complete_transcript = transcriber.reassemble_transcript(meeting)
            if complete_transcript:
                transcript = meeting.transcript
                transcript.text = complete_transcript
                transcript.status = 'completed' if success_count == chunks.count() else 'partially_completed'
                transcript.progress = int((success_count / chunks.count()) * 100)
                transcript.save()
                
                logger.info(f"Meeting {meeting.id} transcription completed: {success_count}/{chunks.count()} chunks")
        
        return success_count == chunks.count()
        
    except Exception as e:
        logger.error(f"Failed to transcribe meeting chunks: {e}")
        return False