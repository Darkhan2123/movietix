from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Booking
from .email_service import EmailService

@receiver(post_save, sender=Booking)
def send_booking_confirmation(sender, instance, created, **kwargs):
    """Send booking confirmation email when a booking is created and confirmed"""
    if created and instance.status == 'confirmed':
        EmailService.send_booking_confirmation(instance)

def send_booking_reminders():
    """
    Send reminder emails for bookings scheduled for tomorrow.
    This should be called by a scheduled task (e.g., Celery).
    """
    tomorrow = timezone.now().date() + timedelta(days=1)
    bookings = Booking.objects.filter(
        showtime__date=tomorrow,
        status='confirmed'
    )

    for booking in bookings:
        EmailService.send_booking_reminder(booking)
