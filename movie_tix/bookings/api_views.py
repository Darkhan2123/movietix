from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from .models import Theater, Showtime, Seat, Booking
from .serializers import TheaterSerializer, ShowtimeSerializer, SeatSerializer, BookingSerializer
from .payment import PaymentService, PaymentError
from .email_service import EmailService

class TheaterViewSet(viewsets.ModelViewSet):
    """
    API endpoint for theaters.
    """
    queryset = Theater.objects.all()
    serializer_class = TheaterSerializer

class ShowtimeViewSet(viewsets.ModelViewSet):
    """
    API endpoint for showtimes.
    """
    queryset = Showtime.objects.all().order_by('date', 'time')
    serializer_class = ShowtimeSerializer
    
    @action(detail=False, methods=['get'])
    def movie_showtimes(self, request):
        """
        Filter showtimes by movie ID.
        """
        movie_id = request.query_params.get('movie_id')
        if not movie_id:
            return Response(
                {"error": "movie_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        showtimes = self.queryset.filter(movie_id=movie_id)
        serializer = self.get_serializer(showtimes, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def available_seats(self, request, pk=None):
        """
        Get available seats for a specific showtime.
        """
        showtime = self.get_object()
        booked_seats = Seat.objects.filter(
            bookings__showtime=showtime,
            bookings__status='confirmed'
        )
        
        all_seats = Seat.objects.all().order_by('row', 'number')
        available_seats = [seat for seat in all_seats if seat not in booked_seats]
        
        serializer = SeatSerializer(available_seats, many=True)
        return Response(serializer.data)

class SeatViewSet(viewsets.ModelViewSet):
    """
    API endpoint for seats.
    """
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer

class BookingViewSet(viewsets.ModelViewSet):
    """
    API endpoint for bookings.
    """
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Filter bookings to return only those belonging to the current user,
        unless the user is staff.
        """
        if self.request.user.is_staff:
            return Booking.objects.all()
        return Booking.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_bookings(self, request):
        """
        Get all bookings for the current user.
        """
        bookings = Booking.objects.filter(user=request.user).order_by('-booking_time')
        serializer = self.get_serializer(bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def confirm_payment(self, request, pk=None):
        """
        Confirm payment for a booking.
        """
        booking = self.get_object()
        
        # Validate that the booking belongs to the current user
        if booking.user != request.user and not request.user.is_staff:
            return Response(
                {"error": "You don't have permission to confirm this booking"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if booking is already confirmed
        if booking.status == 'confirmed':
            return Response(
                {"error": "This booking is already confirmed"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if booking has a payment ID
        if not booking.payment_id:
            return Response(
                {"error": "No payment information found for this booking"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Confirm payment
            payment_service = PaymentService()
            if payment_service.confirm_payment(booking.payment_id):
                # Update booking status in a transaction
                with transaction.atomic():
                    booking.status = 'confirmed'
                    booking.save()
                
                # Send confirmation email
                EmailService.send_booking_confirmation(booking)
                
                serializer = self.get_serializer(booking)
                return Response(serializer.data)
            else:
                # Get detailed payment status
                payment_status = payment_service.get_payment_status(booking.payment_id)
                status_msg = payment_status.get('status', 'unknown')
                
                return Response(
                    {"error": f"Payment not confirmed. Status: {status_msg}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except PaymentError as e:
            return Response(
                {"error": f"Payment error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )