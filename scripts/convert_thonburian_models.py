#!/usr/bin/env python3
"""
Script to convert Thonburian Whisper models from Hugging Face to CTranslate2 format
for use with faster-whisper in TM IntelliMind.

This script downloads and converts Thai-optimized Whisper models for better
Thai language transcription accuracy.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Model configurations
THONBURIAN_MODELS = {
    'thonburian-medium': {
        'hf_model': 'biodatlab/whisper-th-medium-combined',
        'description': 'Thonburian Medium - Thai optimized (7.42% WER)',
        'size': '764M parameters'
    },
    'thonburian-large': {
        'hf_model': 'biodatlab/whisper-th-large-combined',
        'description': 'Thonburian Large - Thai optimized (best accuracy)',
        'size': '1540M parameters'
    }
}

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import transformers
        if not hasattr(transformers, '__version__') or transformers.__version__ < '4.23.0':
            logger.error("transformers>=4.23.0 required for model conversion")
            return False, None
        
        # Check if ct2-transformers-converter is available
        converter_path = '/Users/artdebmac/Library/Python/3.9/bin/ct2-transformers-converter'
        if not os.path.exists(converter_path):
            # Try to find it in common locations
            import shutil
            converter_path = shutil.which('ct2-transformers-converter')
            if not converter_path:
                logger.error("ct2-transformers-converter not found. Install with: pip install ctranslate2")
                return False, None
        
        result = subprocess.run([converter_path, '--help'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("ct2-transformers-converter not found. Install with: pip install ctranslate2")
            return False, None
            
        logger.info("Dependencies check passed")
        return True, converter_path
        
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return False, None

def convert_model(model_name, model_config, output_base_dir, converter_path):
    """Convert a single Thonburian model to CTranslate2 format"""
    hf_model = model_config['hf_model']
    output_dir = output_base_dir / f"{model_name}-ct2"
    
    logger.info(f"Converting {model_name} ({hf_model}) to CTranslate2 format...")
    logger.info(f"Description: {model_config['description']}")
    logger.info(f"Output directory: {output_dir}")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert model
    cmd = [
        converter_path,
        '--model', hf_model,
        '--output_dir', str(output_dir),
        '--copy_files', 'tokenizer.json',  # Copy tokenizer files
        '--quantization', 'float16',  # Use float16 for better performance/memory
        '--force'  # Override existing directory
    ]
    
    try:
        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"Successfully converted {model_name}")
        logger.info(f"Output: {result.stdout}")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to convert {model_name}: {e}")
        logger.error(f"Error output: {e.stderr}")
        return False

def main():
    """Main conversion process"""
    logger.info("Starting Thonburian Whisper model conversion for TM IntelliMind")
    
    # Check dependencies
    deps_ok, converter_path = check_dependencies()
    if not deps_ok:
        logger.error("Dependency check failed. Please install required packages:")
        logger.error("pip install transformers>=4.23.0 ctranslate2")
        sys.exit(1)
    
    # Setup output directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    models_dir = project_root / 'models' / 'thonburian'
    models_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Models will be saved to: {models_dir}")
    
    # Convert each model
    success_count = 0
    for model_name, model_config in THONBURIAN_MODELS.items():
        if convert_model(model_name, model_config, models_dir, converter_path):
            success_count += 1
    
    # Summary
    total_models = len(THONBURIAN_MODELS)
    logger.info(f"Conversion complete: {success_count}/{total_models} models converted successfully")
    
    if success_count > 0:
        logger.info("Converted models are ready for use with faster-whisper")
        logger.info(f"Model location: {models_dir}")
        logger.info("Next steps:")
        logger.info("1. Update TM IntelliMind to include these models in WHISPER_MODEL_CHOICES")
        logger.info("2. Test transcription with Thai audio files")
        logger.info("3. Compare accuracy with existing large-v2 model")
    
    if success_count < total_models:
        sys.exit(1)

if __name__ == "__main__":
    main()