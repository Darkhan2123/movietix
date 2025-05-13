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
from django.http import HttpResponse
from django.core.mail import send_mail
from django.conf import settings
import logging
import importlib.util

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
    return redirect('movies:movie_list') if request.user.is_authenticated else render(request, 'landing.html')

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(**form.cleaned_data)
            check_and_create_profile(user)
            email_sent = send_verification(user)
            if settings.DEBUG:
                user.profile.email_verified = True
                user.profile.save()
            messages.success(request, 'Account created! Check your email.' if email_sent else 'Account created but email failed.')
            return redirect('users:login')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})

def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
        if default_token_generator.check_token(user, token):
            user.profile.email_verified = True
            user.profile.save()
            login(request, user)
            messages.success(request, 'Email verified!')
            return redirect('movies:movie_list')
    except Exception:
        pass
    messages.error(request, 'Invalid or expired verification link.')
    return redirect('users:login')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('movies:movie_list')

    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user:
            if settings.DEBUG or getattr(user.profile, 'email_verified', False):
                login(request, user)
                return redirect(request.POST.get('next') or 'movies:movie_list')
            else:
                send_verification(user)
                messages.warning(request, 'Please verify your email. A new email has been sent.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')

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
    check_and_create_profile(request.user)
    profile = request.user.profile
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Profile updated.')
            return redirect('users:profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=profile)

    from django.utils import timezone
    bookings = Booking.objects.filter(user=request.user).order_by('-booking_time')
    context = {
        'u_form': u_form,
        'p_form': p_form,
        'upcoming_bookings': bookings.filter(showtime__date__gte=timezone.now().date(), status='confirmed')[:5],
        'past_bookings': bookings.filter(showtime__date__lt=timezone.now().date(), status='confirmed')[:5],
        'total_bookings': bookings.count(),
        'is_student': profile.is_student,
        'role': profile.role.name if profile.role else None,
    }

    if is_user_role(request.user, 'admin'):
        from django.db.models import Sum
        context.update({
            'user_count': User.objects.count(),
            'booking_count': Booking.objects.count(),
            'revenue': Booking.objects.filter(status='confirmed').aggregate(Sum('total_price'))['total_price__sum'] or 0,
        })
    elif is_user_role(request.user, 'theater'):
        context['managed_theaters'] = Theater.objects.filter(manager=request.user)

    return render(request, 'users/profile.html', context)

@login_required(login_url='users:login')
def admin_dashboard(request):
    if not is_user_role(request.user, 'admin'):
        messages.error(request, "Access denied.")
        return redirect('movies:movie_list')

    from django.db.models import Count, Sum
    from movies.models import Movie

    context = {
        'user_count': User.objects.count(),
        'booking_count': Booking.objects.count(),
        'confirmed_booking_count': Booking.objects.filter(status='confirmed').count(),
        'revenue': Booking.objects.filter(status='confirmed').aggregate(Sum('total_price'))['total_price__sum'] or 0,
        'recent_users': User.objects.order_by('-date_joined')[:10],
        'recent_bookings': Booking.objects.order_by('-booking_time')[:10],
        'popular_movies': Movie.objects.annotate(booking_count=Count('showtimes__bookings')).order_by('-booking_count')[:10],
        'theaters': Theater.objects.all(),
    }

    return render(request, 'users/admin_dashboard.html', context)

@login_required(login_url='users:login')
def manage_users(request):
    if not is_user_role(request.user, 'admin'):
        messages.error(request, "Access denied.")
        return redirect('movies:movie_list')

    from django.core.paginator import Paginator
    users = User.objects.all().order_by('-date_joined')
    paginator = Paginator(users, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'users/manage_users.html', {'page_obj': page_obj})

@login_required(login_url='users:login')
def theater_dashboard(request):
    if not is_user_role(request.user, 'theater'):
        messages.error(request, "Access denied.")
        return redirect('movies:movie_list')

    from bookings.models import Showtime
    from django.utils import timezone
    import datetime

    theaters = Theater.objects.filter(manager=request.user)
    today = timezone.now().date()
    next_week = today + datetime.timedelta(days=7)

    context = {
        'theaters': theaters,
        'today_showtimes': Showtime.objects.filter(theater__in=theaters, date=today).order_by('time'),
        'upcoming_showtimes': Showtime.objects.filter(theater__in=theaters, date__gt=today, date__lte=next_week).order_by('date', 'time'),
        'recent_bookings': Booking.objects.filter(showtime__theater__in=theaters).order_by('-booking_time')[:20],
    }

    if not theaters.exists():
        messages.warning(request, "No assigned theaters. Contact admin.")

    return render(request, 'users/theater_dashboard.html', context)
#--