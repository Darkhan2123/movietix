from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpResponse, JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.core.serializers import serialize
import logging
import importlib.util
import json

from .forms import RegisterForm, UserUpdateForm, ProfileUpdateForm
from users.models import UserRole, Profile
from bookings.models import Booking, Theater

# Check Celery availability
celery_available = importlib.util.find_spec('celery') is not None
try:
    from .tasks import send_verification_email, send_verification_email_sync
    tasks_available = True
except (ImportError, ModuleNotFoundError):
    tasks_available = False
    logging.warning("Celery tasks unavailable, using fallback.")

logger = logging.getLogger(__name__)

def send_verification(user):
    """Send verification email using Celery or fallback."""
    if celery_available and tasks_available:
        try:
            send_verification_email.delay(user.id)
            return True
        except Exception as e:
            logger.warning(f"Celery failed: {e}")

    if tasks_available:
        try:
            send_verification_email_sync(user.id)
            return True
        except Exception as e:
            logger.error(f"Sync email failed: {e}")

    return False

def check_and_create_profile(user):
    """Ensure user has a profile with default role."""
    if not hasattr(user, 'profile'):
        role, _ = UserRole.objects.get_or_create(
            name='customer',
            defaults={'description': 'Regular user who can book tickets'}
        )
        Profile.objects.create(user=user, role=role)

def is_user_role(user, role_name):
    return hasattr(user, 'profile') and getattr(user.profile.role, 'name', None) == role_name

def landing_view(request):
    if request.user.is_authenticated:
        return redirect('movies:movie_list')
    else:
        return JsonResponse({
            'message': 'Welcome to MovieTix API',
            'api_docs': f"{request.build_absolute_uri('/swagger/')}"
        })

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            user = User.objects.create_user(username=username, email=email, password=password)
            check_and_create_profile(user)
            email_sent = send_verification(user)
            if settings.DEBUG:
                user.profile.email_verified = True
                user.profile.save()
                
            return JsonResponse({
                'success': True,
                'message': 'Account created! Check your email.' if email_sent else 'Account created but email failed.',
                'redirect': '/login'
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)
    else:
        return JsonResponse({
            'message': 'Please use POST method to register',
            'fields_required': ['username', 'email', 'password']
        })

def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
        if default_token_generator.check_token(user, token):
            user.profile.email_verified = True
            user.profile.save()
            login(request, user)
            return JsonResponse({
                'success': True,
                'message': 'Email verified!',
                'redirect': '/movies'
            })
    except Exception:
        pass
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid or expired verification link.',
        'redirect': '/login'
    }, status=400)

def login_view(request):
    if request.user.is_authenticated:
        return JsonResponse({
            'success': True,
            'message': 'Already logged in',
            'redirect': '/movies'
        })

    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user:
            if settings.DEBUG or getattr(user.profile, 'email_verified', False):
                login(request, user)
                return JsonResponse({
                    'success': True,
                    'message': 'Login successful',
                    'redirect': request.POST.get('next') or '/movies'
                })
            else:
                send_verification(user)
                return JsonResponse({
                    'success': False,
                    'message': 'Please verify your email. A new email has been sent.'
                }, status=401)
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid username or password.'
            }, status=401)

    return JsonResponse({
        'message': 'Please use POST method to login',
        'fields_required': ['username', 'password']
    })

def logout_view(request):
    logout(request)
    return JsonResponse({
        'success': True,
        'message': 'Logged out successfully'
    })

class ProtectedView(LoginRequiredMixin, View):
    login_url = '/users/login/'
    redirect_field_name = 'redirect_to'
    
    def get(self, request):
        return JsonResponse({'message': 'This is a protected view'})

@login_required(login_url='users:login')
def profile_view(request):
    check_and_create_profile(request.user)
    profile = request.user.profile
    
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            return JsonResponse({
                'success': True,
                'message': 'Profile updated successfully.'
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': {**u_form.errors, **p_form.errors}
            }, status=400)
    
    # For GET requests - return user profile data
    from django.utils import timezone
    bookings = Booking.objects.filter(user=request.user).order_by('-booking_time')
    
    # Prepare bookings data
    upcoming_bookings = list(bookings.filter(showtime__date__gte=timezone.now().date(), status='confirmed')[:5].values())
    past_bookings = list(bookings.filter(showtime__date__lt=timezone.now().date(), status='confirmed')[:5].values())
    
    profile_data = {
        'username': request.user.username,
        'email': request.user.email,
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'is_student': profile.is_student,
        'role': profile.role.name if profile.role else None,
        'profile_picture': request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None,
        'upcoming_bookings': upcoming_bookings,
        'past_bookings': past_bookings,
        'total_bookings': bookings.count(),
    }

    if is_user_role(request.user, 'admin'):
        from django.db.models import Sum
        profile_data.update({
            'user_count': User.objects.count(),
            'booking_count': Booking.objects.count(),
            'revenue': Booking.objects.filter(status='confirmed').aggregate(Sum('total_price'))['total_price__sum'] or 0,
        })
    elif is_user_role(request.user, 'theater'):
        profile_data['managed_theaters'] = list(Theater.objects.filter(manager=request.user).values())

    return JsonResponse(profile_data)

