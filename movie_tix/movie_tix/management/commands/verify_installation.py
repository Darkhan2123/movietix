import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Verifies that the MovieTix installation is correct and fixes common issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix identified issues automatically',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("MovieTix Installation Verification"))
        self.stdout.write("=" * 50)
        
        fix_mode = options['fix']
        if fix_mode:
            self.stdout.write(self.style.WARNING("Running in FIX mode - will attempt to fix issues"))
        else:
            self.stdout.write("Running in CHECK mode - will only identify issues")
            self.stdout.write("Run with --fix to automatically fix identified issues")
        
        self.stdout.write("\n")
        
        # Check 1: .env file exists
        self._check_env_file(fix_mode)
        
        # Check 2: TMDB API key is configured
        self._check_tmdb_api_key(fix_mode)
        
        # Check 3: Static files are configured
        self._check_static_files(fix_mode)
        
        # Check 4: Media files are configured
        self._check_media_files(fix_mode)
        
        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("Verification complete"))
        
    def _check_env_file(self, fix_mode):
        """Check if .env file exists in correct locations"""
        self.stdout.write(self.style.NOTICE("Checking .env file..."))
        
        # Define paths to check
        base_dir = settings.BASE_DIR
        parent_dir = base_dir.parent if hasattr(base_dir, 'parent') else Path(os.path.dirname(base_dir))
        
        env_paths = [
            base_dir / '.env',  # movie_tix/.env
            parent_dir / '.env',  # root/.env
        ]
        
        # Check if any .env file exists
        env_exists = False
        env_path = None
        
        for path in env_paths:
            if path.exists():
                env_exists = True
                env_path = path
                self.stdout.write(self.style.SUCCESS(f"✓ .env file found at {path}"))
                break
                
        if not env_exists:
            self.stdout.write(self.style.ERROR("✗ No .env file found"))
            
            if fix_mode:
                # Create a basic .env file
                default_env_path = base_dir / '.env'
                self.stdout.write(f"Creating default .env file at {default_env_path}")
                
                # Define default content
                default_content = """# Django Configuration
DJANGO_SECRET_KEY=django-insecure-&gu_y1ldtunyk0(z^d=6q5==33og-3-pyr&br(prt7gx52o2y*
DJANGO_DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# API Keys
TMDB_API_KEY=9c52f42462d276f88fc32d0f13411270

# Site Configuration
SITE_URL=http://127.0.0.1:8000
"""
                # Write file
                try:
                    with open(default_env_path, 'w') as f:
                        f.write(default_content)
                    self.stdout.write(self.style.SUCCESS(f"✓ Created default .env file at {default_env_path}"))
                    env_exists = True
                    env_path = default_env_path
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"✗ Failed to create .env file: {e}"))
        
        # If .env found or created, check its content
        if env_exists:
            # Read .env file
            try:
                with open(env_path, 'r') as f:
                    env_content = f.read()
                    
                # Check if key variables are defined
                required_vars = [
                    'DJANGO_SECRET_KEY',
                    'TMDB_API_KEY',
                    'SITE_URL',
                ]
                
                missing_vars = []
                for var in required_vars:
                    if var not in env_content:
                        missing_vars.append(var)
                
                if missing_vars:
                    self.stdout.write(self.style.WARNING(f"⚠ .env file is missing these variables: {', '.join(missing_vars)}"))
                    
                    if fix_mode:
                        # Add missing variables
                        with open(env_path, 'a') as f:
                            f.write("\n# Added automatically by verify_installation\n")
                            if 'DJANGO_SECRET_KEY' in missing_vars:
                                f.write('DJANGO_SECRET_KEY=django-insecure-&gu_y1ldtunyk0(z^d=6q5==33og-3-pyr&br(prt7gx52o2y*\n')
                            if 'TMDB_API_KEY' in missing_vars:
                                f.write('TMDB_API_KEY=9c52f42462d276f88fc32d0f13411270\n')
                            if 'SITE_URL' in missing_vars:
                                f.write('SITE_URL=http://127.0.0.1:8000\n')
                        self.stdout.write(self.style.SUCCESS(f"✓ Added missing variables to .env file"))
                else:
                    self.stdout.write(self.style.SUCCESS("✓ .env file contains all required variables"))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Failed to read .env file: {e}"))
    
    def _check_tmdb_api_key(self, fix_mode):
        """Check if TMDB API key is configured correctly"""
        self.stdout.write(self.style.NOTICE("\nChecking TMDB API key..."))
        
        api_key = settings.TMDB_API_KEY
        
        if api_key:
            self.stdout.write(self.style.SUCCESS(f"✓ TMDB API key is configured: {api_key[:4]}..."))
            
            # Verify that the API key works
            try:
                from movies.tmdb_api import test_api_key
                success, message = test_api_key()
                
                if success:
                    self.stdout.write(self.style.SUCCESS(f"✓ TMDB API key is valid"))
                else:
                    self.stdout.write(self.style.ERROR(f"✗ TMDB API key validation failed: {message}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Failed to test TMDB API key: {e}"))
        else:
            self.stdout.write(self.style.ERROR("✗ TMDB API key is not configured"))
            
            if fix_mode:
                # Check if we can find it in .env file
                try:
                    import dotenv
                    env_paths = [
                        settings.BASE_DIR / '.env',
                        settings.BASE_DIR.parent / '.env',
                    ]
                    
                    for path in env_paths:
                        if path.exists():
                            env_vars = dotenv.dotenv_values(str(path))
                            if 'TMDB_API_KEY' in env_vars and env_vars['TMDB_API_KEY']:
                                self.stdout.write(self.style.SUCCESS(f"✓ Found TMDB API key in {path}: {env_vars['TMDB_API_KEY'][:4]}..."))
                                os.environ['TMDB_API_KEY'] = env_vars['TMDB_API_KEY']
                                self.stdout.write(self.style.SUCCESS("✓ Set TMDB API key in environment"))
                                return
                                
                    # If key not found, add to .env file
                    default_api_key = '9c52f42462d276f88fc32d0f13411270'
                    self.stdout.write(self.style.WARNING(f"Using default TMDB API key: {default_api_key[:4]}..."))
                    
                    # Find or create .env file
                    env_path = settings.BASE_DIR / '.env'
                    if not env_path.exists():
                        with open(env_path, 'w') as f:
                            f.write(f"TMDB_API_KEY={default_api_key}\n")
                    else:
                        with open(env_path, 'a') as f:
                            f.write(f"\nTMDB_API_KEY={default_api_key}\n")
                            
                    self.stdout.write(self.style.SUCCESS(f"✓ Added TMDB API key to {env_path}"))
                    os.environ['TMDB_API_KEY'] = default_api_key
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"✗ Failed to fix TMDB API key: {e}"))
    
    def _check_static_files(self, fix_mode):
        """Check if static files are configured correctly"""
        self.stdout.write(self.style.NOTICE("\nChecking static files configuration..."))
        
        # Check STATIC_URL
        if hasattr(settings, 'STATIC_URL'):
            self.stdout.write(self.style.SUCCESS(f"✓ STATIC_URL is configured: {settings.STATIC_URL}"))
        else:
            self.stdout.write(self.style.ERROR("✗ STATIC_URL is not configured"))
        
        # Check STATICFILES_DIRS
        if hasattr(settings, 'STATICFILES_DIRS') and settings.STATICFILES_DIRS:
            self.stdout.write(self.style.SUCCESS(f"✓ STATICFILES_DIRS is configured: {settings.STATICFILES_DIRS}"))
            
            # Check if directories exist
            for static_dir in settings.STATICFILES_DIRS:
                path = Path(static_dir)
                if path.exists():
                    self.stdout.write(self.style.SUCCESS(f"✓ Static directory exists: {path}"))
                else:
                    self.stdout.write(self.style.ERROR(f"✗ Static directory does not exist: {path}"))
                    
                    if fix_mode:
                        try:
                            os.makedirs(path, exist_ok=True)
                            self.stdout.write(self.style.SUCCESS(f"✓ Created static directory: {path}"))
                            
                            # Create a placeholder CSS file
                            css_dir = path / 'css'
                            os.makedirs(css_dir, exist_ok=True)
                            
                            placeholder_css = css_dir / 'styles.css'
                            if not placeholder_css.exists():
                                with open(placeholder_css, 'w') as f:
                                    f.write("/* MovieTix styles */\n")
                                self.stdout.write(self.style.SUCCESS(f"✓ Created placeholder CSS file: {placeholder_css}"))
                                
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"✗ Failed to create static directory: {e}"))
        else:
            self.stdout.write(self.style.ERROR("✗ STATICFILES_DIRS is not configured"))
    
    def _check_media_files(self, fix_mode):
        """Check if media files are configured correctly"""
        self.stdout.write(self.style.NOTICE("\nChecking media files configuration..."))
        
        # Check MEDIA_URL
        if hasattr(settings, 'MEDIA_URL'):
            self.stdout.write(self.style.SUCCESS(f"✓ MEDIA_URL is configured: {settings.MEDIA_URL}"))
        else:
            self.stdout.write(self.style.ERROR("✗ MEDIA_URL is not configured"))
        
        # Check MEDIA_ROOT
        if hasattr(settings, 'MEDIA_ROOT'):
            self.stdout.write(self.style.SUCCESS(f"✓ MEDIA_ROOT is configured: {settings.MEDIA_ROOT}"))
            
            # Check if directory exists
            media_path = Path(settings.MEDIA_ROOT)
            if media_path.exists():
                self.stdout.write(self.style.SUCCESS(f"✓ Media directory exists: {media_path}"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ Media directory does not exist: {media_path}"))
                
                if fix_mode:
                    try:
                        os.makedirs(media_path, exist_ok=True)
                        self.stdout.write(self.style.SUCCESS(f"✓ Created media directory: {media_path}"))
                        
                        # Create a placeholder default image
                        profile_dir = media_path / 'profile_pictures'
                        os.makedirs(profile_dir, exist_ok=True)
                        self.stdout.write(self.style.SUCCESS(f"✓ Created profile pictures directory: {profile_dir}"))
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"✗ Failed to create media directory: {e}"))
        else:
            self.stdout.write(self.style.ERROR("✗ MEDIA_ROOT is not configured"))