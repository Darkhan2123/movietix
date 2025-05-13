import os
import logging
import importlib.util
from io import BytesIO
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .ticket_generator import TicketGenerator

logger = logging.getLogger(__name__)

# Check for Celery
celery_available = importlib.util.find_spec('celery') is not None
try:
    from .tasks import (
        send_booking_confirmation_email,
        send_booking_reminder_email,
        send_booking_confirmation_email_sync,
        send_booking_reminder_email_sync
    )
    tasks_available = True
except (ImportError, ModuleNotFoundError):
    tasks_available = False
    logger.warning("Failed to import Celery tasks for email. Using sync fallback.")


class EmailService:
    @staticmethod
    def send_booking_confirmation(booking) -> bool:
        if celery_available and tasks_available:
            try:
                send_booking_confirmation_email.delay(booking.id)
                logger.info(f"Scheduled confirmation email for booking {booking.id}")
                return True
            except Exception as e:
                logger.warning(f"Celery scheduling failed: {e}. Falling back to sync.")

        try:
            if tasks_available:
                send_booking_confirmation_email_sync(booking.id)
            else:
                EmailService._send_booking_confirmation_direct(booking)
            return True
        except Exception as e:
            logger.error(f"Failed to send confirmation email: {e}")
            return False

    @staticmethod
    def send_booking_reminder(booking) -> bool:
        if celery_available and tasks_available:
            try:
                send_booking_reminder_email.delay(booking.id)
                logger.info(f"Scheduled reminder email for booking {booking.id}")
                return True
            except Exception as e:
                logger.warning(f"Celery scheduling failed: {e}. Falling back to sync.")

        try:
            if tasks_available:
                send_booking_reminder_email_sync(booking.id)
            else:
                EmailService._send_booking_reminder_direct(booking)
            return True
        except Exception as e:
            logger.error(f"Failed to send reminder email: {e}")
            return False

    @staticmethod
    def _send_email_with_retry(subject, text_message, html_content, recipient_email, attachments=None) -> bool:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Sending email to {recipient_email} (attempt {attempt + 1})")
                send_mail(
                    subject=subject,
                    message=text_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient_email],
                    html_message=html_content,
                    fail_silently=False,
                    attachments=attachments or []
                )
                logger.info(f"Email sent successfully to {recipient_email}")
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Email attempt {attempt + 1} failed: {e}. Retrying...")
                else:
                    logger.error(f"All attempts to send email failed: {e}")
                    raise
        return False

    @staticmethod
    def _get_recipient_email(user_email: str) -> str:
        if settings.DEBUG:
            return os.environ.get('VERIFIED_EMAIL', user_email)
        return user_email

    @staticmethod
    def _send_booking_confirmation_direct(booking) -> bool:
        if not booking.user.email:
            logger.error(f"No email for user {booking.user.username}")
            return False

        context = {'booking': booking, 'movie': booking.showtime.movie, 'site_url': settings.SITE_URL}
        subject = f"Booking Confirmation - {booking.showtime.movie.title}"
        html_content = render_to_string('bookings/email/booking_confirmation.html', context)
        text_message = render_to_string('bookings/email/booking_confirmation.txt', context)

        pdf_data = TicketGenerator.generate_ticket_pdf(booking)
        if isinstance(pdf_data, BytesIO):
            pdf_data = pdf_data.getvalue()
        if not isinstance(pdf_data, bytes):
            raise ValueError(f"Expected PDF data as bytes, got {type(pdf_data)}")

        recipient = EmailService._get_recipient_email(booking.user.email)
        return EmailService._send_email_with_retry(
            subject=subject,
            text_message=text_message,
            html_content=html_content,
            recipient_email=recipient,
            attachments=[('ticket.pdf', pdf_data, 'application/pdf')]
        )

    @staticmethod
    def _send_booking_reminder_direct(booking) -> bool:
        if not booking.user.email:
            logger.error(f"No email for user {booking.user.username}")
            return False

        context = {'booking': booking, 'movie': booking.showtime.movie, 'site_url': settings.SITE_URL}
        subject = f"Reminder: Your Movie - {booking.showtime.movie.title}"
        html_content = render_to_string('bookings/email/booking_reminder.html', context)
        text_message = render_to_string('bookings/email/booking_reminder.txt', context)

        recipient = EmailService._get_recipient_email(booking.user.email)
        return EmailService._send_email_with_retry(
            subject=subject,
            text_message=text_message,
            html_content=html_content,
            recipient_email=recipient
        )
