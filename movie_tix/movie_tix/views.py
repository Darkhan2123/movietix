from django.http import HttpResponse
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.conf import settings
import logging
import os

logger = logging.getLogger(__name__)

def simple_mail(request):
    """Send a test email"""
    send_mail(
        subject="Hello",
        message="This is a test email",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.DEFAULT_FROM_EMAIL],
    )
    return HttpResponse("Test email sent successfully")

def home_view(request):
    """
    Main home view that routes based on authentication status
    """
    if request.user.is_authenticated:
        # Redirect to movie list for authenticated users
        return redirect('movies:movie_list')
    else:
        # Show landing page for anonymous users
        return render(request, 'landing.html')

def debug_view(request):
    """
    Debug view to help diagnose issues with the site
    """
    context = {
        'static_url': settings.STATIC_URL,
        'static_root': getattr(settings, 'STATIC_ROOT', 'Not set'),
        'staticfiles_dirs': settings.STATICFILES_DIRS,
        'media_url': settings.MEDIA_URL,
        'media_root': settings.MEDIA_ROOT,
        'base_template_path': os.path.join(settings.BASE_DIR, 'templates', 'base.html'),
    }
    
    return render(request, 'debug.html', context)