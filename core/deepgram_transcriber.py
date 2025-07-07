"""
Deepgram Transcriber

Implements external transcription using Deepgram's Speech-to-Text API.
"""

import logging
import requests
from typing import Dict, Any, List
from .external_transcribers import ExternalAPITranscriber, TranscriptionResult

logger = logging.getLogger(__name__)


class DeepgramTranscriber(ExternalAPITranscriber):
    """Deepgram Speech-to-Text API transcription implementation"""
    
    def configure_provider(self):
        """Configure Deepgram-specific settings"""
        self.base_url = "https://api.deepgram.com/v1"
        self.transcription_endpoint = f"{self.base_url}/listen"
        
        # Deepgram-specific settings
        self.features = {
            'punctuate': True,
            'utterances': True,
            'smart_format': True,
            'diarize': False,  # Speaker diarization
            'sentiment': True,
            'summarize': False
        }
    
    def _get_default_model(self) -> str:
        """Get default model for Deepgram"""
        return "nova-2"  # Deepgram's latest high-accuracy model
    
    def _get_max_file_size(self) -> int:
        """Deepgram supports large files"""
        return 2 * 1024 * 1024 * 1024  # 2GB limit for batch processing
    
    def _get_allowed_formats(self) -> List[str]:
        """Deepgram supported formats"""
        return ['.mp3', '.mp4', '.wav', '.m4a', '.flac', '.webm', '.ogg', '.opus']
    
    def _prepare_request_data(self, audio_file_path: str, **kwargs) -> tuple:
        """
        Prepare Deepgram API request data
        
        Args:
            audio_file_path: Path to audio file
            **kwargs: Additional parameters including language
            
        Returns:
            Tuple of (url, headers, files, request_type)
        """
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/*"
        }
        
        # Build query parameters
        params = {
            'model': self.api_model,
            'version': 'latest'
        }
        
        # Add language if specified
        language = kwargs.get('language')
        if language and language != 'auto':
            params['language'] = language
        else:
            params['detect_language'] = 'true'
        
        # Add features
        params.update(self.features)
        
        # Build URL with query parameters
        param_string = '&'.join([f"{k}={'true' if v is True else 'false' if v is False else str(v)}" 
                                for k, v in params.items()])
        url = f"{self.transcription_endpoint}?{param_string}"
        
        # Prepare file data
        files = {
            'audio': open(audio_file_path, 'rb')
        }
        
        return url, headers, files, 'files'
    
    def _parse_response(self, response: requests.Response) -> TranscriptionResult:
        """
        Parse Deepgram API response
        
        Args:
            response: API response object
            
        Returns:
            TranscriptionResult object
        """
        data = response.json()
        
        # Extract text from results
        text = ""
        confidence = None
        language = None
        word_count = 0
        
        if 'results' in data and data['results']['channels']:
            channel = data['results']['channels'][0]
            
            if 'alternatives' in channel and channel['alternatives']:
                alternative = channel['alternatives'][0]
                text = alternative.get('transcript', '').strip()
                confidence = alternative.get('confidence', 0)
                
                # Count words from words array if available
                if 'words' in alternative:
                    word_count = len(alternative['words'])
                else:
                    word_count = len(text.split()) if text else 0
            
            # Extract detected language
            if 'detected_language' in channel:
                language = channel['detected_language']
        
        return TranscriptionResult(
            text=text,
            confidence=confidence,
            language=language,
            word_count=word_count
        )
    
    def validate_configuration(self) -> tuple[bool, str]:
        """
        Validate Deepgram-specific configuration
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Call parent validation first
        is_valid, error_msg = super().validate_configuration()
        if not is_valid:
            return is_valid, error_msg
        
        # Validate model
        valid_models = ['nova-2', 'nova', 'enhanced', 'base']
        if self.api_model not in valid_models:
            return False, f"Invalid Deepgram model: {self.api_model}. Valid models: {', '.join(valid_models)}"
        
        return True, ""
    
    def get_usage_info(self) -> Dict[str, Any]:
        """
        Get Deepgram-specific usage information
        
        Returns:
            Dictionary with usage information
        """
        info = super().get_usage_info()
        info.update({
            'pricing': 'Competitive rates (contact for pricing)',
            'features': [
                'Nova-2: 30% reduction in Word Error Rate',
                'Real-time and batch transcription',
                'Custom model training',
                'Domain-specific models (medical, finance)',
                'Smart formatting and punctuation',
                'Sentiment analysis',
                'Language detection',
                'Speaker diarization',
                'Custom vocabulary'
            ],
            'documentation': 'https://developers.deepgram.com/',
            'rate_limits': 'Enterprise-grade rate limits',
            'supported_languages': [
                'English', 'Spanish', 'French', 'German', 'Italian',
                'Portuguese', 'Dutch', 'Hindi', 'Japanese', 'Korean',
                'Chinese (Mandarin)', 'Russian', 'Arabic', 'Turkish',
                'Swedish', 'and more'
            ],
            'models': {
                'nova-2': 'Latest model with 30% WER reduction',
                'nova': 'High-accuracy general model',
                'enhanced': 'Legacy enhanced model',
                'base': 'Standard accuracy model'
            },
            'specialized_models': [
                'Nova-2 Medical',
                'Nova-2 Finance',
                'Nova-2 Conversational AI',
                'Custom domain models'
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
        # Deepgram typically charges per minute with volume discounts
        # These are estimated rates - actual pricing varies
        cost_per_minute = 0.0125  # Estimated $0.0125 per minute
        
        # Volume discount tiers (estimated)
        if duration_minutes > 10000:  # 166+ hours
            cost_per_minute *= 0.7  # 30% discount
        elif duration_minutes > 1000:  # 16+ hours
            cost_per_minute *= 0.85  # 15% discount
        
        total_cost = duration_minutes * cost_per_minute
        
        return {
            'duration_minutes': duration_minutes,
            'cost_per_minute_usd': cost_per_minute,
            'estimated_cost_usd': total_cost,
            'currency': 'USD',
            'notes': 'Estimated pricing. Contact Deepgram for actual rates and volume discounts.',
            'volume_discounts': 'Available for high-volume usage'
        }
    
    def get_model_info(self, model_name: str = None) -> Dict[str, Any]:
        """
        Get detailed information about specific Deepgram model
        
        Args:
            model_name: Model to get info for (defaults to current model)
            
        Returns:
            Model information dictionary
        """
        model = model_name or self.api_model
        
        model_info = {
            'nova-2': {
                'name': 'Nova-2',
                'description': 'Latest generation model with 30% WER reduction',
                'accuracy': 'Highest',
                'speed': 'Fast',
                'languages': '30+',
                'use_cases': ['General transcription', 'High-accuracy requirements']
            },
            'nova': {
                'name': 'Nova',
                'description': 'High-accuracy general-purpose model',
                'accuracy': 'High',
                'speed': 'Fast',
                'languages': '30+',
                'use_cases': ['General transcription', 'Production workloads']
            },
            'enhanced': {
                'name': 'Enhanced',
                'description': 'Legacy enhanced model',
                'accuracy': 'Medium-High',
                'speed': 'Medium',
                'languages': '20+',
                'use_cases': ['Legacy applications', 'Cost-sensitive workloads']
            },
            'base': {
                'name': 'Base',
                'description': 'Standard accuracy model',
                'accuracy': 'Medium',
                'speed': 'Fast',
                'languages': '15+',
                'use_cases': ['Basic transcription', 'High-volume processing']
            }
        }
        
        return model_info.get(model, {'name': model, 'description': 'Unknown model'})