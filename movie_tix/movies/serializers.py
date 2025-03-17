from rest_framework import serializers
from .models import Movie

class MovieSerializer(serializers.ModelSerializer):
    """
    Serializer for the Movie model.
    """
    class Meta:
        model = Movie
        fields = ['id', 'tmdb_id', 'title', 'overview', 'poster_path', 'backdrop_path', 'release_date']