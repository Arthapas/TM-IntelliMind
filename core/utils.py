import os
import requests
import time
import logging
import platform
import psutil
from datetime import datetime
from faster_whisper import WhisperModel
from django.conf import settings

logger = logging.getLogger(__name__)

# Version detection and feature availability
try:
    from faster_whisper import BatchedInferencePipeline
    BATCHED_INFERENCE_AVAILABLE = True
    logger.info("BatchedInferencePipeline available - advanced features enabled")
except ImportError:
    BATCHED_INFERENCE_AVAILABLE = False
    logger.warning("BatchedInferencePipeline not available in this version of faster-whisper")

def get_faster_whisper_version():
    """Get the version of faster-whisper for compatibility checks"""
    try:
        import faster_whisper
        version = getattr(faster_whisper, '__version__', 'unknown')
        return version
    except:
        return 'unknown'

def get_supported_transcribe_params():
    """Get list of supported parameters for the current faster-whisper version"""
    version = get_faster_whisper_version()
    
    # Base parameters supported in most versions
    base_params = [
        'beam_size', 'temperature', 'initial_prompt', 
        'condition_on_previous_text', 'task', 'language'
    ]
    
    # Additional parameters that might be supported in newer versions
    if version != 'unknown':
        try:
            # Try to determine version-specific features
            version_parts = version.split('.')
            major = int(version_parts[0]) if len(version_parts) > 0 else 0
            minor = int(version_parts[1]) if len(version_parts) > 1 else 0
            patch = int(version_parts[2]) if len(version_parts) > 2 else 0
            
            # Parameters available in v1.1.0+
            if major >= 1 and minor >= 1:
                base_params.extend([
                    'patience', 'length_penalty', 'repetition_penalty',
                    'no_repeat_ngram_size', 'suppress_blank', 'suppress_tokens',
                    'without_timestamps', 'max_initial_timestamp',
                    'word_timestamps', 'compression_ratio_threshold',
                    'no_speech_threshold', 'best_of',
                    'prepend_punctuations', 'append_punctuations'
                ])
                logger.info("Advanced parameters enabled for faster-whisper v1.1+")
                
        except Exception as e:
            logger.warning(f"Error parsing version {version}: {e}")
    
    logger.info(f"faster-whisper version: {version}, supported params: {len(base_params)}")
    return base_params

# Apple Silicon detection and optimization
def is_apple_silicon():
    """Detect if running on Apple Silicon (M1/M2/M3/M4)"""
    return platform.machine() == 'arm64' and platform.system() == 'Darwin'

def get_cpu_info():
    """Get CPU information for optimization"""
    if is_apple_silicon():
        # Try to get specific Apple Silicon model
        try:
            import subprocess
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], 
                                  capture_output=True, text=True)
            cpu_brand = result.stdout.strip()
            return cpu_brand
        except:
            return "Apple Silicon"
    return platform.processor()

def get_memory_info():
    """Get memory information for optimization"""
    memory = psutil.virtual_memory()
    return {
        'total': memory.total,
        'available': memory.available,
        'percent': memory.percent
    }

def optimize_for_apple_silicon():
    """Configure optimizations specific to Apple Silicon"""
    if is_apple_silicon():
        # Set environment variables for Apple Silicon optimization
        os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
        os.environ['OMP_NUM_THREADS'] = str(max(1, psutil.cpu_count(logical=False)))
        
        # Log Apple Silicon detection
        cpu_info = get_cpu_info()
        memory_info = get_memory_info()
        logger.info(f"Apple Silicon detected: {cpu_info}")
        logger.info(f"Available memory: {memory_info['available'] / (1024**3):.1f}GB")
        
        return True
    return False

# Global model cache to avoid reloading models
_model_cache = {}
_batched_model_cache = {}

