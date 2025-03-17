from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import Booking
from .ticket_generator import TicketGenerator
import logging
from io import BytesIO
import tempfile
import os
import boto3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from botocore.exceptions import ClientError
import time

logger = logging.getLogger(__name__)

# Create a boto3 SES client for direct email sending
ses_client = boto3.client(
    'ses',
    region_name=settings.AWS_SES_REGION_NAME,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
)

@shared_task
def send_booking_confirmation_email(booking_id):
    """
    Send booking confirmation email with ticket attached via Celery
    """
    return _send_booking_confirmation_email(booking_id)

def send_booking_confirmation_email_sync(booking_id):
    """
    Synchronous version for sending booking confirmation when Celery is unavailable
    """
    return _send_booking_confirmation_email(booking_id)

def _send_booking_confirmation_email(booking_id):
    """
    Common implementation for both async and sync versions
    """
    try:
        logger.info(f"Starting to send booking confirmation email for booking {booking_id}")
        booking = Booking.objects.get(id=booking_id)

        sender_email = settings.DEFAULT_FROM_EMAIL

        recipient_email = booking.user.email
        verified_email = os.environ.get('VERIFIED_EMAIL', '')

        if settings.DEBUG and verified_email:
            logger.info(f"Using verified recipient email {verified_email} instead of {booking.user.email} due to SES restrictions")
            recipient_email = verified_email

        subject = f'Booking Confirmation - {booking.showtime.movie.title}'
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        text_content = f"""
        Booking Confirmation - {booking.showtime.movie.title} - {timestamp}

        Thank you for your booking!

        Movie: {booking.showtime.movie.title}
        Date: {booking.showtime.date}
        Time: {booking.showtime.time}
        Theater: {booking.showtime.theater.name}
        Seats: {booking.get_seats_display()}

        Your booking reference: {booking.booking_reference}

        Please find your ticket attached to this email.
        """

        # Context for HTML template
        context = {
            'booking': booking,
            'movie': booking.showtime.movie,
            'site_url': settings.SITE_URL,
        }
        html_content = render_to_string('bookings/email/booking_confirmation.html', context)

        # Generate PDF ticket - this now returns bytes directly
        logger.info(f"Generating PDF ticket for booking {booking_id}")
        pdf_bytes = TicketGenerator.generate_ticket_pdf(booking)

        # Try sending directly with boto3 to bypass Django email issues
        try:
            # Create a multipart/mixed email message
            msg = MIMEMultipart('mixed')
            msg['Subject'] = subject
            msg['From'] = sender_email
            msg['To'] = recipient_email

            msg_alt = MIMEMultipart('alternative')

            msg_text = MIMEText(text_content, 'plain', 'utf-8')
            msg_alt.attach(msg_text)

            msg_html = MIMEText(html_content, 'html', 'utf-8')
            msg_alt.attach(msg_html)

            msg.attach(msg_alt)

            ''' pdf '''
            att = MIMEApplication(pdf_bytes)
            att.add_header('Content-Disposition', 'attachment', filename='ticket.pdf')
            msg.attach(att)

            # Send raw email with boto3
            response = ses_client.send_raw_email(
                Source=sender_email,
                Destinations=[recipient_email],
                RawMessage={'Data': msg.as_string()}
            )

            message_id = response.get('MessageId', 'Unknown')
            logger.info(f"Successfully sent email directly with boto3, MessageId: {message_id}")
            return f"Booking confirmation email sent to {recipient_email}, MessageId: {message_id}"

        except ClientError as e:
            logger.error(f"Failed to send email with boto3: {str(e)}")
            # Fall back to Django's email backend
            logger.info("Falling back to Django's email backend...")
            return _send_with_django_backend(booking, subject, text_content, html_content, pdf_bytes, recipient_email)

    except Booking.DoesNotExist:
        logger.error(f"Booking with id {booking_id} does not exist")
        return f"Booking with id {booking_id} does not exist"
    except Exception as e:
        logger.error(f"Error sending booking confirmation email: {str(e)}")
        return f"Error sending booking confirmation email: {str(e)}"

