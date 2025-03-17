from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .ticket_generator import TicketGenerator
import logging
import importlib.util
import os
from io import BytesIO

logger = logging.getLogger(__name__)

# Check if Celery is available
celery_available = importlib.util.find_spec('celery') is not None

# Try to import tasks, use try-except to handle potential import errors
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
    logger.warning("Failed to import Celery tasks for email sending. Using synchronous fallback.")

class EmailService:
    @staticmethod
    def send_booking_confirmation(booking):
        """
        Send booking confirmation email with ticket attached.
        Will try to use Celery if available, otherwise falls back to synchronous sending.
        """
        if celery_available and tasks_available:
            try:
                # Try to use Celery
                send_booking_confirmation_email.delay(booking.id)
                logger.info(f"Scheduled booking confirmation email for booking {booking.id}")
                return True
            except Exception as e:
                logger.warning(f"Failed to schedule email with Celery: {e}. Using synchronous fallback.")

        # Fallback to synchronous sending
        try:
            if tasks_available:
                # Use the synchronous version from tasks.py
                send_booking_confirmation_email_sync(booking.id)
            else:
                # Direct implementation
                EmailService._send_booking_confirmation_direct(booking)
            return True
        except Exception as e:
            logger.error(f"Failed to send booking confirmation email: {e}")
            return False

    @staticmethod
    def send_booking_reminder(booking):
        """
        Send reminder email 24 hours before showtime.
        Will try to use Celery if available, otherwise falls back to synchronous sending.
        """
        if celery_available and tasks_available:
            try:
                # Try to use Celery
                send_booking_reminder_email.delay(booking.id)
                logger.info(f"Scheduled booking reminder email for booking {booking.id}")
                return True
            except Exception as e:
                logger.warning(f"Failed to schedule reminder with Celery: {e}. Using synchronous fallback.")

        # Fallback to synchronous sending
        try:
            if tasks_available:
                # Use the synchronous version from tasks.py
                send_booking_reminder_email_sync(booking.id)
            else:
                # Direct implementation
                EmailService._send_booking_reminder_direct(booking)
            return True
        except Exception as e:
            logger.error(f"Failed to send booking reminder email: {e}")
            return False

    @staticmethod
    def _send_booking_confirmation_direct(booking):
        """Direct implementation for sending booking confirmation email with ticket attached"""
        try:
            # Validate email
            if not booking.user.email:
                logger.error(f"No email address found for user: {booking.user.username}")
                return False
                
            subject = f'Booking Confirmation - {booking.showtime.movie.title}'

            # Render email content from template
            context = {
                'booking': booking,
                'movie': booking.showtime.movie,
                'site_url': settings.SITE_URL,
            }
            html_content = render_to_string('bookings/email/booking_confirmation.html', context)

            # Generate PDF ticket
            logger.info(f"Generating PDF ticket for booking {booking.id}")
            pdf_data = TicketGenerator.generate_ticket_pdf(booking)
            
            # Make sure we have bytes not BytesIO
            if isinstance(pdf_data, BytesIO):
                logger.warning(f"PDF data is BytesIO, converting to bytes")
                pdf_data = pdf_data.getvalue()
                
            if not isinstance(pdf_data, bytes):
                logger.error(f"PDF data is not bytes, it's {type(pdf_data)}")
                raise ValueError(f"PDF data must be bytes, got {type(pdf_data)}")

            # Plain text version of the email
            text_message = f"""
            Booking Confirmation - {booking.showtime.movie.title}
            
            Thank you for your booking!
            
            Movie: {booking.showtime.movie.title}
            Date: {booking.showtime.date}
            Time: {booking.showtime.time}
            Theater: {booking.showtime.theater.name}
            Seats: {booking.get_seats_display()}
            
            Your booking reference: {booking.booking_reference}
            
            Please find your ticket attached to this email.
            """
            
            # Send email with retry mechanism
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Sending email to {booking.user.email} (attempt {attempt+1})")
                    # For Amazon SES where we can only send to verified emails in sandbox mode
                    # In production, use the actual user's email
                    recipient_email = booking.user.email
                    if settings.DEBUG:
                        # Get verified email from environment or use a default for testing
                        verified_email = os.environ.get('VERIFIED_EMAIL', '')
                        if verified_email:
                            logger.info(f"Using verified recipient email {verified_email} instead of {booking.user.email} due to SES restrictions")
                            recipient_email = verified_email
                    
                    send_mail(
                        subject=subject,
                        message=text_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[recipient_email],
                        html_message=html_content,
                        fail_silently=False,
                        attachments=[
                            ('ticket.pdf', pdf_data, 'application/pdf')
                        ]
                    )
                    logger.info(f"Successfully sent booking confirmation email to {booking.user.email}")
                    return True
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Email sending attempt {attempt+1} failed: {e}. Retrying...")
                    else:
                        logger.error(f"All {max_retries} attempts to send email failed. Last error: {e}")
                        raise
            
            return True
        except Exception as e:
            logger.error(f"Failed to send booking confirmation email: {str(e)}")
            return False

    @staticmethod
    def _send_booking_reminder_direct(booking):
        """Direct implementation for sending reminder email"""
        try:
            # Validate email
            if not booking.user.email:
                logger.error(f"No email address found for user: {booking.user.username}")
                return False
                
            subject = f'Reminder: Your Movie - {booking.showtime.movie.title}'

            context = {
                'booking': booking,
                'movie': booking.showtime.movie,
                'site_url': settings.SITE_URL,
            }
            html_content = render_to_string('bookings/email/booking_reminder.html', context)

            # Plain text message
            text_message = f"""
            Reminder: Your Movie - {booking.showtime.movie.title}
            
            This is a reminder for your upcoming movie:
            
            Movie: {booking.showtime.movie.title}
            Date: {booking.showtime.date}
            Time: {booking.showtime.time}
            Theater: {booking.showtime.theater.name}
            Seats: {booking.get_seats_display()}
            
            Your booking reference: {booking.booking_reference}
            """

            # Send email with retry mechanism
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Sending reminder email to {booking.user.email} (attempt {attempt+1})")
                    # For Amazon SES where we can only send to verified emails in sandbox mode
                    # In production, use the actual user's email
                    recipient_email = booking.user.email
                    if settings.DEBUG:
                        # Get verified email from environment or use a default for testing
                        verified_email = os.environ.get('VERIFIED_EMAIL', '')
                        if verified_email:
                            logger.info(f"Using verified recipient email {verified_email} instead of {booking.user.email} due to SES restrictions")
                            recipient_email = verified_email
                    
                    send_mail(
                        subject=subject,
                        message=text_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[recipient_email],
                        html_message=html_content,
                        fail_silently=False,
                    )
                    logger.info(f"Successfully sent booking reminder email to {booking.user.email}")
                    return True
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Email sending attempt {attempt+1} failed: {e}. Retrying...")
                    else:
                        logger.error(f"All {max_retries} attempts to send email failed. Last error: {e}")
                        raise
            
            return True
        except Exception as e:
            logger.error(f"Failed to send booking reminder email: {str(e)}")
            return False