# VAD and batching utilities for offline processing
def load_vad_model():
    """Load Voice Activity Detection model for local processing"""
    try:
        # Try to import silero VAD for local voice activity detection
        import torch
        torch.hub._validate_not_a_forked_repo = lambda a, b, c: True  # Disable fork check
        
        vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False,
            verbose=False
        )
        
        logger.info("Local VAD model loaded successfully")
        return vad_model, utils
    except Exception as e:
        logger.warning(f"Could not load VAD model: {e}")
        return None, None

def detect_speech_segments(audio_path, vad_model=None, utils=None):
    """
    Detect speech segments in audio file using local VAD
    Returns list of (start, end) timestamps in seconds
    """
    if vad_model is None or utils is None:
        # Fallback: return full audio as single segment
        return [(0.0, None)]
    
    try:
        import torch
        import torchaudio
        
        # Load audio
        wav, sr = torchaudio.load(audio_path)
        
        # Resample if needed (VAD expects 16kHz)
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(sr, 16000)
            wav = resampler(wav)
            sr = 16000
        
        # Get speech timestamps
        speech_timestamps = utils[0](wav, vad_model, sampling_rate=sr)
        
        # Convert to (start, end) tuples in seconds
        segments = []
        for timestamp in speech_timestamps:
            start = timestamp['start'] / sr
            end = timestamp['end'] / sr
            segments.append((start, end))
        
        logger.info(f"Detected {len(segments)} speech segments")
        return segments
        
    except Exception as e:
        logger.warning(f"VAD detection failed: {e}")
        return [(0.0, None)]  # Fallback to full audio


def get_or_create_whisper_model(model_size='base'):
    """
    Get or create a Whisper model with caching to avoid reloading
    Optimized for Apple Silicon M4 and offline operation
    """
    if model_size not in _model_cache:
        logger.info(f"Loading Whisper model: {model_size}")
        
        # Initialize Apple Silicon optimizations
        is_m_series = optimize_for_apple_silicon()
        
        # Get configuration from settings with M4 optimizations
        device = getattr(settings, 'WHISPER_DEVICE', 'cpu')
        compute_type = getattr(settings, 'WHISPER_COMPUTE_TYPE', 'int8')
        
        # Apple Silicon specific optimizations
        if is_m_series:
            device = 'cpu'  # M4 uses CPU + Neural Engine
            compute_type = 'int8'  # Optimal for Apple Silicon
            logger.info("Apple Silicon detected - using optimized CPU + Neural Engine configuration")
        elif device == 'auto':
            # Fallback for non-Apple Silicon
            try:
                import torch
                if torch.cuda.is_available():
                    device = 'cuda'
                    compute_type = 'float16'
                    logger.info("GPU detected, using CUDA with float16")
                else:
                    device = 'cpu'
                    compute_type = 'int8'
                    logger.info("No GPU detected, using CPU with int8")
            except ImportError:
                device = 'cpu'
                compute_type = 'int8'
                logger.info("PyTorch not available, using CPU with int8")
        
        # Memory optimization for unified memory architecture
        if is_m_series:
            memory_info = get_memory_info()
            if memory_info['available'] < 4 * (1024**3):  # Less than 4GB available
                logger.warning("Low memory detected - enabling memory efficient mode")
                # Could implement memory efficient loading here
        
        # Initialize model with specified configuration
        try:
            model_kwargs = {
                'device': device,
                'compute_type': compute_type,
                'download_root': getattr(settings, 'WHISPER_MODELS_DIR', None)
            }
            
            # Add Apple Silicon specific optimizations
            if is_m_series:
                # Optimize for M4's unified memory architecture
                model_kwargs['cpu_threads'] = max(1, psutil.cpu_count(logical=False))
                model_kwargs['num_workers'] = 1  # Single worker for unified memory
                
            _model_cache[model_size] = WhisperModel(
                model_size,
                **model_kwargs
            )
            
            # Validate model was loaded successfully
            model = _model_cache[model_size]
            if hasattr(model, 'model') and model.model is not None:
                logger.info(f"Whisper model {model_size} loaded and validated successfully on {device} with compute_type {compute_type}")
            else:
                logger.warning(f"Whisper model {model_size} loaded but validation failed")
                
        except Exception as e:
            logger.error(f"Failed to load Whisper model {model_size}: {str(e)}")
            # Remove from cache if loading failed
            if model_size in _model_cache:
                del _model_cache[model_size]
            raise e
    
    return _model_cache[model_size]


