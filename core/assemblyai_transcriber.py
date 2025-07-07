"""
AssemblyAI Transcriber

Implements external transcription using AssemblyAI's Speech-to-Text API.
"""

import logging
import requests
import time
from typing import Dict, Any, List
from .external_transcribers import ExternalAPITranscriber, TranscriptionResult

logger = logging.getLogger(__name__)


class AssemblyAITranscriber(ExternalAPITranscriber):
    """AssemblyAI Speech-to-Text API transcription implementation"""
    
    def configure_provider(self):
        """Configure AssemblyAI-specific settings"""
        self.base_url = "https://api.assemblyai.com/v2"
        self.upload_endpoint = f"{self.base_url}/upload"
        self.transcription_endpoint = f"{self.base_url}/transcript"
        
        # AssemblyAI-specific settings
        self.polling_interval = 2  # Poll every 2 seconds for status
        self.max_polling_time = 600  # Maximum 10 minutes polling
    
    def _get_default_model(self) -> str:
        """Get default model for AssemblyAI"""
        return "best"  # AssemblyAI's highest accuracy model
    
    def _get_max_file_size(self) -> int:
        """AssemblyAI supports files up to 5GB"""
        return 5 * 1024 * 1024 * 1024  # 5GB
    
    def _get_allowed_formats(self) -> List[str]:
        """AssemblyAI supported formats"""
        return ['.mp3', '.mp4', '.wav', '.m4a', '.flac', '.webm', '.ogg']
    
    def _upload_file(self, audio_file_path: str) -> str:
        """
        Upload file to AssemblyAI and get upload URL
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            Upload URL for transcription
        """
        headers = {
            "authorization": self.api_key,
            "content-type": "application/octet-stream"
        }
        
        with open(audio_file_path, 'rb') as f:
            response = requests.post(
                self.upload_endpoint,
                headers=headers,
                data=f,
                timeout=self.timeout
            )
        
        if response.status_code == 200:
            return response.json()['upload_url']
        else:
            raise Exception(f"File upload failed: {response.status_code} - {response.text}")
    
    def _prepare_request_data(self, audio_file_path: str, **kwargs) -> tuple:
        """
        Prepare AssemblyAI API request data
        
        Args:
            audio_file_path: Path to audio file
            **kwargs: Additional parameters including language
            
        Returns:
            Tuple of (url, headers, data, request_type)
        """
        # First upload the file
        upload_url = self._upload_file(audio_file_path)
        
        headers = {
            "authorization": self.api_key,
            "content-type": "application/json"
        }
        
        # Prepare transcription request data
        data = {
            "audio_url": upload_url,
            "speech_model": self.api_model
        }
        
        # Add language if specified
        language = kwargs.get('language')
        if language and language != 'auto':
            data["language_code"] = language
        else:
            data["language_detection"] = True
        
        # Enable additional features
        data.update({
            "punctuate": True,
            "format_text": True,
            "diarization": False,  # Speaker diarization
            "sentiment_analysis": True,
            "auto_highlights": True,
            "content_safety": False
        })
        
        return self.transcription_endpoint, headers, data, 'json'
    
    def _poll_transcription_status(self, transcript_id: str) -> Dict[str, Any]:
        """
        Poll AssemblyAI for transcription completion
        
        Args:
            transcript_id: ID of the transcription job
            
        Returns:
            Final transcription result data
        """
        headers = {
            "authorization": self.api_key
        }
        
        status_url = f"{self.transcription_endpoint}/{transcript_id}"
        start_time = time.time()
        
        while time.time() - start_time < self.max_polling_time:
            response = requests.get(status_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                
                if status == 'completed':
                    return data
                elif status == 'error':
                    error_msg = data.get('error', 'Unknown error')
                    raise Exception(f"Transcription failed: {error_msg}")
                elif status in ['queued', 'processing']:
                    logger.debug(f"Transcription {transcript_id} status: {status}")
                    time.sleep(self.polling_interval)
                else:
                    raise Exception(f"Unknown status: {status}")
            else:
                raise Exception(f"Status check failed: {response.status_code} - {response.text}")
        
        raise Exception(f"Transcription timeout after {self.max_polling_time}s")
    
    def _parse_response(self, response: requests.Response) -> TranscriptionResult:
        """
        Parse AssemblyAI API response
        
        Args:
            response: API response object (initial submission)
            
        Returns:
            TranscriptionResult object
        """
        # Initial response contains transcript ID
        initial_data = response.json()
        transcript_id = initial_data.get('id')
        
        if not transcript_id:
            raise Exception("No transcript ID returned from AssemblyAI")
        
        logger.info(f"AssemblyAI transcription started with ID: {transcript_id}")
        
        # Poll for completion
        data = self._poll_transcription_status(transcript_id)
        
        # Extract results
        text = data.get('text', '').strip()
        confidence = data.get('confidence', 0) / 100 if data.get('confidence') else None
        language = data.get('language_code')
        
        # Word count
        word_count = data.get('words')
        if isinstance(word_count, list):
            word_count = len(word_count)
        elif not word_count and text:
            word_count = len(text.split())
        
        return TranscriptionResult(
            text=text,
            confidence=confidence,
            language=language,
            word_count=word_count
        )
    
    def validate_configuration(self) -> tuple[bool, str]:
        """
        Validate AssemblyAI-specific configuration
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Call parent validation first
        is_valid, error_msg = super().validate_configuration()
        if not is_valid:
            return is_valid, error_msg
        
        # Validate model
        valid_models = ['best', 'nano']
        if self.api_model not in valid_models:
            return False, f"Invalid AssemblyAI model: {self.api_model}. Valid models: {', '.join(valid_models)}"
        
        return True, ""
    
    def get_usage_info(self) -> Dict[str, Any]:
        """
        Get AssemblyAI-specific usage information
        
        Returns:
            Dictionary with usage information
        """
        info = super().get_usage_info()
        info.update({
            'pricing': '~$0.65 per hour (varies by features)',
            'features': [
                'High accuracy transcription',
                'Automatic punctuation and formatting',
                'Language detection',
                'Sentiment analysis',
                'Content moderation',
                'Auto highlights',
                'Speaker diarization',
                'PII redaction'
            ],
            'documentation': 'https://www.assemblyai.com/docs/',
            'rate_limits': 'Generous rate limits',
            'supported_languages': [
                'English', 'Spanish', 'French', 'German', 'Italian',
                'Portuguese', 'Dutch', 'Hindi', 'Japanese', 'Chinese',
                'Korean', 'Russian', 'Arabic', 'Vietnamese', 'Ukrainian',
                'and more'
            ],
            'models': {
                'best': 'Highest accuracy, slower processing',
                'nano': 'Fastest processing, good accuracy'
            }
        })
        return info
    
    def estimate_cost(self, duration_hours: float) -> Dict[str, Any]:
        """
        Estimate transcription cost for given duration
        
        Args:
            duration_hours: Audio duration in hours
            
        Returns:
            Cost estimation dictionary
        """
        # Base transcription cost
        base_cost_per_hour = 0.65
        
        # Additional feature costs (estimated)
        feature_costs = {
            'sentiment_analysis': 0.1,
            'auto_highlights': 0.05,
            'content_safety': 0.1
        }
        
        total_cost = duration_hours * (base_cost_per_hour + sum(feature_costs.values()))
        
        return {
            'duration_hours': duration_hours,
            'base_cost_per_hour_usd': base_cost_per_hour,
            'feature_costs_per_hour_usd': feature_costs,
            'estimated_total_cost_usd': total_cost,
            'currency': 'USD',
            'notes': 'Pricing estimates. Check AssemblyAI pricing page for current rates.'
        }