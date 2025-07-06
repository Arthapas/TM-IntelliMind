from django.core.management.base import BaseCommand
from django.conf import settings
import os
import subprocess
import json
from pathlib import Path


class Command(BaseCommand):
    help = 'Display information about Whisper model cache'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed information about each model',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up unused or corrupted model files',
        )

    def handle(self, *args, **options):
        cache_dir = Path.home() / '.cache' / 'huggingface' / 'hub'
        
        if not cache_dir.exists():
            self.stdout.write(self.style.WARNING('HuggingFace cache directory not found'))
            return

        self.stdout.write(self.style.SUCCESS('=== Whisper Model Cache Information ===\n'))

        # Find all faster-whisper models
        whisper_models = []
        for model_dir in cache_dir.glob('models--Systran--faster-whisper-*'):
            if model_dir.is_dir():
                whisper_models.append(model_dir)

        if not whisper_models:
            self.stdout.write(self.style.WARNING('No Whisper models found in cache'))
            return

        # Show cache overview
        total_size = self._get_directory_size(cache_dir)
        self.stdout.write(f'📍 Cache Location: {cache_dir}')
        self.stdout.write(f'💾 Total Cache Size: {self._format_size(total_size)}')
        self.stdout.write(f'🔢 Whisper Models Found: {len(whisper_models)}\n')

        # Show each model
        for model_dir in sorted(whisper_models):
            model_name = model_dir.name.replace('models--Systran--faster-whisper-', '')
            model_size = self._get_directory_size(model_dir)
            
            # Check if model is complete
            snapshots_dir = model_dir / 'snapshots'
            is_complete = self._check_model_completeness(snapshots_dir)
            
            status = '✅' if is_complete else '❌'
            self.stdout.write(f'{status} {model_name.ljust(12)} - {self._format_size(model_size)}')
            
            if options['detailed']:
                self._show_detailed_info(model_dir, model_name)

        if options['cleanup']:
            self._cleanup_cache(whisper_models)

    def _get_directory_size(self, path):
        """Get the total size of a directory in bytes"""
        try:
            # Use Python to calculate directory size for better cross-platform compatibility
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
            return total_size
        except (OSError, IOError):
            return 0

    def _format_size(self, size_bytes):
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}TB"

    def _check_model_completeness(self, snapshots_dir):
        """Check if model has all required files"""
        if not snapshots_dir.exists():
            return False
        
        # Find the latest snapshot
        snapshots = list(snapshots_dir.glob('*'))
        if not snapshots:
            return False
        
        latest_snapshot = snapshots[0]  # Should only be one in most cases
        required_files = ['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt']
        
        for file_name in required_files:
            file_path = latest_snapshot / file_name
            if not file_path.exists():
                return False
        
        return True

    def _show_detailed_info(self, model_dir, model_name):
        """Show detailed information about a specific model"""
        snapshots_dir = model_dir / 'snapshots'
        
        if snapshots_dir.exists():
            snapshots = list(snapshots_dir.glob('*'))
            if snapshots:
                snapshot_dir = snapshots[0]
                self.stdout.write(f'  📁 Snapshot: {snapshot_dir.name}')
                
                # Show individual file sizes
                files = ['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt']
                for file_name in files:
                    file_path = snapshot_dir / file_name
                    if file_path.exists():
                        if file_path.is_symlink():
                            # Follow symlink to get actual size
                            actual_path = file_path.resolve()
                            if actual_path.exists():
                                size = actual_path.stat().st_size
                                self.stdout.write(f'    {file_name}: {self._format_size(size)}')
                        else:
                            size = file_path.stat().st_size
                            self.stdout.write(f'    {file_name}: {self._format_size(size)}')
        self.stdout.write('')

    def _cleanup_cache(self, whisper_models):
        """Clean up corrupted or incomplete models"""
        self.stdout.write(self.style.WARNING('\n🧹 Checking for cleanup opportunities...'))
        
        cleaned = False
        for model_dir in whisper_models:
            model_name = model_dir.name.replace('models--Systran--faster-whisper-', '')
            snapshots_dir = model_dir / 'snapshots'
            
            if not self._check_model_completeness(snapshots_dir):
                self.stdout.write(f'❌ Found incomplete model: {model_name}')
                
                # Ask for confirmation before cleanup
                response = input(f'Remove incomplete model {model_name}? (y/N): ')
                if response.lower() == 'y':
                    try:
                        import shutil
                        shutil.rmtree(model_dir)
                        self.stdout.write(self.style.SUCCESS(f'✅ Removed {model_name}'))
                        cleaned = True
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'❌ Failed to remove {model_name}: {e}'))
        
        if not cleaned:
            self.stdout.write(self.style.SUCCESS('✅ No cleanup needed - all models are complete'))