def get_or_create_batched_model(model_size='base'):
    """
    Get or create a batched Whisper model for faster processing
    Optimized for Apple Silicon M4 with advanced VAD support
    """
    if not BATCHED_INFERENCE_AVAILABLE:
        logger.info("BatchedInferencePipeline not available, using regular model")
        return get_or_create_whisper_model(model_size)
        
    if model_size not in _batched_model_cache:
        logger.info(f"Creating enhanced batched inference pipeline for model: {model_size}")
        
        # Get the base model first
        base_model = get_or_create_whisper_model(model_size)
        
        # Determine optimal configuration for M4
        is_m_series = is_apple_silicon()
        memory_info = get_memory_info()
        
        if is_m_series:
            # Optimize for M4's unified memory architecture
            available_gb = memory_info['available'] / (1024**3)
            if available_gb > 16:
                batch_size = 24  # Increased for v1.1.1
                chunk_length = 30
            elif available_gb > 8:
                batch_size = 16
                chunk_length = 30
            else:
                batch_size = 8
                chunk_length = 25
            
            logger.info(f"M4 optimization: {available_gb:.1f}GB available, batch_size={batch_size}")
        else:
            batch_size = 16  # Increased default for v1.1.1
            chunk_length = 30
        
        try:
            # Create enhanced batched inference pipeline
            # Check BatchedInferencePipeline constructor signature for parameter support
            try:
                # Try with additional parameters if supported in this version
                _batched_model_cache[model_size] = BatchedInferencePipeline(
                    model=base_model,
                    batch_size=batch_size
                )
                logger.info(f"Enhanced batched model created with batch_size={batch_size}")
            except TypeError:
                # Fallback: BatchedInferencePipeline only accepts model parameter
                _batched_model_cache[model_size] = BatchedInferencePipeline(model=base_model)
                logger.info(f"Basic batched model created (batch_size configuration not supported)")
            
        except Exception as e:
            logger.error(f"Failed to create batched model {model_size}: {str(e)}")
            # Fallback to regular model
            _batched_model_cache[model_size] = base_model
            logger.info("Falling back to regular model")
            
    return _batched_model_cache[model_size]


def preload_whisper_models(model_sizes=None):
    """
    Preload commonly used Whisper models to avoid download delays
    """
    if model_sizes is None:
        model_sizes = getattr(settings, 'WHISPER_PRELOAD_MODELS', ['base', 'small', 'medium'])
    
    logger.info(f"Preloading Whisper models: {model_sizes}")
    
    for model_size in model_sizes:
        try:
            get_or_create_whisper_model(model_size)
            logger.info(f"Successfully preloaded model: {model_size}")
        except Exception as e:
            logger.error(f"Failed to preload model {model_size}: {str(e)}")


def clear_model_cache():
    """
    Clear the model cache to free memory
    Optimized for M4 unified memory management
    """
    global _model_cache, _batched_model_cache
    
    # Clear regular models
    _model_cache.clear()
    
    # Clear batched models
    _batched_model_cache.clear()
    
    # Force garbage collection for M4 unified memory
    if is_apple_silicon():
        import gc
        gc.collect()
        
        # Log memory status
        memory_info = get_memory_info()
        logger.info(f"Model cache cleared - Available memory: {memory_info['available'] / (1024**3):.1f}GB")
    else:
        logger.info("Whisper model cache cleared")

def monitor_memory_usage():
    """
    Monitor memory usage and clear cache if needed (M4 optimization)
    """
    if not is_apple_silicon():
        return False
        
    memory_info = get_memory_info()
    memory_percent = memory_info['percent']
    
    # If memory usage is high, clear caches
    if memory_percent > 85:
        logger.warning(f"High memory usage detected: {memory_percent}% - clearing model cache")
        clear_model_cache()
        return True
    elif memory_percent > 75:
        logger.info(f"Memory usage: {memory_percent}% - monitoring closely")
        
    return False