def _send_with_django_backend(booking, subject, text_content, html_content, pdf_bytes, recipient_email):
    """Fallback method to send email using Django's email backend"""
    try:
        # Write PDF to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_file.write(pdf_bytes)
        temp_file.close()

        try:
            # Create email with Django
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],
            )

            # Add HTML alternative
            email.attach_alternative(html_content, "text/html")

            # Add PDF attachment
            with open(temp_file.name, 'rb') as f:
                pdf_data = f.read()
                email.attach('ticket.pdf', pdf_data, 'application/pdf')

            # Send the email
            email.send(fail_silently=False)

            logger.info(f"Successfully sent email with Django to {recipient_email}")
            return f"Booking confirmation email sent to {recipient_email} using Django backend"
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {str(e)}")
                pass
    except Exception as e:
        logger.error(f"Django email backend failed: {str(e)}")
        return f"Failed to send email with Django backend: {str(e)}"

@shared_task
def send_booking_reminder_email(booking_id):
    """
    Send reminder email 24 hours before showtime
    """
    return _send_booking_reminder_email(booking_id)

def send_booking_reminder_email_sync(booking_id):
    """
    Synchronous version for sending booking reminders when Celery is unavailable
    """
    return _send_booking_reminder_email(booking_id)

def _send_booking_reminder_email(booking_id):
    """
    Common implementation for both async and sync versions
    """
    try:
        logger.info(f"Starting to send booking reminder email for booking {booking_id}")
        booking = Booking.objects.get(id=booking_id)

        # For Amazon SES where we can only send to verified emails
        sender_email = settings.DEFAULT_FROM_EMAIL

        # Use verified email from environment or fallback to user's email
        recipient_email = booking.user.email
        verified_email = os.environ.get('VERIFIED_EMAIL', '')

        if settings.DEBUG and verified_email:
            logger.info(f"Using verified recipient email {verified_email} instead of {booking.user.email} due to SES restrictions")
            recipient_email = verified_email

        # Create message subject and text body
        subject = f'Reminder: Your Movie - {booking.showtime.movie.title}'
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Plain text content
        text_content = f"""
        Reminder: Your Movie - {booking.showtime.movie.title} - {timestamp}

        This is a reminder for your upcoming movie:

        Movie: {booking.showtime.movie.title}
        Date: {booking.showtime.date}
        Time: {booking.showtime.time}
        Theater: {booking.showtime.theater.name}
        Seats: {booking.get_seats_display()}

        Your booking reference: {booking.booking_reference}
        """

        # Context for HTML template
        context = {
            'booking': booking,
            'movie': booking.showtime.movie,
            'site_url': settings.SITE_URL,
        }
        html_content = render_to_string('bookings/email/booking_reminder.html', context)

        # Try sending directly with boto3
        try:
            # Create a multipart/alternative email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = sender_email
            msg['To'] = recipient_email

            # Attach the plain text part
            msg_text = MIMEText(text_content, 'plain', 'utf-8')
            msg.attach(msg_text)

            # Attach the HTML part
            msg_html = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(msg_html)

            # Send raw email with boto3
            response = ses_client.send_raw_email(
                Source=sender_email,
                Destinations=[recipient_email],
                RawMessage={'Data': msg.as_string()}
            )

            message_id = response.get('MessageId', 'Unknown')
            logger.info(f"Successfully sent reminder email with boto3, MessageId: {message_id}")
            return f"Booking reminder email sent to {recipient_email}, MessageId: {message_id}"

        except ClientError as e:
            logger.error(f"Failed to send reminder email with boto3: {str(e)}")

            # Fall back to Django's email backend
            logger.info("Falling back to Django's email backend for reminder...")
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email]
            )

            # Add HTML alternative
            email.attach_alternative(html_content, "text/html")

            # Send the email
            email.send(fail_silently=False)

            logger.info(f"Successfully sent reminder email with Django to {recipient_email}")
            return f"Booking reminder email sent to {recipient_email} using Django backend"

    except Booking.DoesNotExist:
        logger.error(f"Booking with id {booking_id} does not exist")
        return f"Booking with id {booking_id} does not exist"
    except Exception as e:
        logger.error(f"Error sending booking reminder email: {str(e)}")
        return f"Error sending booking reminder email: {str(e)}"
