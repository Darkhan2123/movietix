import requests
import logging
import os
import sys
from datetime import datetime
from django.conf import settings
from django.core.cache import cache
import json

logger = logging.getLogger(__name__)

# First try to get API key from settings
TMDB_API_KEY = getattr(settings, 'TMDB_API_KEY', '')

# If not found in settings, try environment variables
if not TMDB_API_KEY:
    TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '')
    if TMDB_API_KEY:
        logger.info(f"Using TMDB API key from environment: {TMDB_API_KEY[:4]}...")

# Last resort: try loading directly from .env file
if not TMDB_API_KEY:
    try:
        import dotenv
        from pathlib import Path
        
        # Try multiple locations for .env file
        base_dir = Path(__file__).resolve().parent.parent
        env_paths = [
            base_dir / '.env',                 # movies/.env
            base_dir.parent / '.env',          # project/.env 
            Path(os.getcwd()) / '.env',        # current dir/.env
        ]
        
        for env_path in env_paths:
            if env_path.exists():
                env_vars = dotenv.dotenv_values(str(env_path))
                if 'TMDB_API_KEY' in env_vars and env_vars['TMDB_API_KEY']:
                    TMDB_API_KEY = env_vars['TMDB_API_KEY']
                    logger.info(f"Loaded TMDB API key directly from {env_path}: {TMDB_API_KEY[:4]}...")
                    break
    except Exception as e:
        logger.error(f"Failed to load TMDB API key from .env file: {e}")

# Use hardcoded development key as final fallback
if not TMDB_API_KEY:
    # Hardcoded API key for development only - should be removed in production
    TMDB_API_KEY = '9c52f42462d276f88fc32d0f13411270'
    logger.warning(f"Using hardcoded TMDB API key for development: {TMDB_API_KEY[:4]}...")

TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Log API key status at module initialization
if TMDB_API_KEY:
    logger.info(f"TMDB API initialized with key: {TMDB_API_KEY[:4]}...")
else:
    logger.critical("TMDB API initialization FAILED - no API key available!")

# Create test function to verify API key works
def test_api_key():
    """Tests if the API key is valid by making a simple request"""
    if not TMDB_API_KEY:
        return False, "No API key found"
        
    url = f"{TMDB_BASE_URL}/configuration?api_key={TMDB_API_KEY}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return True, "API key is valid"
        elif response.status_code == 401:
            return False, f"API key is invalid. Response: {response.text}"
        else:
            return False, f"Unexpected status code: {response.status_code}"
    except Exception as e:
        return False, f"Error testing API key: {str(e)}"

def fetch_popular_movies(limit=20):
    """Fetch trending movies from TMDB API, limited to 20 movies."""
    # Return empty list if no API key
    if not TMDB_API_KEY:
        logger.error("Cannot fetch popular movies: No TMDB API key configured")
        return []
        
    cache_key = 'tmdb_trending_movies'
    movies = cache.get(cache_key)
    if movies is None:
        url = f"{TMDB_BASE_URL}/trending/movie/week?api_key={TMDB_API_KEY}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            movies = []
            for movie in data.get('results', [])[:limit]:
                movies.append({
                    'id': movie['id'],
                    'title': movie.get('title'),
                    'poster_path': movie.get('poster_path'),
                    'release_date': movie.get('release_date'),
                })
            cache.set(cache_key, movies, 3600)
        except requests.RequestException as e:
            logger.error(f"Error fetching trending movies: {e}")
            movies = []
    return movies

def fetch_movie_details(movie_id):
    """Fetch movie details from TMDB API and append videos for trailer info."""
    # Return None if no API key
    if not TMDB_API_KEY:
        logger.error("Cannot fetch movie details: No TMDB API key configured")
        return None
        
    # Ensure movie_id is an integer
    try:
        movie_id = int(movie_id)
    except (ValueError, TypeError):
        logger.error(f"Invalid TMDB ID format: {movie_id}")
        return None

    # Check for valid range of movie_id
    if movie_id <= 0:
        logger.error(f"Invalid TMDB ID value (must be positive): {movie_id}")
        return None

    url = f"{TMDB_BASE_URL}/movie/{movie_id}?api_key={TMDB_API_KEY}&append_to_response=videos"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Validate that the ID we received matches the ID we requested
        if 'id' not in data or data['id'] != movie_id:
            logger.error(f"TMDB ID mismatch: requested {movie_id}, received {data.get('id')}")
            return None
            
    except requests.RequestException as e:
        logger.error(f"Error fetching movie details for {movie_id}: {e}")
        return None
    except ValueError as e:
        logger.error(f"Error parsing JSON response for movie {movie_id}: {e}")
        return None

    # Find trailer key for YouTube trailers
    trailer_key = None
    for video in data.get('videos', {}).get('results', []):
        if video.get('type') == 'Trailer' and video.get('site') == 'YouTube':
            trailer_key = video.get('key')
            break

    # Process release date
    formatted_release_date = None
    db_release_date = None
    if data.get('release_date'):
        try:
            date_obj = datetime.strptime(data['release_date'], '%Y-%m-%d')
            formatted_release_date = date_obj.strftime('%B %d, %Y')
            db_release_date = data['release_date']  # Keep original format for DB storage
        except ValueError:
            logger.warning(f"Invalid release date format from TMDB: {data.get('release_date')}")
            db_release_date = None

    movie = {
        'id': data['id'],  # Use direct access since we validated existence
        'tmdb_id': data['id'],  # Include explicit tmdb_id to avoid confusion
        'title': data.get('title', ''),
        'overview': data.get('overview', ''),
        'poster_path': data.get('poster_path', ''),
        'backdrop_path': data.get('backdrop_path', ''),
        'release_date': db_release_date,
        'formatted_release_date': formatted_release_date,  # Human-readable version
        'trailer_key': trailer_key,
    }
    return movie

def search_movies(query, limit=20):
    """
    Search for movies matching the query.
    No caching is applied for search results.
    """
    # Return empty list if no API key
    if not TMDB_API_KEY:
        logger.error("Cannot search movies: No TMDB API key configured")
        return []
        
    url = f"{TMDB_BASE_URL}/search/movie"
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'en-US',
        'query': query,
        'page': 1,
        'include_adult': False,
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get('results', [])[:limit]
    except requests.RequestException as e:
        logger.error(f"Error searching movies with query '{query}': {e}")
        results = []
    return results