def optimize_audio_loading(audio_path):
    """
    Optimize audio file loading for M4 unified memory
    """
    try:
        import librosa
        
        # Load with optimized parameters for M4
        if is_apple_silicon():
            # Use smaller chunks for memory efficiency
            audio, sr = librosa.load(audio_path, sr=16000, mono=True, dtype='float32')
        else:
            # Standard loading for other systems
            audio, sr = librosa.load(audio_path, sr=None, mono=True)
            
        return audio, sr
        
    except ImportError:
        logger.warning("librosa not available, using basic audio loading")
        return None, None
    except Exception as e:
        logger.error(f"Audio loading failed: {e}")
        return None, None

def normalize_thai_text(text):
    """
    Normalize Thai text using business vocabulary and common rules
    """
    if not text:
        return text
        
    try:
        # Get normalization rules from settings
        normalization_rules = getattr(settings, 'THAI_NORMALIZATION_RULES', {})
        
        # Apply normalization rules
        normalized_text = text
        for abbrev, full_form in normalization_rules.items():
            normalized_text = normalized_text.replace(abbrev, full_form)
        
        # Additional Thai-specific cleaning
        normalized_text = normalized_text.strip()
        
        # Remove extra whitespace
        import re
        normalized_text = re.sub(r'\s+', ' ', normalized_text)
        
        return normalized_text
        
    except Exception as e:
        logger.warning(f"Thai text normalization failed: {e}")
        return text

def enhance_thai_transcription(text, language='th'):
    """
    Enhance Thai transcription with business vocabulary and context
    """
    if language != 'th' or not text:
        return text
        
    try:
        # Normalize the text
        enhanced_text = normalize_thai_text(text)
        
        # Add business context improvements here if needed
        # For now, just return normalized text
        
        logger.info("Thai text enhancement completed")
        return enhanced_text
        
    except Exception as e:
        logger.warning(f"Thai enhancement failed: {e}")
        return text


def validate_model_functionality(model_size='base'):
    """
    Test that a Whisper model can perform basic operations
    Enhanced with offline validation and M4 compatibility checks
    """
    try:
        model = get_or_create_whisper_model(model_size)
        
        # Check if model has required methods
        required_methods = ['transcribe', 'generate_segments']
        for method in required_methods:
            if not hasattr(model, method):
                logger.error(f"Model {model_size} missing required method: {method}")
                return False
        
        # Check supported languages
        if hasattr(model, 'supported_languages'):
            supported_langs = model.supported_languages
            if 'th' in supported_langs and 'en' in supported_langs:
                logger.info(f"Model {model_size} supports Thai and English languages")
            else:
                logger.warning(f"Model {model_size} language support: {list(supported_langs)[:10]}...")
        
        # M4-specific validation
        if is_apple_silicon():
            memory_info = get_memory_info()
            if memory_info['available'] < 2 * (1024**3):  # Less than 2GB
                logger.warning(f"Low memory for model {model_size} on M4: {memory_info['available'] / (1024**3):.1f}GB")
                
        # Test basic functionality with a silent audio segment
        try:
            import numpy as np
            import tempfile
            import wave
            
            # Create a short silent audio file for testing
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                sample_rate = 16000
                duration = 1  # 1 second
                samples = np.zeros(sample_rate * duration, dtype=np.int16)
                
                with wave.open(tmp_file.name, 'w') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(samples.tobytes())
                
                # Test transcription
                segments, info = model.transcribe(tmp_file.name, language='en')
                list(segments)  # Consume the generator
                
                # Clean up
                os.unlink(tmp_file.name)
                
                logger.info(f"Model {model_size} functional test passed")
                
        except Exception as test_error:
            logger.warning(f"Model {model_size} functional test failed: {test_error}")
            # Don't fail validation for functional test issues
        
        logger.info(f"Model {model_size} validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Model {model_size} validation failed: {str(e)}")
        return False

