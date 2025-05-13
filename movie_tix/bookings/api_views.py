from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction

from .models import Theater, Showtime, Seat, Booking
from .serializers import (
    TheaterSerializer,
    ShowtimeSerializer,
    SeatSerializer,
    BookingSerializer,
)
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
        booked_seat_ids = Seat.objects.filter(
            bookings__showtime=showtime,
            bookings__status='confirmed'
        ).values_list('id', flat=True)

        available_seats = Seat.objects.exclude(id__in=booked_seat_ids).order_by('row', 'number')
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
        Return bookings for current user, or all if user is staff.
        """
        user = self.request.user
        return Booking.objects.all() if user.is_staff else Booking.objects.filter(user=user)

    def _user_has_access(self, user, booking):
        return user.is_staff or booking.user == user

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
        Confirm payment for a booking and mark it as confirmed.
        """
        booking = self.get_object()

        if not self._user_has_access(request.user, booking):
            return Response(
                {"error": "You don't have permission to confirm this booking"},
                status=status.HTTP_403_FORBIDDEN
            )

        if booking.status == 'confirmed':
            return Response(
                {"error": "This booking is already confirmed"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not booking.payment_id:
            return Response(
                {"error": "No payment information found for this booking"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            payment_service = PaymentService()
            if payment_service.confirm_payment(booking.payment_id):
                with transaction.atomic():
                    booking.status = 'confirmed'
                    booking.save()

                EmailService.send_booking_confirmation(booking)
                serializer = self.get_serializer(booking)
                return Response(serializer.data)
            else:
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