import datetime
import logging
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from movies.models import Movie
from movies.tmdb_api import fetch_movie_details
from .email_service import EmailService
from .forms import PaymentForm
from .models import Theater, Showtime, Seat, Booking
from .payment import PaymentService, PaymentError
from .ticket_generator import TicketGenerator


logger = logging.getLogger(__name__)

@login_required
def select_date_time(request, movie_id):
    """View to select date and time for a movie"""
    # Validate the movie_id

    import time
    start_time = time.time()
    logger.info("START: select_date_time")

    try:
        tmdb_id = int(movie_id)
        if tmdb_id <= 0:
            return JsonResponse({
                'success': False,
                'message': "Invalid movie ID"
            }, status=400)
    except (ValueError, TypeError):
        return JsonResponse({
            'success': False,
            'message': "Invalid movie ID format"
        }, status=400)

    logger.info(f"[{tmdb_id}] After validation: {time.time() - start_time:.2f}s")

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
                return JsonResponse({
                    'success': False,
                    'message': "Error retrieving movie information. Please try again."
                }, status=500)

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
            return JsonResponse({
                'success': False,
                'message': "Movie not found or API error occurred."
            }, status=404)

    # Get dates for the next 7 days
    today = timezone.now().date()
    dates = [today + datetime.timedelta(days=i) for i in range(7)]
    formatted_dates = [date.strftime('%Y-%m-%d') for date in dates]

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

    # Group showtimes by date and format for JSON response
    showtimes_by_date = {}
    for date in dates:
        date_str = date.strftime('%Y-%m-%d')
        date_showtimes = []
        
        for showtime in showtimes.filter(date=date):
            date_showtimes.append({
                'id': showtime.id,
                'time': showtime.time.strftime('%H:%M'),
                'theater': {
                    'id': showtime.theater.id,
                    'name': showtime.theater.name,
                    'has_imax': showtime.theater.has_imax,
                    'has_3d': showtime.theater.has_3d
                },
                'price': float(showtime.price),
                'student_price': float(showtime.student_price),
                'available_seats': showtime.get_available_seats_count()
            })
        
        showtimes_by_date[date_str] = date_showtimes

    # Prepare movie data for response
    movie_data = {
        'id': movie.id,
        'tmdb_id': movie.tmdb_id,
        'title': movie.title,
        'overview': movie.overview,
        'poster_path': movie.poster_path,
        'backdrop_path': movie.backdrop_path,
        'release_date': movie.release_date.isoformat() if movie.release_date else None
    }

    response_data = {
        'movie': movie_data,
        'dates': formatted_dates,
        'showtimes_by_date': showtimes_by_date
    }
    
    return JsonResponse(response_data)