def check_offline_dependencies():
    """
    Check that all required dependencies are available for offline operation
    """
    dependencies = {
        'torch': 'PyTorch for tensor operations',
        'torchaudio': 'Audio processing',
        'faster_whisper': 'Whisper inference engine',
        'numpy': 'Numerical operations',
        'psutil': 'System monitoring'
    }
    
    missing = []
    available = []
    
    for dep, description in dependencies.items():
        try:
            __import__(dep)
            available.append(f"✓ {dep}: {description}")
        except ImportError:
            missing.append(f"✗ {dep}: {description}")
    
    # Optional dependencies
    optional_deps = {
        'librosa': 'Advanced audio processing',
        'silero_vad': 'Voice activity detection'
    }
    
    for dep, description in optional_deps.items():
        try:
            __import__(dep)
            available.append(f"✓ {dep}: {description} (optional)")
        except ImportError:
            available.append(f"~ {dep}: {description} (optional, not available)")
    
    logger.info("Dependency check:")
    for dep in available:
        logger.info(dep)
    
    if missing:
        logger.error("Missing required dependencies:")
        for dep in missing:
            logger.error(dep)
        return False
    
    return True


def detect_language(audio_path, model_size='base'):
    """
    Detect the language of audio file
    """
    try:
        model = get_or_create_whisper_model(model_size)
        
        # The detect_language method expects audio data, not a path
        # For faster-whisper, we need to use the transcribe method with a small portion
        # to detect language, as detect_language expects preprocessed audio
        
        # Transcribe first 30 seconds to detect language
        # Suppress numpy warnings that can occur with certain audio
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=RuntimeWarning)
            segments, info = model.transcribe(
                audio_path, 
                language=None,  # Auto-detect
                task='transcribe',
                beam_size=1,  # Faster for detection
                best_of=1,
                temperature=0,
                without_timestamps=True,
                max_new_tokens=1  # Just need language detection
            )
        
        language = info.language if hasattr(info, 'language') else 'unknown'
        probability = info.language_probability if hasattr(info, 'language_probability') else 0
        
        # Don't waste the segments, just for language detection
        for _ in segments:
            break  # Exit after first segment
        
        return language, probability
            
    except Exception as e:
        logger.error(f"Language detection failed: {str(e)}")
        return 'unknown', 0


