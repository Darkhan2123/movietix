"""
Environment variables loader for Django settings.
This module loads environment variables from a .env file.
"""
import os
import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def load_env_vars():
    """
    Load environment variables from a .env file if it exists.
    Tries multiple locations and provides helpful logging.
    """
    try:
        import dotenv
        
        # Check if the package is actually available
        if not hasattr(dotenv, 'load_dotenv'):
            print("Warning: python-dotenv appears to be installed but load_dotenv function is not available.")
            return {}

        # Find the .env file in the project root directory
        base_dir = Path(__file__).resolve().parent.parent
        env_paths = [
            base_dir / '.env',                    # movie_tix/.env
            base_dir.parent / '.env',             # /.env (project root)
            Path(os.getcwd()) / '.env',           # current working directory
        ]
        
        # Try to load from each path
        loaded = False
        loaded_path = None
        
        for env_path in env_paths:
            if env_path.exists():
                dotenv.load_dotenv(str(env_path))
                loaded = True
                loaded_path = env_path
                print(f"Loaded environment variables from {env_path}")
                break
        
        if not loaded:
            paths_str = "\n  - ".join([str(p) for p in env_paths])
            print(f"Warning: No .env file found. Checked locations:\n  - {paths_str}")
            return {}
            
        # Double-check that TMDB_API_KEY was actually loaded
        if 'TMDB_API_KEY' in os.environ:
            api_key_prefix = os.environ['TMDB_API_KEY'][:4] if os.environ['TMDB_API_KEY'] else "empty"
            print(f"TMDB_API_KEY loaded successfully: {api_key_prefix}...")
        else:
            # Try to manually read the .env file to see if TMDB_API_KEY is present
            try:
                env_content = dotenv.dotenv_values(str(loaded_path))
                if 'TMDB_API_KEY' in env_content:
                    api_key_prefix = env_content['TMDB_API_KEY'][:4] if env_content['TMDB_API_KEY'] else "empty"
                    print(f"TMDB_API_KEY found in .env file but not loaded into environment: {api_key_prefix}...")
                    # Manually set the environment variable
                    os.environ['TMDB_API_KEY'] = env_content['TMDB_API_KEY']
                    print("Set TMDB_API_KEY in environment explicitly")
                else:
                    print("Warning: TMDB_API_KEY not found in .env file")
            except Exception as e:
                print(f"Error reading .env file manually: {e}")
        
        return os.environ
        
    except ImportError:
        print("Warning: python-dotenv is not installed, skipping .env loading.")
        print("Run 'pip install python-dotenv' to enable .env loading.")
        return {}
    except Exception as e:
        print(f"Warning: Error loading .env file: {e}")
        return {}

if __name__ == "__main__":
    # If run directly, test the environment loading
    load_env_vars()
    print("\nEnvironment variables loaded. Available variables:")
    for key in ['DJANGO_SECRET_KEY', 'TMDB_API_KEY', 'AWS_ACCESS_KEY_ID', 'STRIPE_PUBLIC_KEY']:
        if key in os.environ:
            val = os.environ[key]
            print(f"{key}: {val[:4]}..." if val else f"{key}: [empty]")
        else:
            print(f"{key}: [not set]")