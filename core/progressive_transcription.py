"""
Progressive Transcription System

This module handles progressive transcription of audio chunks as they become available,
enabling real-time transcript building for large files.
"""

import logging
import threading
import time
from queue import Queue, Empty
from typing import Optional, Dict, List
from django.utils import timezone
from .models import Meeting, AudioChunk, Transcript
from .chunk_transcription import ChunkTranscriber

logger = logging.getLogger(__name__)


class ProgressiveTranscriber:
    """
    Manages progressive transcription of audio chunks as they become available.
    
    Features:
    - Queue-based transcription processing
    - Limited concurrent transcriptions to manage resources
    - Sequential processing when possible for better reassembly
    - Error handling and retry mechanisms
    """
    
    # Class-level registry to track active transcribers per meeting
    _active_transcribers = {}
    _lock = threading.Lock()
    
    def __init__(self, meeting: Meeting, max_concurrent_transcriptions: int = 1):
        """
        Initialize progressive transcriber for a meeting
        
        Args:
            meeting: Meeting instance to transcribe
            max_concurrent_transcriptions: Maximum number of concurrent transcription threads
        """
        self.meeting = meeting
        self.max_concurrent = max_concurrent_transcriptions
        self.transcription_queue = Queue()
        self.active_threads = {}
        self.thread_start_times = {}  # Track when each thread started
        self.completed_chunks = {}
        self.failed_chunks = set()
        self.retry_counts = {}  # Track retry attempts per chunk
        self.is_running = False
        self.should_stop = False
        self.chunk_transcriber = ChunkTranscriber()
        
        # Performance monitoring
        self.slow_chunk_count = 0  # Track chunks that take >30s
        self.performance_degraded = False
        
        # Track chunk creation status to prevent premature completion
        self.chunking_complete = False
        self.expected_chunk_count = None  # Will be set when chunking is done
        
        # Get transcription settings from meeting
        self.whisper_model = meeting.transcription_model
        self.language = None  # Could be added to meeting model later
        
        # Watchdog settings
        self.thread_timeout = 320  # 5.33 minutes max per chunk (should be > chunk timeout of 300s)
        self.max_retries = 1  # Reduced retry attempts for faster recovery
        self.last_watchdog_check = time.time()
        self.watchdog_interval = 5  # Check every 5 seconds for faster detection
        
        logger.info(f"Initialized ProgressiveTranscriber for meeting {meeting.id} with model {self.whisper_model}")
    
    @classmethod
    def get_or_create_transcriber(cls, meeting: Meeting) -> 'ProgressiveTranscriber':
        """
        Get existing transcriber for meeting or create new one
        
        Args:
            meeting: Meeting instance
            
        Returns:
            ProgressiveTranscriber instance
        """
        with cls._lock:
            meeting_id = str(meeting.id)
            if meeting_id not in cls._active_transcribers:
                cls._active_transcribers[meeting_id] = cls(meeting)
            return cls._active_transcribers[meeting_id]
    
    @classmethod
    def cleanup_transcriber(cls, meeting: Meeting):
        """
        Clean up transcriber for completed meeting
        
        Args:
            meeting: Meeting instance
        """
        with cls._lock:
            meeting_id = str(meeting.id)
            if meeting_id in cls._active_transcribers:
                transcriber = cls._active_transcribers[meeting_id]
                transcriber.stop()
                del cls._active_transcribers[meeting_id]
                logger.info(f"Cleaned up transcriber for meeting {meeting_id}")
    
    def start(self):
        """Start the progressive transcription system"""
        if self.is_running:
            logger.warning(f"Transcriber for meeting {self.meeting.id} is already running")
            return
        
        self.is_running = True
        self.should_stop = False
        
        # Start the queue processor in a separate thread
        processor_thread = threading.Thread(target=self._process_queue, daemon=True)
        processor_thread.start()
        
        logger.info(f"Started progressive transcription for meeting {self.meeting.id}")
    
    def stop(self):
        """Stop the progressive transcription system"""
        self.should_stop = True
        self.is_running = False
        
        # Wait for active transcription threads to complete
        for thread in self.active_threads.values():
            if thread.is_alive():
                thread.join(timeout=10)  # Wait up to 10 seconds
        
        logger.info(f"Stopped progressive transcription for meeting {self.meeting.id}")
    
    def add_chunk_for_transcription(self, chunk: AudioChunk):
        """
        Add a chunk to the transcription queue
        
        Args:
            chunk: AudioChunk instance to transcribe
        """
        if chunk.status != 'pending':
            logger.warning(f"Chunk {chunk.chunk_index} is not pending, status: {chunk.status}")
            return
        
        self.transcription_queue.put(chunk)
        queue_size = self.transcription_queue.qsize()
        logger.info(f"Added chunk {chunk.chunk_index} to transcription queue for meeting {self.meeting.id} "
                   f"(queue size: {queue_size})")
        
        # Start transcriber if not already running
        if not self.is_running:
            self.start()
    
    def _process_queue(self):
        """Main queue processing loop"""
        logger.info(f"Started queue processor for meeting {self.meeting.id}")
        
        while not self.should_stop:
            try:
                # Run watchdog to check for stuck threads
                self._check_stuck_threads()
                
                # Adjust concurrency based on performance
                max_concurrent = self.max_concurrent
                if self.performance_degraded:
                    max_concurrent = 1  # Reduce to single-threaded when performance is poor
                    logger.warning(f"Performance degraded, reducing to single-threaded processing")
                
                # Check if we can start more transcriptions
                if len(self.active_threads) >= max_concurrent:
                    time.sleep(0.5)
                    continue
                
                # Get next chunk from queue with timeout
                try:
                    chunk = self.transcription_queue.get(timeout=1.0)
                    queue_remaining = self.transcription_queue.qsize()
                    logger.info(f"Processing chunk {chunk.chunk_index} from queue "
                               f"(queue remaining: {queue_remaining})")
                except Empty:
                    # Check if we're done processing
                    if self._should_finish():
                        break
                    logger.debug(f"Queue empty, checking if finished (chunking_complete: {self.chunking_complete})")
                    continue
                
                # Start transcription thread for this chunk
                self._start_chunk_transcription(chunk)
                
            except Exception as e:
                logger.error(f"Error in queue processor for meeting {self.meeting.id}: {e}")
                time.sleep(1.0)
        
        logger.info(f"Queue processor finished for meeting {self.meeting.id}")
    
    def _check_stuck_threads(self):
        """
        Watchdog function to check for and clean up stuck transcription threads
        """
        current_time = time.time()
        
        # Check at specified interval for faster detection
        if current_time - self.last_watchdog_check < self.watchdog_interval:
            return
        
        self.last_watchdog_check = current_time
        stuck_chunks = []
        
        # Log watchdog check details
        if self.thread_start_times:
            logger.debug(f"Watchdog checking {len(self.thread_start_times)} active threads for meeting {self.meeting.id}")
        
        # Check thread-based timeouts
        for chunk_index, start_time in self.thread_start_times.items():
            if current_time - start_time > self.thread_timeout:
                stuck_chunks.append(chunk_index)
        
        # Also check database for chunks stuck in processing state
        from django.utils import timezone
        stuck_db_chunks = self.meeting.chunks.filter(
            status='processing',
            updated_at__lt=timezone.now() - timezone.timedelta(seconds=self.thread_timeout)
        )
        
        for chunk in stuck_db_chunks:
            if chunk.chunk_index not in stuck_chunks:
                stuck_chunks.append(chunk.chunk_index)
                logger.warning(f"Found database chunk {chunk.chunk_index} stuck in processing "
                             f"for {(timezone.now() - chunk.updated_at).total_seconds():.0f}s")
        
        for chunk_index in stuck_chunks:
            # Get runtime from either thread tracking or database 
            if chunk_index in self.thread_start_times:
                runtime = current_time - self.thread_start_times[chunk_index]
                logger.error(f"Detected stuck transcription for chunk {chunk_index} "
                           f"(thread running for {runtime:.1f}s)")
            else:
                logger.error(f"Detected stuck transcription for chunk {chunk_index} "
                           f"(found in database processing state)")
            
            # Clean up stuck thread
            if chunk_index in self.active_threads:
                thread = self.active_threads[chunk_index]
                logger.warning(f"Abandoning stuck thread for chunk {chunk_index}")
                # Note: We can't force kill the thread, but we can remove it from tracking
                del self.active_threads[chunk_index]
            
            if chunk_index in self.thread_start_times:
                del self.thread_start_times[chunk_index]
            
            # Check if we should retry this chunk
            retry_count = self.retry_counts.get(chunk_index, 0)
            if retry_count < self.max_retries:
                # Retry the chunk
                self.retry_counts[chunk_index] = retry_count + 1
                logger.info(f"Retrying chunk {chunk_index} (attempt {retry_count + 1}/{self.max_retries})")
                
                try:
                    chunk = self.meeting.chunks.get(chunk_index=chunk_index)
                    chunk.status = 'pending'
                    chunk.error_message = f"Retry {retry_count + 1} after timeout"
                    chunk.save()
                    
                    # Re-queue the chunk for transcription
                    self.transcription_queue.put(chunk)
                    logger.info(f"Re-queued chunk {chunk_index} for retry")
                except Exception as e:
                    logger.error(f"Failed to retry chunk {chunk_index}: {e}")
                    self.failed_chunks.add(chunk_index)
            else:
                # Max retries reached, mark as permanently failed
                self.failed_chunks.add(chunk_index)
                
                # Update chunk status in database
                try:
                    chunk = self.meeting.chunks.get(chunk_index=chunk_index)
                    chunk.status = 'failed'
                    chunk.error_message = f"Transcription timeout after {self.thread_timeout}s (max retries exceeded)"
                    chunk.save()
                    logger.info(f"Marked chunk {chunk_index} as permanently failed after {retry_count} retries")
                except Exception as e:
                    logger.error(f"Failed to update chunk {chunk_index} status: {e}")
    
    def _start_chunk_transcription(self, chunk: AudioChunk):
        """
        Start transcription for a single chunk in a separate thread
        
        Args:
            chunk: AudioChunk to transcribe
        """
        def transcribe_chunk():
            try:
                chunk_id = chunk.chunk_index
                logger.info(f"Starting transcription for chunk {chunk_id} of meeting {self.meeting.id}")
                
                # Perform transcription
                success = self.chunk_transcriber.transcribe_chunk(
                    chunk, self.whisper_model, self.language
                )
                
                if success:
                    self.completed_chunks[chunk_id] = chunk
                    completed_count = len(self.completed_chunks)
                    total_chunks = self.meeting.chunks.count()
                    logger.info(f"Completed transcription for chunk {chunk_id} "
                               f"({completed_count}/{total_chunks} chunks done)")
                    
                    # Check performance and adjust if needed
                    chunk_duration = time.time() - self.thread_start_times.get(chunk_id, time.time())
                    if chunk_duration > 90:  # Chunk took longer than 90 seconds (3x real-time for 30s chunks)
                        self.slow_chunk_count += 1
                        logger.warning(f"Slow chunk detected: {chunk_id} took {chunk_duration:.1f}s")
                        
                        # Degrade performance if too many slow chunks
                        if self.slow_chunk_count >= 3:
                            self.performance_degraded = True
                            logger.warning("Performance degraded: reducing concurrency")
                    
                    # Try to update the meeting transcript progressively
                    self._update_progressive_transcript()
                else:
                    self.failed_chunks.add(chunk_id)
                    failed_count = len(self.failed_chunks)
                    logger.error(f"Failed transcription for chunk {chunk_id} "
                                f"({failed_count} total failures)")
                
            except Exception as e:
                logger.error(f"Error transcribing chunk {chunk.chunk_index}: {e}")
                self.failed_chunks.add(chunk.chunk_index)
            
            finally:
                # Remove from active threads and timing tracking
                if chunk.chunk_index in self.active_threads:
                    del self.active_threads[chunk.chunk_index]
                if chunk.chunk_index in self.thread_start_times:
                    del self.thread_start_times[chunk.chunk_index]
                
                # Mark queue task as done
                self.transcription_queue.task_done()
        
        # Start the transcription thread
        thread = threading.Thread(target=transcribe_chunk, daemon=True)
        self.active_threads[chunk.chunk_index] = thread
        self.thread_start_times[chunk.chunk_index] = time.time()
        thread.start()
    
    def _update_progressive_transcript(self):
        """Update the meeting transcript with available completed chunks"""
        try:
            # Get all chunks for this meeting, ordered by index
            all_chunks = self.meeting.chunks.all().order_by('chunk_index')
            
            # Build transcript from completed chunks in sequence
            transcript_parts = []
            for chunk in all_chunks:
                if chunk.chunk_index in self.completed_chunks and chunk.transcript_text:
                    # Apply overlap removal if this isn't the first chunk
                    text = chunk.transcript_text.strip()
                    if transcript_parts and chunk.chunk_index > 0:
                        # Get previous chunk for overlap calculation
                        prev_chunk = all_chunks.filter(chunk_index=chunk.chunk_index - 1).first()
                        if prev_chunk and hasattr(prev_chunk, 'transcript_text') and prev_chunk.transcript_text:
                            overlap_duration = max(0, prev_chunk.end_time - chunk.start_time)
                            text = self.chunk_transcriber.remove_overlap_text(
                                prev_chunk.transcript_text, text, overlap_duration
                            )
                    
                    if text:
                        transcript_parts.append(text)
            
            # Update the meeting transcript
            if transcript_parts:
                complete_text = ' '.join(transcript_parts)
                transcript = self.meeting.transcript
                transcript.text = complete_text
                transcript.updated_at = timezone.now()
                
                # Update status and progress if all chunks are completed
                total_chunks = self.meeting.chunks.count()
                # Use database state for consistency with get_progress_info()
                completed_chunks = self.meeting.chunks.filter(status='completed').count()
                
                if completed_chunks >= total_chunks and self.chunking_complete:
                    # All chunks are completed - mark transcript as completed
                    transcript.status = 'completed'
                    transcript.progress = 100
                    logger.info(f"Progressive transcription completed for meeting {self.meeting.id}")
                elif completed_chunks > 0:
                    # Partial completion - update progress
                    transcript.status = 'processing'
                    transcript.progress = int((completed_chunks / total_chunks) * 100) if total_chunks > 0 else 0
                
                transcript.save()
                
                logger.info(f"Updated progressive transcript for meeting {self.meeting.id}, "
                          f"length: {len(complete_text)} chars from {len(transcript_parts)} chunks, "
                          f"status: {transcript.status}, progress: {transcript.progress}%")
        
        except Exception as e:
            logger.error(f"Error updating progressive transcript for meeting {self.meeting.id}: {e}")
    
    def _should_finish(self) -> bool:
        """
        Check if the transcriber should finish processing
        
        Returns:
            True if processing should finish
        """
        # Don't finish if chunking is still in progress
        if not self.chunking_complete:
            logger.debug(f"Chunking still in progress for meeting {self.meeting.id}")
            return False
        
        # Check if there are any pending chunks left
        pending_chunks = self.meeting.chunks.filter(status='pending').count()
        
        # Check if all chunks are either completed or failed
        total_chunks = self.meeting.chunks.count()
        # Use database state for consistency
        completed_chunks = self.meeting.chunks.filter(status='completed').count()
        failed_chunks = self.meeting.chunks.filter(status='failed').count()
        processed_chunks = completed_chunks + failed_chunks
        
        # Additional validation: check expected vs actual chunk count
        # But only wait if chunking is not marked as complete
        if (self.expected_chunk_count and 
            total_chunks < self.expected_chunk_count and 
            not self.chunking_complete):
            logger.warning(f"Meeting {self.meeting.id}: Expected {self.expected_chunk_count} chunks, "
                          f"but only {total_chunks} created. Waiting for more chunks...")
            return False
        elif self.expected_chunk_count and total_chunks < self.expected_chunk_count:
            # Chunking is complete but chunk count differs - this is normal for small final chunks
            logger.info(f"Meeting {self.meeting.id}: Chunking complete with {total_chunks} chunks "
                       f"(originally estimated {self.expected_chunk_count})")
        
        should_finish = (pending_chunks == 0 and 
                        len(self.active_threads) == 0 and 
                        processed_chunks >= total_chunks)
        
        if should_finish:
            logger.info(f"Meeting {self.meeting.id} ready to finish: "
                       f"pending={pending_chunks}, active={len(self.active_threads)}, "
                       f"processed={processed_chunks}/{total_chunks}")
        
        return should_finish
    
    def mark_chunking_complete(self, expected_chunk_count: int = None):
        """
        Mark that chunk creation is complete for this meeting
        
        Args:
            expected_chunk_count: Expected number of chunks (for validation)
        """
        self.chunking_complete = True
        if expected_chunk_count:
            self.expected_chunk_count = expected_chunk_count
        
        # Get actual chunk count for validation
        actual_chunks = self.meeting.chunks.count()
        
        logger.info(f"Chunking complete for meeting {self.meeting.id}: "
                   f"expected={expected_chunk_count}, actual={actual_chunks}")
        
        if expected_chunk_count and actual_chunks != expected_chunk_count:
            logger.warning(f"Chunk count mismatch for meeting {self.meeting.id}: "
                          f"expected {expected_chunk_count}, got {actual_chunks}")
    
    def get_progress_info(self) -> Dict:
        """
        Get current progress information
        
        Returns:
            Dictionary with progress information
        """
        total_chunks = self.meeting.chunks.count()
        # Use database state instead of in-memory tracking to avoid decreasing progress
        completed_count = self.meeting.chunks.filter(status='completed').count()
        failed_count = self.meeting.chunks.filter(status='failed').count()
        active_count = len(self.active_threads)
        
        return {
            'total_chunks': total_chunks,
            'completed_chunks': completed_count,
            'failed_chunks': failed_count,
            'active_transcriptions': active_count,
            'progress_percentage': int((completed_count / total_chunks) * 100) if total_chunks > 0 else 0,
            'is_running': self.is_running
        }


