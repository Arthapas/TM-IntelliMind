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
                 chunk_duration: float = 30.0,  # 30 seconds optimal for Whisper
                 overlap_duration: float = 5.0,  # 5 seconds overlap
                 max_chunk_duration: float = 60.0,  # Maximum chunk length
                 min_chunk_duration: float = 10.0):  # Minimum chunk length
        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        self.max_chunk_duration = max_chunk_duration
        self.min_chunk_duration = min_chunk_duration
    
    def should_chunk_file(self, file_size: int) -> bool:
        """
        Determine if a file should be chunked based on size
        
        Args:
            file_size: File size in bytes
            
        Returns:
            True if file should be chunked
        """
        # Chunk files larger than 100MB
        chunk_threshold = getattr(settings, 'AUDIO_CHUNK_THRESHOLD', 100 * 1024 * 1024)
        return file_size > chunk_threshold
    
    def get_audio_duration(self, audio_path: str) -> float:
        """
        Get audio duration in seconds
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Duration in seconds
        """
        try:
            # Try with torchaudio first (more reliable for various formats)
            info = torchaudio.info(audio_path)
            return info.num_frames / info.sample_rate
        except Exception:
            try:
                # Fallback to pydub
                audio = AudioSegment.from_file(audio_path)
                return len(audio) / 1000.0  # Convert ms to seconds
            except Exception as e:
                logger.error(f"Failed to get audio duration: {e}")
                return 0.0
    
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
            
            while current_start < audio_duration:
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
                AudioChunk.objects.create(
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
            
            logger.info(f"Successfully created {len(chunk_segments)} chunks for meeting {meeting.id}")
            return True
            
        except Exception as e:
            logger.error(f"Audio chunking failed: {e}")
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