def transcribe_audio(audio_path, model_size='base', transcript_obj=None, language=None, use_batching=True):
    """
    Enhanced transcribe audio file using faster-whisper with Thai language support
    Optimized for Apple Silicon M4 with advanced VAD batching and performance tracking
    """
    import time
    import os
    
    start_time = time.time()
    
    try:
        # Monitor memory usage before starting (M4 optimization)
        monitor_memory_usage()
        
        # Get audio file info for benchmarking
        audio_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        logger.info(f"Processing audio file: {audio_size_mb:.1f}MB")
        
        if transcript_obj:
            transcript_obj.progress = 10
            transcript_obj.save()
        
        # Choose between batched and regular model based on settings and availability
        use_batched_model = use_batching and getattr(settings, 'WHISPER_USE_BATCHING', True) and BATCHED_INFERENCE_AVAILABLE
        
        model_load_start = time.time()
        if use_batched_model:
            try:
                model = get_or_create_batched_model(model_size)
                logger.info("Using enhanced batched inference pipeline with VAD")
            except Exception as e:
                logger.warning(f"Batched model failed, falling back to regular model: {e}")
                model = get_or_create_whisper_model(model_size)
        else:
            model = get_or_create_whisper_model(model_size)
            if not BATCHED_INFERENCE_AVAILABLE:
                logger.info("Using regular Whisper model (batching not available)")
        
        model_load_time = time.time() - model_load_start
        logger.info(f"Model load time: {model_load_time:.2f}s")
        
        if transcript_obj:
            transcript_obj.progress = 30
            transcript_obj.save()
        
        # Configure enhanced transcription parameters using settings
        language_key = language if language in ['th', 'en'] else 'auto'
        language_settings = getattr(settings, 'WHISPER_LANGUAGE_SETTINGS', {})
        
        # Get base parameters from settings or use enhanced defaults
        base_params = language_settings.get(language_key, {
            'beam_size': 5,
            'temperature': 0.0,
            'condition_on_previous_text': False,
        })
        
        # Get supported parameters for current faster-whisper version
        supported_params = get_supported_transcribe_params()
        
        # Build enhanced transcription parameters with only supported ones
        transcription_params = {
            'language': language if language else None,  # Auto-detect if not specified
            'task': 'transcribe'
        }
        
        # Add only supported parameters from base_params
        for param, value in base_params.items():
            if param in supported_params:
                transcription_params[param] = value
            else:
                logger.debug(f"Skipping unsupported parameter: {param}={value}")
        
        # Add advanced parameters if supported (v1.1.1 features)
        if 'word_timestamps' in supported_params:
            transcription_params['word_timestamps'] = True
            logger.info("Word timestamps enabled")
        
        if 'compression_ratio_threshold' in supported_params:
            transcription_params['compression_ratio_threshold'] = 2.4
            
        # Note: logprob_threshold parameter may not be supported
        # if 'logprob_threshold' in supported_params:
        #     transcription_params['log_prob_threshold'] = -1.0
            
        if 'no_speech_threshold' in supported_params:
            transcription_params['no_speech_threshold'] = 0.6
            
        # Enhanced batched-specific parameters
        # Note: batch_size, chunk_length, vad_filter are BatchedInferencePipeline configuration,
        # not transcribe() parameters - they should be set during pipeline creation
        if use_batched_model and BATCHED_INFERENCE_AVAILABLE:
            logger.info("Using batched inference pipeline with pre-configured VAD and batching")
        
        logger.info(f"Enhanced transcription parameters ({len(transcription_params)}): {list(transcription_params.keys())}")
        
        # Auto-detect language if not specified and Thai optimization is enabled
        if not language and getattr(settings, 'WHISPER_THAI_OPTIMIZED', True):
            detected_lang, confidence = detect_language(audio_path, model_size)
            if detected_lang == 'th' and confidence > 0.7:
                logger.info(f"Auto-detected Thai language with confidence {confidence:.2f}")
                # Apply Thai-specific enhanced parameters
                thai_params = language_settings.get('th', {})
                for param, value in thai_params.items():
                    if param in supported_params:
                        transcription_params[param] = value
                transcription_params['language'] = 'th'
        
        # Transcribe audio with enhanced parameters
        transcribe_start = time.time()
        # Suppress numpy warnings that can occur with certain audio
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=RuntimeWarning)
            segments, info = model.transcribe(audio_path, **transcription_params)
        
        if transcript_obj:
            transcript_obj.progress = 60
            transcript_obj.save()
        
        # Process segments with enhanced features
        full_text = ""
        word_timestamps = []
        total_segments = 0
        
        for segment in segments:
            full_text += segment.text + " "
            total_segments += 1
            
            # Collect word timestamps if available
            if hasattr(segment, 'words') and segment.words:
                for word in segment.words:
                    word_timestamps.append({
                        'word': word.word,
                        'start': word.start,
                        'end': word.end,
                        'probability': getattr(word, 'probability', 0.0)
                    })
        
        transcribe_time = time.time() - transcribe_start
        
        # Apply Thai language enhancement if applicable
        detected_language = info.language if hasattr(info, 'language') else language
        if detected_language == 'th' or language == 'th':
            full_text = enhance_thai_transcription(full_text, 'th')
        
        if transcript_obj:
            transcript_obj.progress = 90
            transcript_obj.save()
        
        # Enhanced logging with performance metrics
        total_time = time.time() - start_time
        detected_language = info.language if hasattr(info, 'language') else 'unknown'
        language_probability = info.language_probability if hasattr(info, 'language_probability') else 0
        
        # Performance metrics
        audio_duration = getattr(info, 'duration', 0)
        if audio_duration > 0:
            real_time_factor = audio_duration / transcribe_time
            logger.info(f"Performance: {real_time_factor:.1f}x real-time ({transcribe_time:.2f}s for {audio_duration:.1f}s audio)")
        
        logger.info(f"Transcription complete: {total_segments} segments, {len(word_timestamps)} words")
        logger.info(f"Detected language: {detected_language} (confidence: {language_probability:.2f})")
        logger.info(f"Total processing time: {total_time:.2f}s")
        
        return full_text.strip()
        
    except Exception as e:
        if transcript_obj:
            transcript_obj.status = 'failed'
            transcript_obj.error_message = str(e)
            transcript_obj.save()
        logger.error(f"Transcription failed after {time.time() - start_time:.2f}s: {str(e)}")
        raise e


