"""
Audio Chunking Utilities for Large File Processing

This module provides utilities for splitting large audio files (>100MB) into
manageable chunks for Whisper transcription processing.

Features:
- VAD-aware splitting to preserve speech boundaries
- Configurable chunk duration with overlap
- Fallback to time-based chunking
- Memory-efficient processing
"""

import os
import logging
import torchaudio
from pydub import AudioSegment
from typing import List, Tuple, Optional
from django.conf import settings
from .models import Meeting, AudioChunk
from .utils import detect_speech_segments

logger = logging.getLogger(__name__)


class AudioChunker:
    """
    Handles chunking of large audio files using VAD-aware and time-based strategies
    """
    
    def __init__(self, 
                 chunk_duration: float = None,  # Will use settings or default
                 overlap_duration: float = None,  # Will use settings or default
                 max_chunk_duration: float = None,  # Will use settings or default
                 min_chunk_duration: float = None):  # Will use settings or default
        
        # Load from Django settings with fallbacks
        from django.conf import settings
        
        self.chunk_duration = chunk_duration or getattr(settings, 'AUDIO_CHUNK_DURATION', 30.0)
        self.overlap_duration = overlap_duration or getattr(settings, 'AUDIO_OVERLAP_DURATION', 5.0)
        self.max_chunk_duration = max_chunk_duration or getattr(settings, 'AUDIO_MAX_CHUNK_DURATION', 60.0)
        self.min_chunk_duration = min_chunk_duration or getattr(settings, 'AUDIO_MIN_CHUNK_DURATION', 10.0)
        self.max_chunks = getattr(settings, 'AUDIO_MAX_CHUNKS', 150)  # Increased safety limit
        self.max_duration = getattr(settings, 'AUDIO_MAX_DURATION', 7200)  # 2 hours max
        
        logger.debug(f"AudioChunker configured - Duration: {self.chunk_duration}s, "
                    f"Overlap: {self.overlap_duration}s, "
                    f"Range: {self.min_chunk_duration}s-{self.max_chunk_duration}s")
    
    def should_chunk_file(self, file_size: int) -> bool:
        """
        Determine if a file should be chunked based on size
        
        Args:
            file_size: File size in bytes
            
        Returns:
            True if file should be chunked
        """
        # Chunk files larger than the configured threshold (default: 2MB)
        chunk_threshold = getattr(settings, 'AUDIO_CHUNK_THRESHOLD', 2 * 1024 * 1024)
        return file_size > chunk_threshold
    
    def get_audio_duration(self, audio_path: str) -> float:
        """
        Get audio duration in seconds with enhanced reliability
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Duration in seconds
        """
        # Try multiple methods for maximum reliability
        methods = [
            ("torchaudio", self._get_duration_torchaudio),
            ("pydub", self._get_duration_pydub),
            ("ffprobe", self._get_duration_ffprobe)
        ]
        
        for method_name, method_func in methods:
            try:
                duration = method_func(audio_path)
                if duration > 0:
                    logger.info(f"Audio duration detected via {method_name}: {duration:.2f} seconds")
                    return duration
            except Exception as e:
                logger.warning(f"Duration detection failed with {method_name}: {e}")
                continue
        
        logger.error(f"All duration detection methods failed for: {audio_path}")
        return 0.0
    
    def _get_duration_torchaudio(self, audio_path: str) -> float:
        """Get duration using torchaudio (most reliable for various formats)"""
        info = torchaudio.info(audio_path)
        return info.num_frames / info.sample_rate
    
    def _get_duration_pydub(self, audio_path: str) -> float:
        """Get duration using pydub (good fallback)"""
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0  # Convert ms to seconds
    
    def _get_duration_ffprobe(self, audio_path: str) -> float:
        """Get duration using ffprobe command (most comprehensive)"""
        import subprocess
        import json
        
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise Exception(f"ffprobe failed: {result.stderr}")
        
        data = json.loads(result.stdout)
        duration_str = data.get('format', {}).get('duration')
        if duration_str:
            return float(duration_str)
        
        raise Exception("Duration not found in ffprobe output")
    
    def estimate_duration_from_file_size(self, file_size: int, file_extension: str) -> float:
        """
        Estimate audio duration from file size using format-aware compression ratios
        
        Args:
            file_size: File size in bytes
            file_extension: File extension (e.g., '.mp3', '.wav', '.m4a')
            
        Returns:
            Estimated duration in seconds
        """
        # Format-specific compression ratios (MB per minute)
        # Adjusted to more conservative estimates for typical user uploads
        compression_ratios = {
            '.mp3': 1.0,    # ~1MB per minute (more conservative for typical MP3s)
            '.wav': 10.0,   # Uncompressed WAV
            '.m4a': 0.5,    # ~0.5MB per minute (conservative M4A/AAC)
            '.mp4': 0.8,    # ~0.8MB per minute (MP4 audio)
            '.flac': 5.0,   # Lossless compression
            '.ogg': 0.8,    # ~0.8MB per minute OGG Vorbis
            '.aac': 0.5,    # ~0.5MB per minute AAC
        }
        
        # Default to MP3 ratio if format unknown
        mb_per_minute = compression_ratios.get(file_extension.lower(), 1.0)
        
        # Calculate estimated duration
        file_size_mb = file_size / (1024 * 1024)
        estimated_minutes = file_size_mb / mb_per_minute
        estimated_seconds = estimated_minutes * 60
        
        logger.info(f"Format-aware estimation for {file_extension}: "
                   f"{file_size_mb:.2f}MB ÷ {mb_per_minute}MB/min = {estimated_minutes:.2f}min = {estimated_seconds:.2f}s")
        
        return estimated_seconds
    
    def get_audio_duration_with_fallback(self, audio_path: str, file_size: int) -> float:
        """
        Get audio duration with intelligent fallback to format-aware estimation
        
        Args:
            audio_path: Path to audio file
            file_size: File size in bytes
            
        Returns:
            Duration in seconds
        """
        # First try to get actual duration
        actual_duration = self.get_audio_duration(audio_path)
        
        if actual_duration > 0:
            return actual_duration
        
        # Fallback to format-aware estimation
        file_extension = os.path.splitext(audio_path)[1]
        estimated_duration = self.estimate_duration_from_file_size(file_size, file_extension)
        
        logger.warning(f"Using format-aware estimation for {audio_path}: {estimated_duration:.2f}s")
        return estimated_duration
    
    def create_vad_aware_chunks(self, audio_path: str, meeting: Meeting) -> List[Tuple[float, float]]:
        """
        Create chunks using VAD to respect speech boundaries
        
        Args:
            audio_path: Path to audio file
            meeting: Meeting instance
            
        Returns:
            List of (start_time, end_time) tuples in seconds
        """
        try:
            logger.info("Attempting VAD-aware chunking")
            
            # Get speech segments using existing VAD detection
            speech_segments = detect_speech_segments(audio_path)
            
            if not speech_segments or len(speech_segments) == 1:
                logger.info("VAD detection failed or found single segment, falling back to time-based")
                return self.create_time_based_chunks(audio_path)
            
            chunks = []
            current_chunk_start = 0.0
            current_chunk_duration = 0.0
            
            for start, end in speech_segments:
                # Check if we've reached chunk limit
                if len(chunks) >= self.max_chunks:
                    logger.warning(f"Reached maximum chunk limit of {self.max_chunks} during VAD chunking")
                    break
                
                segment_duration = end - start if end else self.chunk_duration
                
                # If adding this segment would exceed chunk duration, finalize current chunk
                if (current_chunk_duration + segment_duration > self.chunk_duration and 
                    current_chunk_duration >= self.min_chunk_duration):
                    
                    # Add overlap to the end
                    chunk_end = min(start + self.overlap_duration, end if end else start + segment_duration)
                    chunks.append((current_chunk_start, chunk_end))
                    
                    # Start new chunk with overlap
                    current_chunk_start = max(0, start - self.overlap_duration)
                    current_chunk_duration = segment_duration + self.overlap_duration
                else:
                    # Add segment to current chunk
                    current_chunk_duration += segment_duration
            
            # Add final chunk if there's remaining content
            if current_chunk_duration >= self.min_chunk_duration:
                audio_duration = self.get_audio_duration(audio_path)
                chunks.append((current_chunk_start, audio_duration))
            
            logger.info(f"VAD-aware chunking created {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.warning(f"VAD-aware chunking failed: {e}, falling back to time-based")
            return self.create_time_based_chunks(audio_path)
    
    def create_time_based_chunks(self, audio_path: str) -> List[Tuple[float, float]]:
        """
        Create chunks based on time intervals
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            List of (start_time, end_time) tuples in seconds
        """
        try:
            audio_duration = self.get_audio_duration(audio_path)
            
            if audio_duration <= self.chunk_duration:
                return [(0.0, audio_duration)]
            
            chunks = []
            current_start = 0.0
            
            while current_start < audio_duration and len(chunks) < self.max_chunks:
                chunk_end = min(current_start + self.chunk_duration, audio_duration)
                chunks.append((current_start, chunk_end))
                
                # Next chunk starts with overlap
                current_start += self.chunk_duration - self.overlap_duration
                
                # Avoid very small final chunks
                if audio_duration - current_start < self.min_chunk_duration:
                    # Extend the last chunk to include remaining audio
                    if chunks:
                        chunks[-1] = (chunks[-1][0], audio_duration)
                    break
            
            if len(chunks) >= self.max_chunks:
                logger.warning(f"Reached maximum chunk limit of {self.max_chunks}. "
                              f"Remaining audio duration: {audio_duration - current_start:.1f}s")
                break
                
            if audio_duration > self.max_duration:
                logger.warning(f"Audio duration {audio_duration:.1f}s exceeds maximum {self.max_duration}s. "
                              f"Processing only first {self.max_duration}s")
                # Adjust audio duration to maximum allowed
                audio_duration = min(audio_duration, self.max_duration)
            
            logger.info(f"Time-based chunking created {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Time-based chunking failed: {e}")
            return [(0.0, self.chunk_duration)]  # Fallback to single chunk
    
    def save_audio_chunk(self, audio_path: str, start_time: float, end_time: float, 
                        output_path: str) -> bool:
        """
        Save a chunk of audio to a separate file
        
        Args:
            audio_path: Source audio file path
            start_time: Start time in seconds
            end_time: End time in seconds
            output_path: Output file path
            
        Returns:
            True if successful
        """
        try:
            # Use pydub for reliable chunking across formats
            audio = AudioSegment.from_file(audio_path)
            
            # Convert seconds to milliseconds
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            
            # Extract chunk
            chunk = audio[start_ms:end_ms]
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Export chunk (maintain original format when possible)
            chunk.export(output_path, format="wav")  # WAV for reliability
            
            logger.info(f"Saved chunk: {start_time:.1f}s-{end_time:.1f}s to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save audio chunk: {e}")
            return False
    
    def chunk_audio_file(self, meeting: Meeting) -> bool:
        """
        Main method to chunk an audio file for a meeting
        
        Args:
            meeting: Meeting instance with audio file
            
        Returns:
            True if chunking was successful
        """
        try:
            if not meeting.audio_file:
                logger.error("Meeting has no audio file to chunk")
                return False
            
            audio_path = meeting.audio_file.path
            if not os.path.exists(audio_path):
                logger.error(f"Audio file not found: {audio_path}")
                return False
            
            # Check if chunking is needed
            if not self.should_chunk_file(meeting.file_size or 0):
                logger.info("File size below chunking threshold, skipping")
                return True
            
            logger.info(f"Starting chunking for meeting {meeting.id}")
            
            # Create chunk time segments using VAD-aware method
            chunk_segments = self.create_vad_aware_chunks(audio_path, meeting)
            
            if not chunk_segments:
                logger.error("No chunks created")
                return False
            
            # Create AudioChunk records and save chunk files
            for idx, (start_time, end_time) in enumerate(chunk_segments):
                # Generate chunk file path
                chunk_filename = f"chunk_{idx:03d}_{start_time:.1f}s-{end_time:.1f}s.wav"
                chunk_dir = os.path.join(os.path.dirname(audio_path), "chunks")
                chunk_path = os.path.join(chunk_dir, chunk_filename)
                
                # Save audio chunk
                if not self.save_audio_chunk(audio_path, start_time, end_time, chunk_path):
                    logger.error(f"Failed to save chunk {idx}")
                    continue
                
                # Get chunk file size
                chunk_size = os.path.getsize(chunk_path) if os.path.exists(chunk_path) else 0
                
                # Create AudioChunk record
                chunk = AudioChunk.objects.create(
                    meeting=meeting,
                    chunk_index=idx,
                    start_time=start_time,
                    end_time=end_time,
                    duration=end_time - start_time,
                    file_path=chunk_path,
                    file_size=chunk_size,
                    status='pending'
                )
                
                logger.info(f"Created chunk {idx}: {start_time:.1f}s-{end_time:.1f}s")
                
                # Add chunk to progressive transcription queue immediately
                try:
                    from .progressive_transcription import add_chunk_to_transcription_queue
                    add_chunk_to_transcription_queue(chunk)
                    logger.info(f"Added chunk {idx} to transcription queue")
                except Exception as e:
                    logger.error(f"Failed to add chunk {idx} to transcription queue: {e}")
            
            logger.info(f"Successfully created {len(chunk_segments)} chunks for meeting {meeting.id}")
            
            # Mark chunking as complete for progressive transcription
            try:
                from .progressive_transcription import mark_chunking_complete
                mark_chunking_complete(meeting, len(chunk_segments))
            except Exception as e:
                logger.error(f"Failed to mark chunking complete: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Audio chunking failed: {e}")
            # Also mark chunking complete on failure (with no expected count)
            try:
                from .progressive_transcription import mark_chunking_complete
                mark_chunking_complete(meeting, 0)
            except Exception:
                pass
            return False


def chunk_meeting_audio(meeting: Meeting) -> bool:
    """
    Convenience function to chunk audio for a meeting
    
    Args:
        meeting: Meeting instance
        
    Returns:
        True if successful
    """
    chunker = AudioChunker()
    return chunker.chunk_audio_file(meeting)


def cleanup_chunks(meeting: Meeting) -> bool:
    """
    Clean up chunk files for a meeting
    
    Args:
        meeting: Meeting instance
        
    Returns:
        True if successful
    """
    try:
        chunks = meeting.chunks.all()
        
        for chunk in chunks:
            if chunk.file_path and os.path.exists(chunk.file_path):
                try:
                    os.remove(chunk.file_path)
                    logger.info(f"Removed chunk file: {chunk.file_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove chunk file {chunk.file_path}: {e}")
        
        # Remove chunk directory if empty
        if chunks.exists():
            chunk_dir = os.path.dirname(chunks.first().file_path)
            if os.path.exists(chunk_dir) and not os.listdir(chunk_dir):
                try:
                    os.rmdir(chunk_dir)
                    logger.info(f"Removed empty chunk directory: {chunk_dir}")
                except Exception as e:
                    logger.warning(f"Failed to remove chunk directory: {e}")
        
        # Delete chunk records
        chunks.delete()
        logger.info(f"Cleaned up chunks for meeting {meeting.id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to cleanup chunks: {e}")
        return False