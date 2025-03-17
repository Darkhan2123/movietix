from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_verification_email(user_id):
    """
    Send verification email to a newly registered user
    """
    return _send_verification_email(user_id)

def send_verification_email_sync(user_id):
    """
    Synchronous version of send_verification_email that can be called directly
    when Celery is unavailable
    """
    return _send_verification_email(user_id)

def _send_verification_email(user_id):
    """
    Common implementation for both sync and async versions
    """
    try:
        user = User.objects.get(id=user_id)

        # Generate token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Build the verification link
        verification_link = f"{settings.SITE_URL}/users/verify/{uid}/{token}/"

        # Render email content
        context = {
            'user': user,
            'verification_link': verification_link,
        }
        html_content = render_to_string('users/email/verify_email.html', context)

        # Send email
        send_mail(
            subject='Verify Your Email - MovieTix',
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content,
            fail_silently=False,
        )

        return f"Verification email sent to {user.email}"
    except User.DoesNotExist:
        return f"User with id {user_id} does not exist"
    except Exception as e:
        logger.error(f"Error sending verification email: {str(e)}")
        return f"Error sending verification email: {str(e)}"
