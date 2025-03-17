from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.http import Http404, HttpResponse
from django.urls import reverse
from movies.tmdb_api import fetch_movie_details
from movies.models import Movie
from django.utils.dateparse import parse_date

from .models import Theater, Showtime, Seat, Booking
from .forms import PaymentForm
from .payment import PaymentService, PaymentError
from .email_service import EmailService
from .ticket_generator import TicketGenerator

import stripe
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

import datetime
import logging

logger = logging.getLogger(__name__)

@login_required
def select_date_time(request, movie_id):
    """View to select date and time for a movie"""
    # Validate the movie_id
    try:
        tmdb_id = int(movie_id)
        if tmdb_id <= 0:
            messages.error(request, "Invalid movie ID")
            return redirect('movies:movie_list')
    except (ValueError, TypeError):
        messages.error(request, "Invalid movie ID format")
        return redirect('movies:movie_list')

    # Try to get the movie from the database by tmdb_id
    try:
        movie = Movie.objects.get(tmdb_id=tmdb_id)
        logger.info(f"Found movie in database with tmdb_id={tmdb_id}")
    except Movie.DoesNotExist:
        # If the movie doesn't exist in our database, get it from TMDB and save it
        logger.info(f"Movie with tmdb_id={tmdb_id} not found in database, fetching from TMDB")
        tmdb_movie = fetch_movie_details(tmdb_id)

        if tmdb_movie:
            # Verify the ID matches what we requested
            if tmdb_movie['tmdb_id'] != tmdb_id:
                logger.error(f"TMDB ID mismatch: requested {tmdb_id}, received {tmdb_movie['tmdb_id']}")
                messages.error(request, "Error retrieving movie information. Please try again.")
                return redirect('movies:movie_list')

            # Create a new Movie object with the TMDB data
            movie_data = {
                'tmdb_id': tmdb_movie['tmdb_id'],  # Use the explicit tmdb_id from response
                'title': tmdb_movie['title'],
                'overview': tmdb_movie.get('overview', ''),
                'poster_path': tmdb_movie.get('poster_path', ''),
                'backdrop_path': tmdb_movie.get('backdrop_path', ''),
            }

            # Handle release_date separately to avoid format issues
            release_date = tmdb_movie.get('release_date', '')
            if release_date and isinstance(release_date, str) and len(release_date) >= 10:  # Check if it's in YYYY-MM-DD format
                try:
                    # Try to parse the date
                    parsed_date = parse_date(release_date)
                    if parsed_date:
                        movie_data['release_date'] = parsed_date
                except (ValueError, TypeError):
                    # If parsing fails, log the error
                    logger.warning(f"Failed to parse release date: {release_date}")
                    # Don't include the release_date
                    pass

            logger.info(f"Creating new movie entry with tmdb_id={tmdb_id}")
            movie = Movie.objects.create(**movie_data)
        else:
            logger.error(f"Failed to fetch movie with tmdb_id={tmdb_id} from TMDB API")
            messages.error(request, "Movie not found or API error occurred.")
            return redirect('movies:movie_list')

    # Get dates for the next 7 days
    today = timezone.now().date()
    dates = [today + datetime.timedelta(days=i) for i in range(7)]

    # Check if there are any showtimes for this movie
    showtimes = Showtime.objects.filter(
        movie=movie,
        date__gte=today
    ).order_by('date', 'time')

    # If no showtimes exist, create some sample ones for testing
    if not showtimes.exists():
        # Get or create theaters with different features
        main_theater, created = Theater.objects.get_or_create(
            name="MovieTime Main Cinema",
            defaults={
                'location': '123 Main Street',
                'total_seats': 48,
                'has_imax': False,
                'has_3d': False
            }
        )

        imax_theater, created = Theater.objects.get_or_create(
            name="MovieTime IMAX",
            defaults={
                'location': '123 Main Street',
                'total_seats': 60,
                'has_imax': True,
                'has_3d': False
            }
        )

        premium_theater, created = Theater.objects.get_or_create(
            name="MovieTime Premium",
            defaults={
                'location': '123 Main Street',
                'total_seats': 36,
                'has_imax': False,
                'has_3d': True
            }
        )

        # Create different showtime patterns based on the movie
        # The patterns differ based on the tmdb_id to ensure variety
        if movie.tmdb_id % 3 == 0:  # Pattern 1
            times = [
                (datetime.time(10, 30), main_theater, 10.00, 8.00),  # Morning, standard
                (datetime.time(14, 0), main_theater, 11.50, 9.00),   # Afternoon, standard
                (datetime.time(17, 30), imax_theater, 15.00, 12.00), # Evening, IMAX
                (datetime.time(20, 0), main_theater, 12.50, 9.50),   # Night, standard
            ]
        elif movie.tmdb_id % 3 == 1:  # Pattern 2
            times = [
                (datetime.time(11, 15), premium_theater, 12.00, 9.50),  # Morning, 3D
                (datetime.time(15, 45), main_theater, 11.00, 8.50),     # Afternoon, standard
                (datetime.time(18, 30), imax_theater, 15.50, 12.50),    # Evening, IMAX
                (datetime.time(21, 15), premium_theater, 13.00, 10.00), # Night, 3D
            ]
        else:  # Pattern 3
            times = [
                (datetime.time(9, 45), main_theater, 9.50, 7.50),       # Morning, standard
                (datetime.time(13, 30), premium_theater, 12.50, 10.00), # Afternoon, 3D
                (datetime.time(16, 45), main_theater, 11.50, 9.00),     # Evening, standard
                (datetime.time(19, 45), imax_theater, 16.00, 13.00),    # Night, IMAX
            ]

        # Create showtimes using get_or_create to avoid duplicate entries
        for i in range(7):
            date = today + datetime.timedelta(days=i)

            # Adjust the number of showtimes per day based on the day of week
            # Weekends have more showtimes
            is_weekend = date.weekday() >= 5  # 5 and 6 are Saturday and Sunday

            # Use all times for weekends, limit for weekdays
            day_times = times if is_weekend else times[:3]

            for time_data in day_times:
                time, theater, price, student_price = time_data
                try:
                    # Try to get existing showtime or create a new one
                    showtime, created = Showtime.objects.get_or_create(
                        movie=movie,
                        theater=theater,
                        date=date,
                        time=time,
                        defaults={
                            'price': price,
                            'student_price': student_price
                        }
                    )

                    # Update the price if it exists but price is not set
                    if not created and (showtime.price == 0 or showtime.student_price == 0):
                        showtime.price = price
                        showtime.student_price = student_price
                        showtime.save()

                except Exception as e:
                    logger.error(f"Error creating showtime: {e}")
                    # Continue with the next time slot if there's an error

        # Refresh the showtimes queryset
        showtimes = Showtime.objects.filter(
            movie=movie,
            date__gte=today
        ).order_by('date', 'time')

    # Group showtimes by date
    showtimes_by_date = {}
    for date in dates:
        showtimes_by_date[date] = showtimes.filter(date=date)

    # If a date and time are selected, redirect to seat selection
    if request.method == 'POST':
        showtime_id = request.POST.get('showtime')
        if showtime_id:
            return redirect('bookings:select_seats', showtime_id=showtime_id)

    context = {
        'movie': movie,
        'dates': dates,
        'showtimes': showtimes,
        'showtimes_by_date': showtimes_by_date,
        'today': today,
    }
    return render(request, 'bookings/select_date_time.html', context)

