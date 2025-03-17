from django.shortcuts import render
from django.conf import settings
import os
from .tmdb_api import fetch_popular_movies, fetch_movie_details, search_movies

def movie_list_view(request):
    """
    View to display a list of popular movies.
    """
    # Check if TMDB API key is configured
    api_key = settings.TMDB_API_KEY or os.environ.get('TMDB_API_KEY', '')
    
    # Try to get movies from API
    movies = fetch_popular_movies(limit=21)
    
    # If no movies were returned, and we appear to have an API key,
    # there might be a connectivity issue - test the API key
    api_working = True
    if not movies and api_key:
        from movies.tmdb_api import test_api_key
        api_working, message = test_api_key()
        
    # If API is not working or no movies, use mock data in development
    if not movies and settings.DEBUG:
        # Create sample movies for development
        movies = _get_mock_movies(12)
    
    # Add context for template to show API key message if needed
    context = {
        'movies': movies,
        'api_key_configured': bool(api_key),
        'api_working': api_working,
    }
    return render(request, 'movies/movie_list.html', context)

def _get_mock_movies(count=9):
    """Generate mock movie data for development when API is unavailable"""
    movie_titles = [
        "The Space Between Stars", "Midnight Whispers", "The Last Guardian",
        "Echoes of Tomorrow", "Phantom Protocol", "Beyond the Horizon",
        "Legends of the Deep", "City of Dreams", "Shadows of the Past",
        "The Final Countdown", "Whispers in the Dark", "Forgotten Kingdom"
    ]
    
    release_years = ["2023", "2024", "2025"]
    
    mock_movies = []
    import random
    
    for i in range(min(count, len(movie_titles))):
        year = random.choice(release_years)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        
        movie = {
            'id': 1000 + i,
            'title': movie_titles[i],
            'poster_path': None,  # No poster available
            'release_date': f"{year}-{month:02d}-{day:02d}",
        }
        mock_movies.append(movie)
        
    return mock_movies

def movie_detail_view(request, tmdb_id):
    """
    View to display details of a specific movie.
    """
    details = fetch_movie_details(tmdb_id)
    
    # If details not available and in debug mode, generate mock details
    if not details and settings.DEBUG:
        # For development only - create mock movie details
        import random
        mock_titles = [
            "The Space Between Stars", "Midnight Whispers", "The Last Guardian",
            "Echoes of Tomorrow", "Phantom Protocol"
        ]
        year = random.choice(["2023", "2024", "2025"])
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        
        details = {
            'id': int(tmdb_id),
            'tmdb_id': int(tmdb_id),
            'title': mock_titles[int(tmdb_id) % len(mock_titles)],
            'overview': "This is a mock movie description for development purposes when the TMDB API is unavailable. "
                      "The movie features an ensemble cast in an epic adventure that spans galaxies and generations. "
                      "Critical acclaim and audience praise have followed this film since its theatrical release.",
            'poster_path': None,
            'backdrop_path': None,
            'release_date': f"{year}-{month:02d}-{day:02d}",
            'formatted_release_date': f"{month:02d}/{day:02d}/{year}",
            'trailer_key': None,
        }
        
    # If still no details, show error
    if not details:
        api_key = settings.TMDB_API_KEY or os.environ.get('TMDB_API_KEY', '')
        context = {
            'error': 'Movie details not available.',
            'api_key_configured': bool(api_key),
        }
        return render(request, 'movies/movie_detail.html', context)
        
    return render(request, 'movies/movie_detail.html', {'movie': details})

def search_results_view(request):
    """
    View to handle movie search queries.
    """
    query = request.GET.get('q', '')
    results = search_movies(query) if query else []
    return render(request, 'movies/search_results.html', {'query': query, 'results': results})
