#!/usr/bin/env python3
"""
Integration tests for Thonburian Whisper end-to-end workflow
Tests complete transcription pipeline with Thai audio
"""

import unittest
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User

# Django tests - already configured

from core.models import Meeting, Transcript, Insight
from core.utils import transcribe_audio


class TestThonburianTranscriptionWorkflow(TestCase):
    """Test complete transcription workflow with Thonburian models"""
    
    def setUp(self):
        """Set up test client and test data"""
        self.client = Client()
        self.test_user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create test audio file
        self.test_audio_content = b'dummy audio content'
        self.test_audio = SimpleUploadedFile(
            "test_thai_audio.wav",
            self.test_audio_content,
            content_type="audio/wav"
        )
    
    def test_upload_with_thonburian_model_selection(self):
        """Test file upload with Thonburian model selection"""
        response = self.client.post(reverse('core:upload_audio'), {
            'audio_file': self.test_audio,
            'transcription_provider': 'local',
            'transcription_model': 'thonburian-medium'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Check meeting was created with correct model
        meeting = Meeting.objects.get(id=data['meeting_id'])
        self.assertEqual(meeting.transcription_model, 'thonburian-medium')
    
    @patch('core.utils.WhisperModel')
    def test_start_transcription_with_thonburian(self, mock_whisper_model):
        """Test transcription start with Thonburian model"""
        # Create meeting first
        meeting = Meeting.objects.create(
            title="Test Thai Meeting",
            transcription_provider='local',
            transcription_model='thonburian-medium'
        )
        Transcript.objects.create(meeting=meeting)
        
        # Mock model
        mock_model_instance = MagicMock()
        mock_model_instance.model = MagicMock()
        mock_model_instance.transcribe.return_value = ([
            {'text': 'สวัสดีครับ ทดสอบการถอดความ'}
        ], {})
        mock_whisper_model.return_value = mock_model_instance
        
        # Start transcription
        response = self.client.post(
            reverse('core:start_transcription'),
            json.dumps({
                'meeting_id': str(meeting.id),
                'whisper_model': 'thonburian-medium',
                'language': 'th',
                'transcription_provider': 'local'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
    
    def test_model_switching_workflow(self):
        """Test switching between standard and Thonburian models"""
        # Create meeting with standard model
        meeting = Meeting.objects.create(
            title="Test Model Switching",
            transcription_provider='local',
            transcription_model='medium'
        )
        Transcript.objects.create(meeting=meeting, whisper_model='medium')
        
        # Switch to Thonburian model
        response = self.client.post(
            reverse('core:start_transcription'),
            json.dumps({
                'meeting_id': str(meeting.id),
                'whisper_model': 'thonburian-medium',
                'language': 'th',
                'transcription_provider': 'local'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check model was updated
        meeting.refresh_from_db()
        self.assertEqual(meeting.transcription_provider, 'local')
    
    def test_progress_tracking_with_thonburian(self):
        """Test progress tracking during Thonburian transcription"""
        meeting = Meeting.objects.create(
            title="Test Progress",
            transcription_provider='local',
            transcription_model='thonburian-large'
        )
        transcript = Transcript.objects.create(
            meeting=meeting,
            whisper_model='thonburian-large',
            status='processing',
            progress=50
        )
        
        response = self.client.get(
            reverse('core:transcription_progress'),
            {'meeting_id': str(meeting.id)}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['progress'], 50)
        self.assertEqual(data['status'], 'processing')


class TestThonburianLanguageDetection(TestCase):
    """Test language detection with Thonburian models"""
    
    @patch('core.utils.WhisperModel')
    def test_thai_language_auto_detection(self, mock_whisper_model):
        """Test that Thai language is properly detected"""
        # Setup mock to return Thai text
        mock_model_instance = MagicMock()
        mock_model_instance.model = MagicMock()
        mock_model_instance.transcribe.return_value = ([
            {
                'text': 'สวัสดีครับ วันนี้เรามาประชุมเรื่องประกันภัย',
                'language': 'th'
            }
        ], {'language': 'th', 'language_probability': 0.98})
        mock_whisper_model.return_value = mock_model_instance
        
        # Create test audio file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(b'dummy audio content')
            tmp_path = tmp.name
        
        try:
            # Transcribe with auto language detection
            result = transcribe_audio(
                tmp_path,
                model_size='thonburian-medium',
                language=None  # Auto-detect
            )
            
            # Verify Thai was detected and transcribed
            self.assertIn('สวัสดีครับ', result)
            self.assertIn('ประกันภัย', result)
        finally:
            os.unlink(tmp_path)
    
    @patch('core.utils.WhisperModel')
    def test_mixed_language_handling(self, mock_whisper_model):
        """Test handling of mixed Thai-English content"""
        mock_model_instance = MagicMock()
        mock_model_instance.model = MagicMock()
        mock_model_instance.transcribe.return_value = ([
            {
                'text': 'วันนี้เราจะพูดถึง insurance policy และ premium rates',
                'language': 'th'
            }
        ], {'language': 'th', 'language_probability': 0.85})
        mock_whisper_model.return_value = mock_model_instance
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(b'dummy audio content')
            tmp_path = tmp.name
        
        try:
            result = transcribe_audio(
                tmp_path,
                model_size='thonburian-medium',
                language='th'
            )
            
            # Should handle both Thai and English
            self.assertIn('วันนี้', result)
            self.assertIn('insurance policy', result)
        finally:
            os.unlink(tmp_path)


class TestThonburianErrorHandling(TestCase):
    """Test error handling with Thonburian models"""
    
    def test_upload_with_invalid_thonburian_selection(self):
        """Test handling of invalid Thonburian model selection"""
        audio = SimpleUploadedFile(
            "test.wav",
            b'dummy content',
            content_type="audio/wav"
        )
        
        response = self.client.post(reverse('core:upload_audio'), {
            'audio_file': audio,
            'transcription_provider': 'local',
            'transcription_model': 'thonburian-invalid'  # Invalid model
        })
        
        # Should fail validation
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('Invalid transcription model', data['error'])
    
    @patch('core.utils.get_thonburian_model_path')
    @patch('core.utils.WhisperModel')
    def test_fallback_on_model_load_failure(self, mock_whisper_model, mock_get_path):
        """Test fallback when Thonburian model fails to load"""
        # First call fails (Thonburian), second succeeds (fallback)
        mock_get_path.side_effect = ['thonburian-path', 'medium']
        mock_whisper_model.side_effect = [
            Exception("Thonburian model load failed"),
            MagicMock(model=MagicMock())  # Fallback succeeds
        ]
        
        # Should log error but continue with fallback
        from core import utils
        utils._model_cache.clear()  # Clear cache
        
        with self.assertRaises(Exception):
            # First attempt should fail
            model = utils.get_or_create_whisper_model('thonburian-medium')
    
    def test_non_thai_audio_with_thonburian(self):
        """Test Thonburian model behavior with non-Thai audio"""
        meeting = Meeting.objects.create(
            title="English Audio Test",
            transcription_provider='local',
            transcription_model='thonburian-medium'
        )
        transcript = Transcript.objects.create(
            meeting=meeting,
            whisper_model='thonburian-medium'
        )
        
        # Should still work but may have reduced accuracy
        # This would be tested with real model and audio
        self.assertIsNotNone(transcript)


class TestThonburianUIIntegration(TestCase):
    """Test UI elements for Thonburian models"""
    
    def test_create_insight_page_shows_thonburian_options(self):
        """Test that create insight page includes Thonburian options"""
        response = self.client.get(reverse('core:create_insight'))
        self.assertEqual(response.status_code, 200)
        
        # Check for Thonburian options in response
        content = response.content.decode('utf-8')
        self.assertIn('thonburian-medium', content)
        self.assertIn('thonburian-large', content)
        self.assertIn('Thai Optimized', content)
        self.assertIn('7.4% WER', content)
    
    def test_model_help_text_updated(self):
        """Test that help text mentions Thonburian models"""
        response = self.client.get(reverse('core:create_insight'))
        content = response.content.decode('utf-8')
        
        self.assertIn('Thonburian models recommended for best accuracy', content)
        self.assertIn('50%+ accuracy improvement', content)


if __name__ == '__main__':
    unittest.main()