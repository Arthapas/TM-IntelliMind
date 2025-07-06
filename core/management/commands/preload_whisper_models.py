from django.core.management.base import BaseCommand
from django.conf import settings
from core.utils import preload_whisper_models, get_or_create_whisper_model, validate_model_functionality
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Preload Whisper models to avoid download delays during transcription'

    def add_arguments(self, parser):
        parser.add_argument(
            '--models',
            type=str,
            nargs='+',
            default=None,
            help='Specific models to preload (e.g., base small medium large)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Preload all available models',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reload models even if already cached',
        )
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Validate model functionality after loading',
        )

    def handle(self, *args, **options):
        if options['force']:
            from core.utils import clear_model_cache
            clear_model_cache()
            self.stdout.write(self.style.SUCCESS('Cleared model cache'))

        if options['all']:
            models_to_load = ['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3']
        elif options['models']:
            models_to_load = options['models']
        else:
            models_to_load = getattr(settings, 'WHISPER_PRELOAD_MODELS', ['base', 'small', 'medium'])

        self.stdout.write(f'Preloading Whisper models: {", ".join(models_to_load)}')

        for model_name in models_to_load:
            try:
                self.stdout.write(f'Loading {model_name}...', ending='')
                get_or_create_whisper_model(model_name)
                self.stdout.write(self.style.SUCCESS(' ✓'))
                
                # Validate if requested
                if options['validate']:
                    self.stdout.write(f'  Validating {model_name}...', ending='')
                    if validate_model_functionality(model_name):
                        self.stdout.write(self.style.SUCCESS(' ✓'))
                    else:
                        self.stdout.write(self.style.WARNING(' ⚠ - validation issues'))
                        
            except Exception as e:
                self.stdout.write(self.style.ERROR(f' ✗ - {str(e)}'))
                logger.error(f'Failed to load model {model_name}: {str(e)}')

        self.stdout.write(self.style.SUCCESS('Model preloading completed'))