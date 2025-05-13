from celery import shared_task
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from bookings.models import Booking
from bookings.ticket_generator import TicketGenerator
from botocore.exceptions import ClientError
import boto3
import logging
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

logger = logging.getLogger(__name__)

ses_client = boto3.client(
    'ses',
    region_name=settings.AWS_SES_REGION_NAME,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
)


@shared_task
def send_booking_confirmation_email(booking_id):
    return _send_email(booking_id, email_type='confirmation')


@shared_task
def send_booking_reminder_email(booking_id):
    return _send_email(booking_id, email_type='reminder')


def _send_email(booking_id, email_type):
    try:
        booking = Booking.objects.select_related('user', 'showtime__movie', 'showtime__theater').get(id=booking_id)
    except Booking.DoesNotExist:
        msg = f"Booking with id {booking_id} does not exist"
        logger.error(msg)
        return msg

    recipient_email = _get_recipient_email(booking)
    subject, text_body, html_body = _render_email_content(booking, email_type)

    attachments = []
    if email_type == 'confirmation':
        pdf_bytes = TicketGenerator.generate_ticket_pdf(booking)
        attachments.append(('ticket.pdf', pdf_bytes, 'application/pdf'))

    try:
        return _send_email_with_ses(subject, recipient_email, text_body, html_body, attachments)
    except ClientError as e:
        logger.warning(f"SES failed: {e}, falling back to Django backend.")
        return _send_email_with_django(subject, recipient_email, text_body, html_body, attachments)


def _get_recipient_email(booking):
    """Use verified email in DEBUG mode for SES restrictions"""
    real_email = booking.user.email
    verified_email = os.environ.get('VERIFIED_EMAIL')

    if settings.DEBUG and verified_email:
        logger.info(f"Overriding real recipient {real_email} with verified {verified_email}")
        return verified_email
    return real_email


def _render_email_content(booking, email_type):
    context = {
        'booking': booking,
        'movie': booking.showtime.movie,
        'site_url': settings.SITE_URL,
        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
    }

    if email_type == 'confirmation':
        subject = f"Booking Confirmation - {booking.showtime.movie.title}"
        text_template = 'bookings/email/booking_confirmation.txt'
        html_template = 'bookings/email/booking_confirmation.html'
    elif email_type == 'reminder':
        subject = f"Reminder: Your Movie - {booking.showtime.movie.title}"
        text_template = 'bookings/email/booking_reminder.txt'
        html_template = 'bookings/email/booking_reminder.html'
    else:
        raise ValueError("Invalid email type")

    text_body = render_to_string(text_template, context)
    html_body = render_to_string(html_template, context)
    return subject, text_body, html_body


def _send_email_with_ses(subject, recipient, text_body, html_body, attachments):
    msg = MIMEMultipart('mixed')
    msg['Subject'] = subject
    msg['From'] = settings.DEFAULT_FROM_EMAIL
    msg['To'] = recipient

    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(text_body, 'plain', 'utf-8'))
    alt.attach(MIMEText(html_body, 'html', 'utf-8'))
    msg.attach(alt)

    for filename, content, mime_type in attachments:
        part = MIMEApplication(content)
        part.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(part)

    response = ses_client.send_raw_email(
        Source=settings.DEFAULT_FROM_EMAIL,
        Destinations=[recipient],
        RawMessage={'Data': msg.as_string()}
    )
    message_id = response.get('MessageId', 'Unknown')
    logger.info(f"Email sent via SES to {recipient} | MessageId: {message_id}")
    return f"Email sent via SES to {recipient} | MessageId: {message_id}"


def _send_email_with_django(subject, recipient, text_body, html_body, attachments):
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    email.attach_alternative(html_body, 'text/html')

    for filename, content, mime_type in attachments:
        email.attach(filename, content, mime_type)

    email.send(fail_silently=False)
    logger.info(f"Email sent via Django backend to {recipient}")
    return f"Email sent via Django backend to {recipient}"
