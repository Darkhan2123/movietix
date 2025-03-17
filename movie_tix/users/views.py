from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator
from .forms import RegisterForm, UserUpdateForm, ProfileUpdateForm
import logging
import importlib.util
from django.http import HttpResponse
from django.core.mail import send_mail
from django.conf import settings
# Check if Celery is available
celery_available = importlib.util.find_spec('celery') is not None

# Try to import tasks, handle potential import errors
try:
    from .tasks import send_verification_email, send_verification_email_sync
    tasks_available = True
except (ImportError, ModuleNotFoundError):
    tasks_available = False
    logging.warning("Failed to import Celery tasks for email verification. Using synchronous fallback.")

logger = logging.getLogger(__name__)


def landing_view(request):
    """
    Landing view that redirects authenticated users to movies list
    and unauthenticated users to login
    """
    if request.user.is_authenticated:
        return redirect('movies:movie_list')
    return render(request, 'landing.html')  # Create a nice landing page instead of redirecting directly to login

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')

            # Create the user but don't log them in yet
            user = User.objects.create_user(username=username, email=email, password=password)
            
            # Explicitly create UserRole if it doesn't exist
            from users.models import UserRole
            customer_role, _ = UserRole.objects.get_or_create(
                name='customer',
                defaults={'description': 'Regular user who can book tickets'}
            )
            
            # Ensure the user has a profile
            if not hasattr(user, 'profile'):
                from users.models import Profile
                Profile.objects.create(user=user, role=customer_role)
                logger.info(f"Created profile for user {username}")

            # Try to send verification email using Celery if available
            email_sent = False
            if celery_available and tasks_available:
                try:
                    # Schedule verification email to be sent via Celery
                    send_verification_email.delay(user.id)
                    email_sent = True
                    logger.info(f"Scheduled verification email for user {user.id}")
                except Exception as e:
                    logger.warning(f"Failed to schedule email with Celery: {e}. Using synchronous fallback.")

            # If Celery is unavailable or failed, use synchronous sending
            if not email_sent:
                try:
                    if tasks_available:
                        send_verification_email_sync(user.id)
                    else:
                        # If even import failed, just log a warning - could implement direct sending here
                        logger.warning("Could not send verification email - task module not available")
                    email_sent = True
                except Exception as e:
                    logger.error(f"Failed to send verification email: {e}")
                    messages.warning(request, 'Your account was created, but we could not send the verification email. Please contact support.')
                    email_sent = False

            if email_sent:
                messages.success(request, 'Your account has been created! Please check your email to verify your account.')
            
            # In DEBUG mode, automatically mark email as verified
            if settings.DEBUG:
                user.profile.email_verified = True
                user.profile.save()
                messages.info(request, 'DEBUG MODE: Email automatically verified')

            return redirect('users:login')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})

def verify_email(request, uidb64, token):
    try:
        # Decode the user id
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)

        # Check if the token is valid
        if default_token_generator.check_token(user, token):
            # Mark email as verified
            user.profile.email_verified = True
            user.profile.save()

            # Log the user in
            login(request, user)

            messages.success(request, 'Your email has been verified successfully! You are now logged in.')
            return redirect('movies:movie_list')
        else:
            messages.error(request, 'The verification link is invalid or has expired.')
            return redirect('users:login')
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        messages.error(request, 'The verification link is invalid.')
        return redirect('users:login')