@login_required
def select_seats(request, showtime_id):
    """API view to get available seats for a showtime"""
    # Get the showtime by ID
    showtime = get_object_or_404(Showtime, id=showtime_id)
    
    # Get all seats for this showtime
    all_seats = Seat.objects.filter(showtime=showtime)
    
    # If no seats exist for this showtime, create them
    if not all_seats.exists():
        # Create initial seats for this showtime if they don't exist yet
        logger.info(f"Creating seats for showtime {showtime_id}")
        seats = []
        
        # Determine rows and columns based on total_seats
        total_seats = showtime.theater.total_seats
        if total_seats <= 36:
            rows = 6
            columns = 6
        elif total_seats <= 48:
            rows = 8
            columns = 6
        else:
            rows = 8
            columns = 8
        
        # Create seats with row and column labels
        for i in range(1, rows + 1):
            row_label = chr(64 + i)  # A, B, C, etc.
            for j in range(1, columns + 1):
                seat = Seat(
                    showtime=showtime,
                    row=row_label,
                    number=j,
                    is_reserved=False
                )
                seats.append(seat)
        
        # Bulk create all seats
        Seat.objects.bulk_create(seats)
        
        # Get all seats after creation
        all_seats = Seat.objects.filter(showtime=showtime)
    
    # Convert seat data to a format suitable for JSON response
    rows = {}
    for seat in all_seats:
        if seat.row not in rows:
            rows[seat.row] = []
        
        rows[seat.row].append({
            'id': seat.id,
            'row': seat.row,
            'number': seat.number,
            'is_reserved': seat.is_reserved,
            'price': float(showtime.price),
            'student_price': float(showtime.student_price)
        })
    
    # Sort rows by row letter
    sorted_rows = [{'row': row, 'seats': seats} for row, seats in sorted(rows.items())]
    
    # Prepare movie data
    movie_data = {
        'id': showtime.movie.id,
        'tmdb_id': showtime.movie.tmdb_id,
        'title': showtime.movie.title
    }
    
    # Prepare showtime data
    showtime_data = {
        'id': showtime.id,
        'date': showtime.date.isoformat(),
        'time': showtime.time.strftime('%H:%M'),
        'theater': {
            'id': showtime.theater.id,
            'name': showtime.theater.name,
            'has_imax': showtime.theater.has_imax,
            'has_3d': showtime.theater.has_3d
        },
        'price': float(showtime.price),
        'student_price': float(showtime.student_price)
    }
    
    # Return JSON response with all required data
    return JsonResponse({
        'movie': movie_data,
        'showtime': showtime_data,
        'seat_rows': sorted_rows,
        'is_student': request.user.profile.is_student if hasattr(request.user, 'profile') else False
    })

@login_required
def payment(request):
    """API endpoint to process payment for a booking"""
    # Get session data
    showtime_id = request.session.get('showtime_id')
    selected_seat_ids = request.session.get('selected_seat_ids', [])
    
    if not showtime_id or not selected_seat_ids:
        return JsonResponse({
            'success': False,
            'message': 'Invalid booking data. Please start over.'
        }, status=400)
    
    # Get the showtime
    try:
        showtime = Showtime.objects.get(id=showtime_id)
    except Showtime.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Showtime not found'
        }, status=404)
    
    # Get the selected seats
    selected_seats = Seat.objects.filter(id__in=selected_seat_ids)
    
    # Check if any of the selected seats are already reserved
    reserved_seats = selected_seats.filter(is_reserved=True)
    if reserved_seats.exists():
        # Format the list of reserved seats for display
        reserved_seat_labels = [f"{seat.row}{seat.number}" for seat in reserved_seats]
        return JsonResponse({
            'success': False,
            'message': f"One or more selected seats are no longer available: {', '.join(reserved_seat_labels)}",
            'reserved_seats': list(reserved_seat_labels)
        }, status=409)  # Conflict status code
    
    # Prepare data for payment form
    if hasattr(request.user, 'profile') and request.user.profile.is_student:
        unit_price = showtime.student_price
    else:
        unit_price = showtime.price
    
    seat_count = len(selected_seats)
    total_price = unit_price * seat_count
    
    # Get or create instance of PaymentService
    payment_service = PaymentService()
    
    if request.method == 'POST':
        # Process the payment form
        form = PaymentForm(request.POST)
        if form.is_valid():
            # Get form data
            card_number = form.cleaned_data['card_number']
            expiry_date = form.cleaned_data['expiry_date']
            cvv = form.cleaned_data['cvv']
            name_on_card = form.cleaned_data['name_on_card']
            
            # Create payment description
            payment_description = f"MovieTix booking for {showtime.movie.title} on {showtime.date}, {showtime.time}"
            
            try:
                # Process payment
                payment_result = payment_service.process_payment(
                    amount=total_price,
                    card_number=card_number,
                    expiry_date=expiry_date,
                    cvv=cvv,
                    name=name_on_card,
                    description=payment_description
                )
                
                # If payment is successful, create booking
                with transaction.atomic():
                    # Create booking
                    booking = Booking.objects.create(
                        user=request.user,
                        showtime=showtime,
                        booking_time=timezone.now(),
                        payment_id=payment_result.get('payment_id', ''),
                        total_price=total_price,
                        status='confirmed'
                    )
                    
                    # Associate seats with the booking and mark them as reserved
                    for seat in selected_seats:
                        seat.is_reserved = True
                        seat.bookings.add(booking)
                        seat.save()
                    
                    # Clear booking session data
                    if 'showtime_id' in request.session:
                        del request.session['showtime_id']
                    if 'selected_seat_ids' in request.session:
                        del request.session['selected_seat_ids']
                    request.session.modified = True
                    
                    # Return success response with booking details
                    return JsonResponse({
                        'success': True,
                        'message': 'Payment successful!',
                        'booking_id': booking.id,
                        'redirect': f"/bookings/{booking.id}/"
                    })
                    
            except PaymentError as e:
                # Return payment error
                logger.error(f"Payment error: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'message': f"Payment failed: {str(e)}"
                }, status=400)
        else:
            # Return form validation errors
            return JsonResponse({
                'success': False,
                'message': 'Invalid payment information',
                'errors': form.errors
            }, status=400)
    
    # For GET requests, return booking information
    seat_labels = [f"{seat.row}{seat.number}" for seat in selected_seats]
    
    return JsonResponse({
        'showtime': {
            'id': showtime.id,
            'movie': {
                'id': showtime.movie.id,
                'title': showtime.movie.title
            },
            'date': showtime.date.isoformat(),
            'time': showtime.time.strftime('%H:%M'),
            'theater': showtime.theater.name
        },
        'seats': seat_labels,
        'seat_count': seat_count,
        'unit_price': float(unit_price),
        'total_price': float(total_price),
        'payment_required_fields': [
            {'name': 'card_number', 'type': 'text', 'maxlength': 16, 'placeholder': 'Card Number', 'required': True},
            {'name': 'expiry_date', 'type': 'text', 'maxlength': 5, 'placeholder': 'MM/YY', 'required': True},
            {'name': 'cvv', 'type': 'text', 'maxlength': 3, 'placeholder': 'CVV', 'required': True},
            {'name': 'name_on_card', 'type': 'text', 'placeholder': 'Name on Card', 'required': True}
        ]
    })

