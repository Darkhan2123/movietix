from rest_framework import serializers
from .models import Theater, Showtime, Seat, Booking

class TheaterSerializer(serializers.ModelSerializer):
    """
    Serializer for the Theater model.
    """
    class Meta:
        model = Theater
        fields = ['id', 'name', 'location', 'address', 'city', 'state', 'postal_code',
                 'total_seats', 'phone', 'email', 'website', 'description',
                 'has_imax', 'has_3d', 'has_parking', 'is_accessible',
                 'opening_time', 'closing_time']

class SeatSerializer(serializers.ModelSerializer):
    """
    Serializer for the Seat model.
    """
    class Meta:
        model = Seat
        fields = ['id', 'row', 'number']

class ShowtimeSerializer(serializers.ModelSerializer):
    """
    Serializer for the Showtime model.
    """
    theater = TheaterSerializer(read_only=True)
    movie_title = serializers.CharField(source='movie.title', read_only=True)
    
    class Meta:
        model = Showtime
        fields = ['id', 'movie', 'movie_title', 'theater', 'date', 'time', 
                 'price', 'student_price', 'is_active']

class BookingSerializer(serializers.ModelSerializer):
    """
    Serializer for the Booking model.
    """
    seats = SeatSerializer(many=True, read_only=True)
    showtime = ShowtimeSerializer(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Booking
        fields = ['id', 'username', 'showtime', 'seats', 'booking_time', 
                 'status', 'total_price', 'booking_reference',
                 'student_discount_applied', 'payment_method']