def start_progressive_transcription(meeting: Meeting) -> ProgressiveTranscriber:
    """
    Start progressive transcription for a meeting
    
    Args:
        meeting: Meeting instance
        
    Returns:
        ProgressiveTranscriber instance
    """
    transcriber = ProgressiveTranscriber.get_or_create_transcriber(meeting)
    transcriber.start()
    return transcriber


def add_chunk_to_transcription_queue(chunk: AudioChunk):
    """
    Add a newly created chunk to the transcription queue
    
    Args:
        chunk: AudioChunk instance that was just created
    """
    transcriber = ProgressiveTranscriber.get_or_create_transcriber(chunk.meeting)
    transcriber.add_chunk_for_transcription(chunk)


def mark_chunking_complete(meeting: Meeting, expected_chunk_count: int = None):
    """
    Mark that chunking is complete for a meeting
    
    Args:
        meeting: Meeting instance
        expected_chunk_count: Expected number of chunks
    """
    with ProgressiveTranscriber._lock:
        meeting_id = str(meeting.id)
        if meeting_id in ProgressiveTranscriber._active_transcribers:
            transcriber = ProgressiveTranscriber._active_transcribers[meeting_id]
            transcriber.mark_chunking_complete(expected_chunk_count)
        else:
            logger.warning(f"No active transcriber found for meeting {meeting_id} when marking chunking complete")


def stop_progressive_transcription(meeting: Meeting):
    """
    Stop progressive transcription for a meeting
    
    Args:
        meeting: Meeting instance
    """
    ProgressiveTranscriber.cleanup_transcriber(meeting)