@login_required
def payment_confirm(request, booking_id):
    """API endpoint to confirm a successful payment"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Check if booking is confirmed
    if booking.status != 'confirmed':
        return JsonResponse({
            'success': False,
            'message': 'Booking not confirmed'
        }, status=400)
    
    # Generate and send ticket if not already sent
    if not booking.ticket_sent:
        try:
            ticket_generator = TicketGenerator()
            email_service = EmailService()
            
            # Generate ticket
            ticket_path = ticket_generator.generate_ticket(booking)
            
            # Send email with ticket
            email_service.send_ticket_email(booking, ticket_path)
            
            # Mark ticket as sent
            booking.ticket_sent = True
            booking.save()
        except Exception as e:
            logger.error(f"Error sending ticket for booking {booking_id}: {str(e)}")
            # Continue even if ticket sending fails
    
    # Get seats information
    seats = booking.seats.all()
    seat_labels = [f"{seat.row}{seat.number}" for seat in seats]
    
    return JsonResponse({
        'success': True,
        'booking': {
            'id': booking.id,
            'user': booking.user.username,
            'showtime': {
                'id': booking.showtime.id,
                'movie': {
                    'id': booking.showtime.movie.id,
                    'title': booking.showtime.movie.title
                },
                'date': booking.showtime.date.isoformat(),
                'time': booking.showtime.time.strftime('%H:%M'),
                'theater': booking.showtime.theater.name
            },
            'booking_time': booking.booking_time.isoformat(),
            'seats': seat_labels,
            'total_price': float(booking.total_price),
            'status': booking.status,
            'ticket_sent': booking.ticket_sent
        }
    })

@login_required
def booking_detail(request, booking_id):
    """API endpoint to get details for a specific booking"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Get seats information
    seats = booking.seats.all()
    seat_labels = [f"{seat.row}{seat.number}" for seat in seats]
    
    return JsonResponse({
        'booking': {
            'id': booking.id,
            'user': booking.user.username,
            'showtime': {
                'id': booking.showtime.id,
                'movie': {
                    'id': booking.showtime.movie.id,
                    'title': booking.showtime.movie.title
                },
                'date': booking.showtime.date.isoformat(),
                'time': booking.showtime.time.strftime('%H:%M'),
                'theater': booking.showtime.theater.name
            },
            'booking_time': booking.booking_time.isoformat(),
            'seats': seat_labels,
            'total_price': float(booking.total_price),
            'status': booking.status,
            'ticket_sent': booking.ticket_sent,
            'ticket_download_url': f"/bookings/download-ticket/{booking.id}/"
        }
    })