def login_view(request):
    # Redirect authenticated users to movies list
    if request.user.is_authenticated:
        return redirect('movies:movie_list')

    error_message = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        logger.info(f"Login attempt for user: {username}")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            # For development and debugging, skip email verification
            if settings.DEBUG:
                login(request, user)
                logger.info(f"User {username} logged in successfully (DEBUG mode - bypassing email verification)")
                next_url = request.POST.get('next') or request.GET.get('next') or 'movies:movie_list'
                return redirect(next_url)

            # Normal flow with email verification check
            try:
                # Server-side verification check - get fresh data from database
                from django.shortcuts import get_object_or_404
                from users.models import Profile

                # Fetch profile directly from database
                profile = get_object_or_404(Profile, user=user)

                # Check if email is verified
                if profile.email_verified:
                    login(request, user)
                    logger.info(f"User {username} logged in successfully")
                    next_url = request.POST.get('next') or request.GET.get('next') or 'movies:movie_list'
                    return redirect(next_url)
                else:
                    error_message = "Please verify your email before logging in. Check your inbox for the verification link."
                    logger.warning(f"Login attempt for user {username} failed: Email not verified")

                    # Try to resend verification email
                    email_sent = False
                    if celery_available and tasks_available:
                        try:
                            # Try to use Celery
                            send_verification_email.delay(user.id)
                            email_sent = True
                        except Exception as e:
                            logger.warning(f"Failed to schedule verification email with Celery: {e}. Using synchronous fallback.")

                    if not email_sent and tasks_available:
                        try:
                            send_verification_email_sync(user.id)
                            email_sent = True
                        except Exception as e:
                            logger.error(f"Failed to send verification email: {e}")

                    if email_sent:
                        messages.info(request, "A new verification email has been sent to your email address.")
            except Exception as e:
                # If any error occurs during profile check, log in the user anyway in DEBUG mode
                if settings.DEBUG:
                    login(request, user)
                    logger.warning(f"Error during profile check: {e}, but logging in user {username} anyway (DEBUG mode)")
                    next_url = request.POST.get('next') or request.GET.get('next') or 'movies:movie_list'
                    return redirect(next_url)

                # In production, show error
                logger.error(f"Error during login for {username}: {e}")
                error_message = "An error occurred during login. Please try again."
        else:
            logger.warning(f"Failed login attempt for user: {username} - Invalid credentials")
            error_message = "Invalid username or password"

    # Add debug information in DEBUG mode
    context = {'error_message': error_message}
    if settings.DEBUG:
        context['debug_info'] = {
            'request_path': request.path,
            'auth_status': request.user.is_authenticated,
        }

    return render(request, 'accounts/login.html', context)

def logout_view(request):
    logout(request)
    return redirect('users:login')

class ProtectedView(LoginRequiredMixin, View):
    login_url = '/users/login/'
    redirect_field_name = 'redirect_to'

    def get(self, request):
        return render(request, 'registration/protected.html')

@login_required(login_url='users:login')
def profile_view(request):
    # Ensure user has a profile
    try:
        profile = request.user.profile
    except:
        # Create a profile if it doesn't exist
        from users.models import UserRole, Profile
        customer_role, _ = UserRole.objects.get_or_create(
            name='customer',
            defaults={'description': 'Regular user who can book tickets'}
        )
        profile = Profile.objects.create(user=request.user, role=customer_role)
    
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('users:profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=profile)

    # Get user's booking history
    from bookings.models import Booking
    from django.utils import timezone

    bookings = Booking.objects.filter(user=request.user).order_by('-booking_time')
    upcoming_bookings = bookings.filter(
        showtime__date__gte=timezone.now().date(),
        status='confirmed'
    )
    past_bookings = bookings.filter(
        showtime__date__lt=timezone.now().date(),
        status='confirmed'
    )

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'upcoming_bookings': upcoming_bookings[:5],  # Limit to 5 most recent
        'past_bookings': past_bookings[:5],  # Limit to 5 most recent
        'total_bookings': bookings.count(),
    }

    # Check if user has a student profile
    if hasattr(request.user, 'profile'):
        context['is_student'] = request.user.profile.is_student

        # Add role-specific context
        if hasattr(request.user.profile, 'role') and request.user.profile.role:
            role_name = request.user.profile.role.name
            context['role'] = role_name

            # Add admin statistics if user is admin
            if role_name == 'admin':
                from django.db.models import Count, Sum
                from django.contrib.auth.models import User

                context['user_count'] = User.objects.count()
                context['booking_count'] = Booking.objects.count()
                context['revenue'] = Booking.objects.filter(status='confirmed').aggregate(Sum('total_price'))['total_price__sum'] or 0

            # Add theater manager context if user is theater manager
            elif role_name == 'theater':
                from bookings.models import Theater
                context['managed_theaters'] = Theater.objects.filter(manager=request.user)

    return render(request, 'users/profile.html', context)

# Helper function to check if user is an admin
def is_admin(user):
    try:
        if not user or not user.is_authenticated:
            return False
        if not hasattr(user, 'profile') or not user.profile:
            return False
        if not hasattr(user.profile, 'role') or not user.profile.role:
            return False
        return user.profile.role.name == 'admin'
    except Exception as e:
        logger.error(f"Error in is_admin check: {e}")
        return False

# Helper function to check if user is a theater manager
def is_theater_manager(user):
    try:
        if not user or not user.is_authenticated:
            return False
        if not hasattr(user, 'profile') or not user.profile:
            return False
        if not hasattr(user.profile, 'role') or not user.profile.role:
            return False
        return user.profile.role.name == 'theater'
    except Exception as e:
        logger.error(f"Error in is_theater_manager check: {e}")
        return False