@login_required
def select_seats(request, showtime_id):
    """View to select seats for a showtime"""
    showtime = get_object_or_404(Showtime, id=showtime_id)

    # Get all seats
    all_seats = Seat.objects.all().order_by('row', 'number')

    # If no seats exist yet, create them
    if not all_seats.exists():
        for row in "ABCDEF":
            for number in range(1, 9):
                Seat.objects.create(row=row, number=number)
        all_seats = Seat.objects.all().order_by('row', 'number')

    # Get booked seats for this showtime
    booked_seats = Seat.objects.filter(
        bookings__showtime=showtime,
        bookings__status='confirmed'
    )

    # Create a list of seat IDs for template comparison (e.g., "A1", "B2")
    booked_seats_display = [f"{seat.row}{seat.number}" for seat in booked_seats]

    if request.method == 'POST':
        # Get selected seats from form
        selected_seat_ids = request.POST.getlist('selected_seats')

        if selected_seat_ids:
            # Store selected seats in session
            request.session['selected_seat_ids'] = selected_seat_ids
            request.session['showtime_id'] = showtime_id

            # Save the session explicitly
            request.session.modified = True

            # Redirect to confirm booking page
            return redirect('bookings:confirm_booking')
        else:
            messages.error(request, "Please select at least one seat.")

    context = {
        'showtime': showtime,
        'booked_seats': booked_seats,
        'booked_seats_display': booked_seats_display,
    }
    return render(request, 'bookings/select_seats.html', context)

