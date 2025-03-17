from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Movie
from .serializers import MovieSerializer
from .tmdb_api import fetch_popular_movies, fetch_movie_details, search_movies

class MovieViewSet(viewsets.ModelViewSet):
    """
    API endpoint for movies.
    """
    queryset = Movie.objects.all()
    serializer_class = MovieSerializer
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """
        Get popular movies from TMDB API.
        """
        limit = int(request.query_params.get('limit', 12))
        movies = fetch_popular_movies(limit=limit)
        return Response(movies)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Search movies by query string.
        """
        query = request.query_params.get('q', '')
        if not query:
            return Response(
                {"error": "Query parameter 'q' is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        results = search_movies(query)
        return Response(results)
    
    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """
        Get detailed information for a specific movie from TMDB.
        """
        try:
            tmdb_id = int(pk)
            details = fetch_movie_details(tmdb_id)
            if details:
                return Response(details)
            return Response(
                {"error": "Movie details not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError:
            return Response(
                {"error": "Invalid movie ID"},
                status=status.HTTP_400_BAD_REQUEST
            )