@login_required(login_url='users:login')
def admin_dashboard(request):
    if not is_user_role(request.user, 'admin'):
        return JsonResponse({
            'success': False,
            'message': 'Access denied. Admin role required.',
        }, status=403)

    from django.db.models import Count, Sum
    from movies.models import Movie

    # Prepare data for admin dashboard
    recent_users = list(User.objects.order_by('-date_joined')[:10].values('id', 'username', 'email', 'date_joined'))
    recent_bookings = list(Booking.objects.order_by('-booking_time')[:10].values())
    popular_movies = list(Movie.objects.annotate(booking_count=Count('showtimes__bookings')).order_by('-booking_count')[:10].values('id', 'title', 'booking_count'))
    theaters = list(Theater.objects.all().values())

    data = {
        'user_count': User.objects.count(),
        'booking_count': Booking.objects.count(),
        'confirmed_booking_count': Booking.objects.filter(status='confirmed').count(),
        'revenue': Booking.objects.filter(status='confirmed').aggregate(Sum('total_price'))['total_price__sum'] or 0,
        'recent_users': recent_users,
        'recent_bookings': recent_bookings,
        'popular_movies': popular_movies,
        'theaters': theaters,
    }

    return JsonResponse(data)

@login_required(login_url='users:login')
def manage_users(request):
    if not is_user_role(request.user, 'admin'):
        return JsonResponse({
            'success': False,
            'message': 'Access denied. Admin role required.',
        }, status=403)

    from django.core.paginator import Paginator
    
    users = User.objects.all().order_by('-date_joined')
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    users_data = list(page_obj.object_list.values('id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'is_active'))
    
    # Add profile info to each user
    for user_data in users_data:
        try:
            user = User.objects.get(id=user_data['id'])
            if hasattr(user, 'profile'):
                user_data['role'] = user.profile.role.name if user.profile.role else None
                user_data['is_student'] = user.profile.is_student
                user_data['email_verified'] = user.profile.email_verified
        except (User.DoesNotExist, AttributeError):
            pass
    
    return JsonResponse({
        'users': users_data,
        'total_pages': paginator.num_pages,
        'current_page': page_obj.number,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
    })

@login_required(login_url='users:login')
def theater_dashboard(request):
    if not is_user_role(request.user, 'theater'):
        return JsonResponse({
            'success': False,
            'message': 'Access denied. Theater manager role required.',
        }, status=403)

    from bookings.models import Showtime
    from django.utils import timezone
    import datetime

    theaters = Theater.objects.filter(manager=request.user)
    today = timezone.now().date()
    next_week = today + datetime.timedelta(days=7)

    # Convert querysets to lists of dictionaries for JSON serialization
    theaters_data = list(theaters.values())
    today_showtimes = list(Showtime.objects.filter(theater__in=theaters, date=today).order_by('time').values())
    upcoming_showtimes = list(Showtime.objects.filter(theater__in=theaters, date__gt=today, date__lte=next_week).order_by('date', 'time').values())
    recent_bookings = list(Booking.objects.filter(showtime__theater__in=theaters).order_by('-booking_time')[:20].values())

    # Enrich data with related objects
    for showtime in today_showtimes + upcoming_showtimes:
        showtime_obj = Showtime.objects.get(id=showtime['id'])
        showtime['movie_title'] = showtime_obj.movie.title
        showtime['theater_name'] = showtime_obj.theater.name
    
    for booking in recent_bookings:
        booking_obj = Booking.objects.get(id=booking['id'])
        booking['movie_title'] = booking_obj.showtime.movie.title
        booking['customer_name'] = booking_obj.user.username

    data = {
        'theaters': theaters_data,
        'today_showtimes': today_showtimes,
        'upcoming_showtimes': upcoming_showtimes,
        'recent_bookings': recent_bookings,
        'has_theaters': theaters.exists(),
    }

    if not theaters.exists():
        data['message'] = "No assigned theaters. Contact admin."

    return JsonResponse(data)
#--