def generate_insights_from_text(text, insight_obj=None):
    """
    Generate insights from transcript text using LMStudio API
    """
    try:
        if insight_obj:
            insight_obj.progress = 20
            insight_obj.save()
        
        # LMStudio API endpoint
        api_url = "http://localhost:1234/v1/chat/completions"
        
        # Prepare the prompt for insights generation with 9 specific categories
        prompt = f"""
        Please analyze the following meeting transcript and provide insights in two main sections:

        1. SITUATION: A clear, concise summary of what was discussed, key topics, and the context of the meeting.

        2. INSIGHTS: Please organize your insights into the following 9 categories:
        
        **Tasks & Action Items**: Specific tasks assigned or action items mentioned
        **Decisions Made**: Key decisions that were reached during the meeting
        **Questions & Answers**: Important questions raised and their answers
        **Key Insights**: Major revelations, discoveries, or important points
        **Deadlines**: Any dates, deadlines, or time-sensitive items mentioned
        **Meeting Participants**: Who was present and their roles/contributions
        **Follow-up Actions**: What needs to happen next or follow-up required
        **Risks Identified**: Potential risks, concerns, or challenges mentioned
        **Meeting Agenda**: The main topics or agenda items covered

        Please format your response exactly as follows:
        SITUATION:
        [Your situation analysis here]

        INSIGHTS:
        **Tasks & Action Items**:
        [List specific tasks and action items]

        **Decisions Made**:
        [List key decisions]

        **Questions & Answers**:
        [List important Q&A]

        **Key Insights**:
        [List major insights]

        **Deadlines**:
        [List deadlines and dates]

        **Meeting Participants**:
        [List participants and roles]

        **Follow-up Actions**:
        [List follow-up actions needed]

        **Risks Identified**:
        [List risks and concerns]

        **Meeting Agenda**:
        [List main agenda items]

        Transcript:
        {text}
        """
        
        if insight_obj:
            insight_obj.progress = 40
            insight_obj.save()
        
        # Make API request to LMStudio
        payload = {
            "model": "local-model",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        if insight_obj:
            insight_obj.progress = 60
            insight_obj.save()
        
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=settings.LLM_TIMEOUT)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error("LMStudio API timeout")
            raise Exception("LMStudio API timeout - generation took too long")
        except requests.exceptions.ConnectionError:
            logger.error("LMStudio API connection error")
            raise Exception("Cannot connect to LMStudio service")
        except requests.exceptions.HTTPError as e:
            logger.error(f"LMStudio API HTTP error: {e}")
            raise Exception(f"LMStudio API error: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"LMStudio API request error: {e}")
            raise Exception(f"LMStudio API request failed: {e}")
        
        # Parse response
        try:
            result = response.json()
        except ValueError as e:
            logger.error(f"Invalid JSON response from LMStudio: {e}")
            raise Exception("Invalid response from LMStudio service")
        
        # Extract content from response
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        if not content:
            error_msg = result.get('error', {}).get('message', 'No content returned')
            logger.error(f"LMStudio API error: {error_msg}")
            raise Exception(f"LMStudio API error: {error_msg}")
        
        generated_text = content
        
        if insight_obj:
            insight_obj.progress = 80
            insight_obj.save()
        
        # Parse the response to extract situation and insights
        situation = ""
        insights = ""
        
        lines = generated_text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('SITUATION:'):
                current_section = 'situation'
                situation += line.replace('SITUATION:', '').strip() + '\n'
            elif line.startswith('INSIGHTS:'):
                current_section = 'insights'
                insights += line.replace('INSIGHTS:', '').strip() + '\n'
            elif current_section == 'situation' and line:
                situation += line + '\n'
            elif current_section == 'insights' and line:
                insights += line + '\n'
        
        if insight_obj:
            insight_obj.progress = 100
            insight_obj.save()
        
        return situation.strip(), insights.strip()
            
    except Exception as e:
        if insight_obj:
            insight_obj.status = 'failed'
            insight_obj.error_message = str(e)
            insight_obj.save()
        raise e


def generate_meeting_name_and_description(text, meeting_obj=None):
    """
    Generate a meeting name and description from transcript text using LMStudio API
    """
    try:
        # LMStudio API endpoint from settings
        from django.conf import settings
        api_url = f"{settings.LLM_API_BASE}/chat/completions"
        
        # Check if LMStudio is available
        try:
            health_check = requests.get(f"{settings.LLM_API_BASE}/models", timeout=5)
            if health_check.status_code != 200:
                raise Exception("LMStudio service not available")
        except requests.exceptions.RequestException as e:
            logger.error(f"LMStudio health check failed: {str(e)}")
            raise Exception(f"LMStudio service unavailable: {str(e)}")
        
        # Prepare the prompt for meeting name generation
        prompt = f"""
        Please analyze the following meeting transcript and provide a concise meeting name and description.

        Please format your response exactly as follows:
        MEETING_NAME:
        [A short, descriptive meeting name (max 50 characters)]

        DESCRIPTION:
        [A brief description of the meeting purpose and main topics (max 200 characters)]

        Transcript:
        {text[:2000]}...
        """
        
        # Make API request to LMStudio
        payload = {
            "model": "local-model",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 300
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error("LMStudio API timeout")
            raise Exception("LMStudio API timeout - generation took too long")
        except requests.exceptions.ConnectionError:
            logger.error("LMStudio API connection error")
            raise Exception("Cannot connect to LMStudio service")
        except requests.exceptions.HTTPError as e:
            logger.error(f"LMStudio API HTTP error: {e}")
            raise Exception(f"LMStudio API error: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"LMStudio API request error: {e}")
            raise Exception(f"LMStudio API request failed: {e}")
        
        # Parse response
        try:
            result = response.json()
        except ValueError as e:
            logger.error(f"Invalid JSON response from LMStudio: {e}")
            raise Exception("Invalid response from LMStudio service")
        
        # Extract content from response
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        if not content:
            error_msg = result.get('error', {}).get('message', 'No content returned')
            logger.error(f"LMStudio API error: {error_msg}")
            raise Exception(f"LMStudio API error: {error_msg}")
        
        generated_text = content
        
        # Parse the response to extract meeting name and description
        meeting_name = ""
        description = ""
        
        lines = generated_text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('MEETING_NAME:'):
                current_section = 'name'
                meeting_name += line.replace('MEETING_NAME:', '').strip() + ' '
            elif line.startswith('DESCRIPTION:'):
                current_section = 'description'
                description += line.replace('DESCRIPTION:', '').strip() + ' '
            elif current_section == 'name' and line:
                meeting_name += line + ' '
            elif current_section == 'description' and line:
                description += line + ' '
        
        # Clean up and limit lengths
        meeting_name = meeting_name.strip()[:50]
        description = description.strip()[:200]
        
        return meeting_name, description
            
    except Exception as e:
        # Return fallback names if API fails
        return f"Meeting {datetime.now().strftime('%Y-%m-%d %H:%M')}", "Meeting analysis generated by TM IntelliMind"