@login_required
def payment(request):
    # Get session data
    showtime_id = request.session.get('showtime_id')
    selected_seat_ids = request.session.get('selected_seat_ids')

    if not showtime_id or not selected_seat_ids:
        messages.error(request, 'Please select seats first.')
        return redirect('movies:movie_list')

    showtime = get_object_or_404(Showtime, id=showtime_id)

    # Get the actual Seat objects from the database
    seats = []
    for seat_id in selected_seat_ids:
        row = seat_id[0]  # First character is the row (e.g., "A" from "A1")
        number = int(seat_id[1:])  # Rest is the number (e.g., "1" from "A1")
        try:
            seat = Seat.objects.get(row=row, number=number)
            seats.append(seat)
        except Seat.DoesNotExist:
            # Create the seat if it doesn't exist
            seat = Seat.objects.create(row=row, number=number)
            seats.append(seat)

    # Calculate price based on student discount if applicable
    regular_price = showtime.price * len(seats)
    student_price = showtime.student_price * len(seats)

    # Pre-fill student discount option based on user profile
    initial_data = {}
    if hasattr(request.user, 'profile') and request.user.profile.is_student:
        initial_data['apply_student_discount'] = True
        initial_data['student_id'] = request.user.profile.student_id_number

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Check if student discount is applied
                    apply_student_discount = form.cleaned_data.get('apply_student_discount', False)
                    student_id = form.cleaned_data.get('student_id', '')
                    payment_method = form.cleaned_data.get('payment_method')

                    # Determine total price based on discount
                    total_price = student_price if apply_student_discount else regular_price

                    # Create booking
                    booking = Booking.objects.create(
                        user=request.user,
                        showtime=showtime,
                        total_price=total_price,
                        status='pending',
                        student_discount_applied=apply_student_discount,
                        payment_method=payment_method
                    )

                    # Add seats to booking
                    booking.seats.add(*seats)

                    # If student discount applied, save the info
                    if apply_student_discount:
                        booking.notes = f"Student ID: {student_id} - Verification required"
                        booking.save()

                        # Also update user profile if they're applying student discount
                        if hasattr(request.user, 'profile'):
                            request.user.profile.is_student = True
                            request.user.profile.student_id_number = student_id
                            request.user.profile.save()

                    # Process payment
                    payment_service = PaymentService()
                    payment_result = payment_service.create_payment_intent(booking)

                    # Update booking with payment ID
                    booking.payment_id = payment_result['payment_id']
                    booking.save()

                    # Clear session data
                    if 'selected_seat_ids' in request.session:
                        del request.session['selected_seat_ids']
                    if 'showtime_id' in request.session:
                        del request.session['showtime_id']

                    # Redirect to payment confirmation page
                    return redirect('bookings:payment_confirm', booking_id=booking.id)

            except PaymentError as e:
                messages.error(request, str(e))
                return redirect('bookings:payment')
    else:
        form = PaymentForm(initial=initial_data)

    context = {
        'form': form,
        'showtime': showtime,
        'selected_seats': seats,
        'regular_price': regular_price,
        'student_price': student_price,
        'discount_amount': regular_price - student_price,
        'discount_percentage': int((1 - (showtime.student_price / showtime.price)) * 100),
    }
    return render(request, 'bookings/payment.html', context)