# Admin views
@login_required(login_url='users:login')
def admin_dashboard(request):
    """Dashboard view for administrators"""
    # Check if user is admin - improved error handling
    try:
        if not hasattr(request.user, 'profile') or not request.user.profile or not request.user.profile.role:
            messages.error(request, "Your user profile is incomplete. Please contact support.")
            return redirect('movies:movie_list')
            
        if request.user.profile.role.name != 'admin':
            messages.error(request, "You don't have permission to access this page")
            return redirect('movies:movie_list')
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        messages.error(request, "An error occurred while verifying your permissions")
        return redirect('movies:movie_list')

    # Get various statistics
    try:
        from django.db.models import Count, Sum
        from bookings.models import Booking
        from movies.models import Movie
        from bookings.models import Theater

        context = {}
        
        # User statistics with error handling
        try:
            user_count = User.objects.count()
            context['user_count'] = user_count
        except Exception as e:
            logger.error(f"Error getting user count: {e}")
            context['user_count'] = 0
            
        # Booking statistics with error handling
        try:
            booking_count = Booking.objects.count()
            confirmed_booking_count = Booking.objects.filter(status='confirmed').count()
            revenue = Booking.objects.filter(status='confirmed').aggregate(Sum('total_price'))['total_price__sum'] or 0
            context.update({
                'booking_count': booking_count,
                'confirmed_booking_count': confirmed_booking_count,
                'revenue': revenue,
            })
        except Exception as e:
            logger.error(f"Error getting booking statistics: {e}")
            context.update({
                'booking_count': 0,
                'confirmed_booking_count': 0,
                'revenue': 0,
            })
            
        # Recent activity with error handling
        try:
            recent_users = User.objects.order_by('-date_joined')[:10]
            recent_bookings = Booking.objects.order_by('-booking_time')[:10]
            context.update({
                'recent_users': recent_users,
                'recent_bookings': recent_bookings,
            })
        except Exception as e:
            logger.error(f"Error getting recent activity: {e}")
            context.update({
                'recent_users': [],
                'recent_bookings': [],
            })
            
        # Popular movies with error handling
        try:
            popular_movies = Movie.objects.annotate(
                booking_count=Count('showtimes__bookings', distinct=True)
            ).order_by('-booking_count')[:10]
            context['popular_movies'] = popular_movies
        except Exception as e:
            logger.error(f"Error getting popular movies: {e}")
            context['popular_movies'] = []
            
        # Theater statistics with error handling
        try:
            theaters = Theater.objects.all()
            context['theaters'] = theaters
        except Exception as e:
            logger.error(f"Error getting theaters: {e}")
            context['theaters'] = []
            
    except Exception as e:
        logger.error(f"Unexpected error in admin dashboard: {e}")
        messages.error(request, "An error occurred while loading the dashboard")
        return redirect('movies:movie_list')
        
    return render(request, 'users/admin_dashboard.html', context)

    return render(request, 'users/admin_dashboard.html', context)

@login_required(login_url='users:login')
def manage_users(request):
    """Admin view for managing users"""
    # Check if user is admin
    if not is_admin(request.user):
        messages.error(request, "You don't have permission to access this page")
        return redirect('movies:movie_list')

    from django.core.paginator import Paginator

    users = User.objects.all().order_by('-date_joined')

    # Pagination
    paginator = Paginator(users, 20)  # 20 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }

    return render(request, 'users/manage_users.html', context)

@login_required(login_url='users:login')
def theater_dashboard(request):
    """Dashboard view for theater managers"""
    # Check if user is theater manager
    if not is_theater_manager(request.user):
        messages.error(request, "You don't have permission to access this page")
        return redirect('movies:movie_list')

    from bookings.models import Theater, Showtime, Booking
    from django.utils import timezone
    import datetime

    # Get theaters managed by this user
    theaters = Theater.objects.filter(manager=request.user)

    if not theaters.exists():
        messages.warning(request, "You don't have any theaters assigned to you yet. Please contact an administrator.")

    # Today's showtimes
    today = timezone.now().date()
    today_showtimes = Showtime.objects.filter(
        theater__in=theaters,
        date=today
    ).order_by('time')

    # Upcoming showtimes for next 7 days
    next_week = today + datetime.timedelta(days=7)
    upcoming_showtimes = Showtime.objects.filter(
        theater__in=theaters,
        date__gt=today,
        date__lte=next_week
    ).order_by('date', 'time')

    # Recent bookings for managed theaters
    recent_bookings = Booking.objects.filter(
        showtime__theater__in=theaters
    ).order_by('-booking_time')[:20]

    context = {
        'theaters': theaters,
        'today_showtimes': today_showtimes,
        'upcoming_showtimes': upcoming_showtimes,
        'recent_bookings': recent_bookings,
    }

    return render(request, 'users/theater_dashboard.html', context)