@login_required
def download_ticket(request, booking_id):
    """Endpoint to download a ticket for a booking"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Check if booking is confirmed
    if booking.status != 'confirmed':
        return JsonResponse({
            'success': False,
            'message': 'Booking not confirmed'
        }, status=400)
    
    # Generate ticket PDF
    ticket_generator = TicketGenerator()
    ticket_path = ticket_generator.generate_ticket(booking)
    
    # Return file as attachment
    with open(ticket_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="ticket_{booking_id}.pdf"'
        return response

@login_required
def my_bookings(request):
    """API endpoint to list all bookings for the current user"""
    from django.utils import timezone
    
    # Get user bookings
    bookings = Booking.objects.filter(user=request.user).order_by('-booking_time')
    
    # Separate upcoming and past bookings
    today = timezone.now().date()
    upcoming_bookings = []
    past_bookings = []
    
    for booking in bookings:
        booking_data = {
            'id': booking.id,
            'showtime': {
                'id': booking.showtime.id,
                'movie': {
                    'id': booking.showtime.movie.id,
                    'title': booking.showtime.movie.title
                },
                'date': booking.showtime.date.isoformat(),
                'time': booking.showtime.time.strftime('%H:%M'),
                'theater': booking.showtime.theater.name
            },
            'booking_time': booking.booking_time.isoformat(),
            'seats': [f"{seat.row}{seat.number}" for seat in booking.seats.all()],
            'total_price': float(booking.total_price),
            'status': booking.status
        }
        
        if booking.showtime.date >= today:
            upcoming_bookings.append(booking_data)
        else:
            past_bookings.append(booking_data)
    
    return JsonResponse({
        'upcoming_bookings': upcoming_bookings,
        'past_bookings': past_bookings,
        'total_bookings': len(bookings)
    })

@login_required
def confirm_booking(request):
    """API endpoint to confirm seat selection and proceed to payment"""
    # Get session data
    showtime_id = request.session.get('showtime_id')
    selected_seat_ids = request.session.get('selected_seat_ids', [])
    
    if not showtime_id or not selected_seat_ids:
        return JsonResponse({
            'success': False,
            'message': 'No seats selected. Please select seats first.'
        }, status=400)
    
    # Get the showtime
    try:
        showtime = Showtime.objects.get(id=showtime_id)
    except Showtime.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Showtime not found'
        }, status=404)
    
    # Get the selected seats
    selected_seats = Seat.objects.filter(id__in=selected_seat_ids)
    
    # Check if any of the selected seats are already reserved
    if selected_seats.filter(is_reserved=True).exists():
        return JsonResponse({
            'success': False,
            'message': 'One or more selected seats are no longer available. Please select different seats.'
        }, status=409)
    
    # Calculate price
    if hasattr(request.user, 'profile') and request.user.profile.is_student:
        unit_price = showtime.student_price
    else:
        unit_price = showtime.price
    
    total_price = unit_price * len(selected_seats)
    
    return JsonResponse({
        'success': True,
        'showtime': {
            'id': showtime.id,
            'movie': {
                'id': showtime.movie.id,
                'title': showtime.movie.title
            },
            'date': showtime.date.isoformat(),
            'time': showtime.time.strftime('%H:%M'),
            'theater': showtime.theater.name
        },
        'seats': [f"{seat.row}{seat.number}" for seat in selected_seats],
        'unit_price': float(unit_price),
        'total_price': float(total_price),
        'redirect': '/bookings/payment/'
    })