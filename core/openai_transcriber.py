"""
OpenAI Whisper API Transcriber

Implements external transcription using OpenAI's Whisper API service.
"""

import logging
import requests
from typing import Dict, Any, List
from .external_transcribers import ExternalAPITranscriber, TranscriptionResult

logger = logging.getLogger(__name__)


class OpenAITranscriber(ExternalAPITranscriber):
    """OpenAI Whisper API transcription implementation"""
    
    def configure_provider(self):
        """Configure OpenAI-specific settings"""
        self.base_url = "https://api.openai.com/v1"
        self.transcription_endpoint = f"{self.base_url}/audio/transcriptions"
        
        # OpenAI-specific settings
        self.temperature = 0.2  # Lower temperature for more consistent results
        self.response_format = "verbose_json"  # Get detailed response with timestamps
    
    def _get_default_model(self) -> str:
        """Get default model for OpenAI"""
        return "whisper-1"
    
    def _get_max_file_size(self) -> int:
        """OpenAI has a 25MB file size limit"""
        return 25 * 1024 * 1024  # 25MB
    
    def _get_allowed_formats(self) -> List[str]:
        """OpenAI supported formats"""
        return ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm']
    
    def _prepare_request_data(self, audio_file_path: str, **kwargs) -> tuple:
        """
        Prepare OpenAI API request data
        
        Args:
            audio_file_path: Path to audio file
            **kwargs: Additional parameters including language
            
        Returns:
            Tuple of (url, headers, files, request_type)
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Prepare form data
        files = {
            "file": open(audio_file_path, "rb"),
            "model": (None, self.api_model),
            "response_format": (None, self.response_format),
            "temperature": (None, str(self.temperature))
        }
        
        # Add language if specified
        language = kwargs.get('language')
        if language and language != 'auto':
            files["language"] = (None, language)
        
        # Add prompt for better accuracy (optional)
        prompt = kwargs.get('prompt')
        if prompt:
            files["prompt"] = (None, prompt)
        
        return self.transcription_endpoint, headers, files, 'files'
    
    def _parse_response(self, response: requests.Response) -> TranscriptionResult:
        """
        Parse OpenAI API response
        
        Args:
            response: API response object
            
        Returns:
            TranscriptionResult object
        """
        data = response.json()
        
        # Extract text
        text = data.get('text', '').strip()
        
        # Extract language (if detected)
        language = data.get('language')
        
        # Calculate confidence from segments if available
        confidence = None
        if 'segments' in data and data['segments']:
            confidences = [segment.get('avg_logprob', 0) for segment in data['segments'] 
                          if segment.get('avg_logprob') is not None]
            if confidences:
                # Convert log probabilities to confidence scores (approximate)
                confidence = sum(confidences) / len(confidences)
                confidence = max(0, min(1, (confidence + 1) / 1))  # Normalize to 0-1
        
        # Word count
        word_count = len(text.split()) if text else 0
        
        return TranscriptionResult(
            text=text,
            confidence=confidence,
            language=language,
            word_count=word_count
        )
    
    def validate_configuration(self) -> tuple[bool, str]:
        """
        Validate OpenAI-specific configuration
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Call parent validation first
        is_valid, error_msg = super().validate_configuration()
        if not is_valid:
            return is_valid, error_msg
        
        # Validate API key format (should start with 'sk-')
        if not self.api_key.startswith('sk-'):
            return False, "Invalid OpenAI API key format (should start with 'sk-')"
        
        # Validate model
        valid_models = ['whisper-1']
        if self.api_model not in valid_models:
            return False, f"Invalid OpenAI model: {self.api_model}. Valid models: {', '.join(valid_models)}"
        
        return True, ""
    
    def get_usage_info(self) -> Dict[str, Any]:
        """
        Get OpenAI-specific usage information
        
        Returns:
            Dictionary with usage information
        """
        info = super().get_usage_info()
        info.update({
            'pricing': '$0.006 per minute',
            'features': [
                'Multi-language support (99+ languages)',
                'Automatic language detection',
                'High accuracy transcription',
                'Detailed timestamps and confidence scores'
            ],
            'documentation': 'https://platform.openai.com/docs/guides/speech-to-text',
            'rate_limits': 'Standard API rate limits apply',
            'supported_languages': [
                'English', 'Thai', 'Chinese', 'Spanish', 'French', 'German',
                'Italian', 'Portuguese', 'Russian', 'Japanese', 'Korean',
                'Arabic', 'Hindi', 'and 90+ more languages'
            ]
        })
        return info
    
    def estimate_cost(self, duration_minutes: float) -> Dict[str, Any]:
        """
        Estimate transcription cost for given duration
        
        Args:
            duration_minutes: Audio duration in minutes
            
        Returns:
            Cost estimation dictionary
        """
        cost_per_minute = 0.006  # $0.006 per minute
        total_cost = duration_minutes * cost_per_minute
        
        return {
            'duration_minutes': duration_minutes,
            'cost_per_minute_usd': cost_per_minute,
            'estimated_cost_usd': total_cost,
            'currency': 'USD',
            'notes': 'Pricing as of 2024. Check OpenAI pricing page for current rates.'
        }