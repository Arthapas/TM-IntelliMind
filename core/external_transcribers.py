"""
External API Transcription Services

This module provides a unified interface for various external transcription APIs,
including OpenAI Whisper API, AssemblyAI, Deepgram, and custom endpoints.
"""

import logging
import requests
import time
import base64
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from django.conf import settings
from .models import Meeting, AudioChunk

logger = logging.getLogger(__name__)


class TranscriptionResult:
    """Container for transcription results from external APIs"""
    
    def __init__(self, text: str, confidence: float = None, language: str = None, 
                 word_count: int = None, processing_time: float = None):
        self.text = text
        self.confidence = confidence
        self.language = language
        self.word_count = word_count or len(text.split()) if text else 0
        self.processing_time = processing_time
        self.timestamp = time.time()


class ExternalAPITranscriber(ABC):
    """
    Abstract base class for external transcription API providers
    
    Provides a unified interface for different transcription services with
    common functionality like file handling, error management, and retry logic.
    """
    
    def __init__(self, meeting: Meeting):
        """
        Initialize transcriber with meeting configuration
        
        Args:
            meeting: Meeting instance with API configuration
        """
        self.meeting = meeting
        self.api_key = self._decrypt_api_key(meeting.api_credentials) if meeting.api_credentials else None
        self.api_endpoint = meeting.api_endpoint
        self.api_model = meeting.api_model or self._get_default_model()
        self.timeout = getattr(settings, 'EXTERNAL_API_TIMEOUT', 300)  # 5 minutes default
        self.max_retries = getattr(settings, 'EXTERNAL_API_MAX_RETRIES', 2)
        
        # Provider-specific configuration
        self.configure_provider()
    
    def _decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt API key from database storage"""
        try:
            return base64.b64decode(encrypted_key.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {e}")
            return None
    
    @abstractmethod
    def configure_provider(self):
        """Configure provider-specific settings"""
        pass
    
    @abstractmethod
    def _get_default_model(self) -> str:
        """Get default model for this provider"""
        pass
    
    @abstractmethod
    def _prepare_request_data(self, audio_file_path: str, **kwargs) -> tuple:
        """
        Prepare request data for API call
        
        Args:
            audio_file_path: Path to audio file to transcribe
            **kwargs: Additional parameters
            
        Returns:
            Tuple of (url, headers, data/files, request_type)
        """
        pass
    
    @abstractmethod
    def _parse_response(self, response: requests.Response) -> TranscriptionResult:
        """
        Parse API response into TranscriptionResult
        
        Args:
            response: Raw API response
            
        Returns:
            TranscriptionResult object
        """
        pass
    
    def validate_configuration(self) -> tuple[bool, str]:
        """
        Validate API configuration
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.api_key:
            return False, "API key is required"
        
        if self.meeting.transcription_provider == 'custom' and not self.api_endpoint:
            return False, "Custom endpoint URL is required"
        
        return True, ""
    
    def check_file_limits(self, file_path: str) -> tuple[bool, str]:
        """
        Check if file meets provider's size and format requirements
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        import os
        
        if not os.path.exists(file_path):
            return False, f"Audio file not found: {file_path}"
        
        file_size = os.path.getsize(file_path)
        max_size = self._get_max_file_size()
        
        if file_size > max_size:
            return False, f"File too large: {file_size / (1024*1024):.1f}MB exceeds {max_size / (1024*1024):.1f}MB limit"
        
        # Check format
        allowed_formats = self._get_allowed_formats()
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in allowed_formats:
            return False, f"Unsupported format: {file_ext}. Allowed: {', '.join(allowed_formats)}"
        
        return True, ""
    
    def _get_max_file_size(self) -> int:
        """Get maximum file size for this provider (in bytes)"""
        # Default to 25MB (OpenAI's limit)
        return 25 * 1024 * 1024
    
    def _get_allowed_formats(self) -> List[str]:
        """Get list of allowed file formats for this provider"""
        return ['.mp3', '.wav', '.m4a', '.mp4', '.webm']
    
    def transcribe_file(self, audio_file_path: str, language: str = None, **kwargs) -> TranscriptionResult:
        """
        Transcribe audio file using external API
        
        Args:
            audio_file_path: Path to audio file
            language: Language code (optional)
            **kwargs: Additional transcription parameters
            
        Returns:
            TranscriptionResult object
            
        Raises:
            Exception: If transcription fails after all retries
        """
        start_time = time.time()
        
        # Validate configuration
        is_valid, error_msg = self.validate_configuration()
        if not is_valid:
            raise Exception(f"Configuration error: {error_msg}")
        
        # Check file limits
        is_valid, error_msg = self.check_file_limits(audio_file_path)
        if not is_valid:
            raise Exception(f"File validation error: {error_msg}")
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Transcription attempt {attempt + 1}/{self.max_retries + 1} for {audio_file_path}")
                
                # Prepare request
                url, headers, data_or_files, request_type = self._prepare_request_data(
                    audio_file_path, language=language, **kwargs
                )
                
                # Make API request
                if request_type == 'files':
                    response = requests.post(url, headers=headers, files=data_or_files, timeout=self.timeout)
                else:
                    response = requests.post(url, headers=headers, json=data_or_files, timeout=self.timeout)
                
                # Check response
                if response.status_code == 200:
                    result = self._parse_response(response)
                    result.processing_time = time.time() - start_time
                    
                    logger.info(f"Transcription successful: {len(result.text)} characters, "
                              f"{result.word_count} words, {result.processing_time:.2f}s")
                    
                    return result
                else:
                    error_msg = f"API request failed: {response.status_code} - {response.text}"
                    logger.warning(error_msg)
                    last_error = Exception(error_msg)
                    
                    # Don't retry on certain errors
                    if response.status_code in [400, 401, 403]:
                        break
                    
            except requests.exceptions.Timeout:
                error_msg = f"Request timeout after {self.timeout}s"
                logger.warning(error_msg)
                last_error = Exception(error_msg)
                
            except requests.exceptions.RequestException as e:
                error_msg = f"Request error: {str(e)}"
                logger.warning(error_msg)
                last_error = Exception(error_msg)
                
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                logger.warning(error_msg)
                last_error = Exception(error_msg)
            
            # Wait before retry (exponential backoff)
            if attempt < self.max_retries:
                wait_time = (2 ** attempt) * 1.0  # 1s, 2s, 4s, etc.
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        # All retries failed
        total_time = time.time() - start_time
        error_msg = f"Transcription failed after {self.max_retries + 1} attempts in {total_time:.2f}s"
        logger.error(error_msg)
        
        if last_error:
            raise last_error
        else:
            raise Exception(error_msg)
    
    def transcribe_chunk(self, chunk: AudioChunk, language: str = None) -> bool:
        """
        Transcribe an audio chunk using external API
        
        Args:
            chunk: AudioChunk instance to transcribe
            language: Language code (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            chunk.status = 'processing'
            chunk.save()
            
            logger.info(f"Starting external API transcription for chunk {chunk.chunk_index} "
                       f"of meeting {chunk.meeting.id} using {self.meeting.transcription_provider}")
            
            # Transcribe the chunk file
            result = self.transcribe_file(chunk.file_path, language=language)
            
            # Update chunk with results
            chunk.transcript_text = result.text
            chunk.status = 'completed'
            chunk.progress = 100
            
            # Store additional metadata if available
            if hasattr(chunk, 'confidence_score') and result.confidence:
                chunk.confidence_score = result.confidence
            
            chunk.save()
            
            logger.info(f"External API transcription completed for chunk {chunk.chunk_index}: "
                       f"{len(result.text)} characters")
            
            return True
            
        except Exception as e:
            chunk.status = 'failed'
            chunk.error_message = f"External API transcription failed: {str(e)}"
            chunk.save()
            
            logger.error(f"External API transcription failed for chunk {chunk.chunk_index}: {e}")
            return False
    
    def get_usage_info(self) -> Dict[str, Any]:
        """
        Get usage information and cost estimates
        
        Returns:
            Dictionary with usage information
        """
        return {
            'provider': self.meeting.transcription_provider,
            'model': self.api_model,
            'max_file_size_mb': self._get_max_file_size() / (1024 * 1024),
            'allowed_formats': self._get_allowed_formats(),
            'timeout_seconds': self.timeout,
            'max_retries': self.max_retries
        }


def create_external_transcriber(meeting: Meeting) -> ExternalAPITranscriber:
    """
    Factory function to create appropriate external transcriber
    
    Args:
        meeting: Meeting instance with transcription configuration
        
    Returns:
        Configured ExternalAPITranscriber instance
        
    Raises:
        ValueError: If provider is not supported
    """
    provider = meeting.transcription_provider
    
    if provider == 'openai':
        from .openai_transcriber import OpenAITranscriber
        return OpenAITranscriber(meeting)
    elif provider == 'assemblyai':
        from .assemblyai_transcriber import AssemblyAITranscriber
        return AssemblyAITranscriber(meeting)
    elif provider == 'deepgram':
        from .deepgram_transcriber import DeepgramTranscriber
        return DeepgramTranscriber(meeting)
    elif provider == 'custom':
        from .custom_transcriber import CustomAPITranscriber
        return CustomAPITranscriber(meeting)
    else:
        raise ValueError(f"Unsupported transcription provider: {provider}")