@login_required
def payment_confirm(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    # Validate the booking has a payment ID
    if not booking.payment_id:
        logger.error(f"No payment ID found for booking {booking_id}")
        messages.error(request, 'No payment information found for this booking.')
        return redirect('bookings:payment')

    # Check if booking is already confirmed
    if booking.status == 'confirmed':
        logger.info(f"Booking {booking_id} is already confirmed")
        messages.info(request, 'This booking is already confirmed.')
        return redirect('bookings:booking_detail', booking_id=booking.id)

    try:
        # Confirm payment
        payment_service = PaymentService()
        if payment_service.confirm_payment(booking.payment_id):
            # Update booking status in a transaction
            with transaction.atomic():
                booking.status = 'confirmed'
                booking.save()
                logger.info(f"Booking {booking_id} confirmed with payment {booking.payment_id}")

            # Display student discount verification message if applicable
            if hasattr(booking, 'student_discount_applied') and booking.student_discount_applied:
                messages.warning(
                    request,
                    'Important: You must present a valid student ID at the theater to verify your student discount. '
                    'Failure to provide valid ID may result in you needing to pay the price difference.'
                )

            # Schedule confirmation email with ticket
            email_sent = EmailService.send_booking_confirmation(booking)

            success_msg = 'Payment confirmed successfully.'
            if email_sent:
                success_msg += ' Your ticket has been sent to your email.'
            else:
                success_msg += ' We encountered an issue sending your ticket email. Please view and download your ticket from your booking details.'
                logger.warning(f"Email sending failed for confirmed booking {booking_id}")

            messages.success(request, success_msg)
            return redirect('bookings:booking_detail', booking_id=booking.id)
        else:
            # Get detailed payment status for better error handling
            payment_status = payment_service.get_payment_status(booking.payment_id)
            status_msg = payment_status.get('status', 'unknown')

            logger.warning(f"Payment not confirmed for booking {booking_id}. Status: {status_msg}")
            messages.error(request, f'Payment not confirmed. Status: {status_msg}. Please try again or contact support.')
            return redirect('bookings:payment')

    except PaymentError as e:
        logger.error(f"Payment error for booking {booking_id}: {str(e)}")
        messages.error(request, f'Payment error: {str(e)}. Please try again or contact support.')
        return redirect('bookings:payment')

@login_required
def booking_detail(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    context = {
        'booking': booking,
    }
    return render(request, 'bookings/booking_detail.html', context)

@login_required
def download_ticket(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if booking.status != 'confirmed':
        messages.error(request, 'Ticket is only available for confirmed bookings.')
        return redirect('bookings:booking_detail', booking_id=booking.id)

    # Generate PDF ticket
    pdf_ticket = TicketGenerator.generate_ticket_pdf(booking)

    # Create the HTTP response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ticket_{booking.booking_reference}.pdf"'
    response.write(pdf_ticket)

    return response

@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(
        user=request.user
    ).order_by('-booking_time')

    context = {
        'bookings': bookings,
    }
    return render(request, 'bookings/my_bookings.html', context)

@login_required
def confirm_booking(request):
    """View to confirm booking without payment processing"""
    # Get session data
    showtime_id = request.session.get('showtime_id')
    selected_seat_ids = request.session.get('selected_seat_ids')

    if not showtime_id or not selected_seat_ids:
        messages.error(request, 'Please select seats first.')
        return redirect('movies:movie_list')

    showtime = get_object_or_404(Showtime, id=showtime_id)

    # Get the actual Seat objects from the database
    seats = []
    for seat_id in selected_seat_ids:
        row = seat_id[0]  # First character is the row (e.g., "A" from "A1")
        number = int(seat_id[1:])  # Rest is the number (e.g., "1" from "A1")
        try:
            seat = Seat.objects.get(row=row, number=number)
            seats.append(seat)
        except Seat.DoesNotExist:
            # Create the seat if it doesn't exist
            seat = Seat.objects.create(row=row, number=number)
            seats.append(seat)

    # Calculate total price
    total_price = showtime.price * len(seats)

    if request.method == 'POST':
        # Create booking
        booking = Booking.objects.create(
            user=request.user,
            showtime=showtime,
            total_price=total_price,
            status='confirmed'
        )

        # Add seats to booking
        booking.seats.add(*seats)

        # Clear session data
        if 'selected_seat_ids' in request.session:
            del request.session['selected_seat_ids']
        if 'showtime_id' in request.session:
            del request.session['showtime_id']

        # Schedule email confirmation via Celery
        EmailService.send_booking_confirmation(booking)

        messages.success(request, 'Booking confirmed successfully! Your ticket will be sent to your email shortly.')
        return redirect('bookings:booking_detail', booking_id=booking.id)

    context = {
        'showtime': showtime,
        'selected_seats': seats,
        'selected_seat_ids': selected_seat_ids,
        'total_price': total_price,
    }
    return render(request, 'bookings/confirm_booking.html', context)
