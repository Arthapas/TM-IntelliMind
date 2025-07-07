"""
Custom API Transcriber

Implements external transcription using custom API endpoints.
Provides a flexible interface for integrating with any compatible transcription API.
"""

import logging
import requests
from typing import Dict, Any, List
from .external_transcribers import ExternalAPITranscriber, TranscriptionResult

logger = logging.getLogger(__name__)


class CustomAPITranscriber(ExternalAPITranscriber):
    """Custom API endpoint transcription implementation"""
    
    def configure_provider(self):
        """Configure custom API-specific settings"""
        # Use the custom endpoint from meeting configuration
        self.transcription_endpoint = self.api_endpoint
        
        # Default settings for custom APIs
        self.request_format = "multipart/form-data"  # Can be overridden
        self.response_format = "json"  # Expected response format
        
        # Custom API configuration (can be extended)
        self.custom_headers = {}
        self.custom_params = {}
    
    def _get_default_model(self) -> str:
        """Get default model for custom API"""
        return "custom"
    
    def _get_max_file_size(self) -> int:
        """Default file size limit for custom APIs (can be overridden)"""
        return 100 * 1024 * 1024  # 100MB default
    
    def _get_allowed_formats(self) -> List[str]:
        """Default allowed formats for custom APIs"""
        return ['.mp3', '.wav', '.m4a', '.mp4', '.flac', '.webm', '.ogg']
    
    def _prepare_request_data(self, audio_file_path: str, **kwargs) -> tuple:
        """
        Prepare custom API request data
        
        Args:
            audio_file_path: Path to audio file
            **kwargs: Additional parameters including language
            
        Returns:
            Tuple of (url, headers, data_or_files, request_type)
        """
        # Base headers
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            **self.custom_headers
        }
        
        # Prepare data based on request format
        if self.request_format == "multipart/form-data":
            # Form data with file upload
            files = {
                "audio": open(audio_file_path, "rb"),
                "model": (None, self.api_model)
            }
            
            # Add language if specified
            language = kwargs.get('language')
            if language and language != 'auto':
                files["language"] = (None, language)
            
            # Add custom parameters
            for key, value in self.custom_params.items():
                files[key] = (None, str(value))
            
            return self.transcription_endpoint, headers, files, 'files'
        
        else:
            # JSON data (assuming file URL or base64 encoding)
            # This would require pre-uploading the file or encoding it
            data = {
                "model": self.api_model,
                **self.custom_params
            }
            
            # Add language if specified
            language = kwargs.get('language')
            if language and language != 'auto':
                data["language"] = language
            
            # Note: This implementation assumes file upload via form data
            # For JSON APIs, you'd need to implement file uploading separately
            headers["Content-Type"] = "application/json"
            
            return self.transcription_endpoint, headers, data, 'json'
    
    def _parse_response(self, response: requests.Response) -> TranscriptionResult:
        """
        Parse custom API response
        
        Args:
            response: API response object
            
        Returns:
            TranscriptionResult object
        """
        try:
            data = response.json()
        except ValueError:
            # If response is not JSON, treat as plain text
            text = response.text.strip()
            return TranscriptionResult(
                text=text,
                confidence=None,
                language=None,
                word_count=len(text.split()) if text else 0
            )
        
        # Try common response formats
        text = None
        confidence = None
        language = None
        word_count = None
        
        # Format 1: Direct text field
        if 'text' in data:
            text = data['text']
        elif 'transcript' in data:
            text = data['transcript']
        elif 'transcription' in data:
            text = data['transcription']
        
        # Format 2: Nested in results
        elif 'results' in data:
            results = data['results']
            if isinstance(results, list) and results:
                result = results[0]
                text = result.get('text') or result.get('transcript')
            elif isinstance(results, dict):
                text = results.get('text') or results.get('transcript')
        
        # Format 3: OpenAI-style response
        elif 'choices' in data and data['choices']:
            text = data['choices'][0].get('text', '')
        
        # Clean up text
        if text:
            text = text.strip()
        
        # Extract confidence if available
        confidence_fields = ['confidence', 'score', 'accuracy']
        for field in confidence_fields:
            if field in data:
                confidence = data[field]
                break
        
        # Extract language if available
        language_fields = ['language', 'detected_language', 'language_code']
        for field in language_fields:
            if field in data:
                language = data[field]
                break
        
        # Extract word count if available
        if 'word_count' in data:
            word_count = data['word_count']
        elif 'words' in data:
            words = data['words']
            if isinstance(words, list):
                word_count = len(words)
            elif isinstance(words, int):
                word_count = words
        
        # Calculate word count from text if not provided
        if not word_count and text:
            word_count = len(text.split())
        
        return TranscriptionResult(
            text=text or "",
            confidence=confidence,
            language=language,
            word_count=word_count or 0
        )
    
    def validate_configuration(self) -> tuple[bool, str]:
        """
        Validate custom API-specific configuration
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Call parent validation first
        is_valid, error_msg = super().validate_configuration()
        if not is_valid:
            return is_valid, error_msg
        
        # Validate endpoint URL
        if not self.api_endpoint:
            return False, "Custom API endpoint URL is required"
        
        if not self.api_endpoint.startswith(('http://', 'https://')):
            return False, "Custom API endpoint must be a valid HTTP/HTTPS URL"
        
        return True, ""
    
    def test_connection(self) -> tuple[bool, str]:
        """
        Test connection to custom API endpoint
        
        Returns:
            Tuple of (is_connected, message)
        """
        try:
            # Try a simple GET request to test connectivity
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                **self.custom_headers
            }
            
            response = requests.get(
                self.api_endpoint,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 404, 405]:  # 404/405 might be expected for POST-only endpoints
                return True, f"Connection successful (HTTP {response.status_code})"
            else:
                return False, f"Connection failed: HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "Connection timeout - endpoint not reachable"
        except requests.exceptions.ConnectionError:
            return False, "Connection error - check endpoint URL"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"
    
    def get_usage_info(self) -> Dict[str, Any]:
        """
        Get custom API-specific usage information
        
        Returns:
            Dictionary with usage information
        """
        info = super().get_usage_info()
        info.update({
            'endpoint': self.api_endpoint,
            'request_format': self.request_format,
            'response_format': self.response_format,
            'custom_headers': list(self.custom_headers.keys()),
            'custom_params': list(self.custom_params.keys()),
            'features': [
                'Custom endpoint integration',
                'Flexible request/response format',
                'Configurable parameters',
                'Custom authentication'
            ],
            'notes': [
                'Ensure your API endpoint accepts multipart/form-data requests',
                'Response should be JSON with text/transcript field',
                'API should return HTTP 200 for successful transcriptions',
                'Consider implementing proper error handling in your API'
            ],
            'supported_response_formats': [
                '{"text": "transcribed text"}',
                '{"transcript": "transcribed text"}',
                '{"results": {"text": "transcribed text"}}',
                '{"results": [{"text": "transcribed text"}]}',
                'Plain text response'
            ]
        })
        return info
    
    def set_custom_headers(self, headers: Dict[str, str]):
        """
        Set custom headers for API requests
        
        Args:
            headers: Dictionary of custom headers
        """
        self.custom_headers.update(headers)
    
    def set_custom_params(self, params: Dict[str, Any]):
        """
        Set custom parameters for API requests
        
        Args:
            params: Dictionary of custom parameters
        """
        self.custom_params.update(params)
    
    def set_request_format(self, format_type: str):
        """
        Set request format for API calls
        
        Args:
            format_type: 'multipart/form-data' or 'application/json'
        """
        if format_type in ['multipart/form-data', 'application/json']:
            self.request_format = format_type
        else:
            raise ValueError(f"Unsupported request format: {format_type}")
    
    def estimate_cost(self, duration_minutes: float) -> Dict[str, Any]:
        """
        Provide generic cost estimation template for custom APIs
        
        Args:
            duration_minutes: Audio duration in minutes
            
        Returns:
            Cost estimation template
        """
        return {
            'duration_minutes': duration_minutes,
            'cost_per_minute_usd': 'Unknown - depends on your API',
            'estimated_cost_usd': 'Contact your API provider',
            'currency': 'Varies',
            'notes': 'Cost estimation not available for custom APIs. Check with your API provider for pricing information.'
        }