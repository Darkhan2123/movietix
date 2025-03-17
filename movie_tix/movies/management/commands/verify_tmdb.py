import os
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from movies.tmdb_api import test_api_key

class Command(BaseCommand):
    help = 'Verifies that the TMDB API key is valid and working'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("TMDB API Key Verification"))
        self.stdout.write('-' * 40)
        
        # Check if TMDB_API_KEY is in settings
        settings_key = getattr(settings, 'TMDB_API_KEY', None)
        if settings_key:
            self.stdout.write(f"TMDB_API_KEY in settings: {settings_key[:4]}... [Found]")
        else:
            self.stdout.write(self.style.WARNING("TMDB_API_KEY in settings: [Not Found]"))
        
        # Check if TMDB_API_KEY is in environment
        env_key = os.environ.get('TMDB_API_KEY', None)
        if env_key:
            self.stdout.write(f"TMDB_API_KEY in environment: {env_key[:4]}... [Found]")
        else:
            self.stdout.write(self.style.WARNING("TMDB_API_KEY in environment: [Not Found]"))
        
        # Test if API key works
        self.stdout.write("\nTesting API key...")
        success, message = test_api_key()
        
        if success:
            self.stdout.write(self.style.SUCCESS(f"✓ {message}"))
            self.stdout.write(self.style.SUCCESS("TMDB API key is valid and working!"))
        else:
            self.stdout.write(self.style.ERROR(f"✗ {message}"))
            self.stdout.write(self.style.ERROR("TMDB API key verification FAILED"))
            
        self.stdout.write('-' * 40)