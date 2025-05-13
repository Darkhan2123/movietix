from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
import qrcode
from PIL import Image
import tempfile
import os
import logging

logger = logging.getLogger(__name__)


class TicketGenerator:
    PRIMARY_COLOR = colors.HexColor('#ff0040')
    SECONDARY_COLOR = colors.HexColor('#141824')
    TEXT_COLOR = colors.black
    BORDER_COLOR = colors.HexColor('#dddddd')

    @classmethod
    def generate_ticket_pdf(cls, booking):
        """Main method to generate a styled ticket as PDF."""
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        try:
            cls._draw_background(p, width, height)
            cls._draw_header(p, width, height)
            cls._draw_ticket_body(p, booking, width, height)

            # QR Code
            qr_img = cls._generate_qr_code_image(str(booking.booking_reference))
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                qr_img.save(temp_file.name)
                qr_path = temp_file.name

            cls._draw_qr_code(p, qr_path, width, height)
            os.unlink(qr_path)

            cls._draw_footer(p, booking, width, height)

            p.showPage()
            p.save()
            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Error generating ticket: {e}")
            return cls._generate_fallback_pdf(booking)
        finally:
            buffer.close()

    @classmethod
    def _draw_background(cls, p, width, height):
        p.setFillColor(colors.white)
        p.rect(0, 0, width, height, fill=1)

    @classmethod
    def _draw_header(cls, p, width, height):
        p.setFillColor(cls.PRIMARY_COLOR)
        p.rect(0.5 * inch, height - 1.5 * inch, width - inch, 0.75 * inch, fill=1)
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 24)
        p.drawString(1 * inch, height - 1 * inch, "MovieTime Ticket")

    @classmethod
    def _draw_ticket_body(cls, p, booking, width, height):
        p.setFillColor(colors.white)
        p.setStrokeColor(cls.BORDER_COLOR)
        p.setLineWidth(2)
        p.roundRect(0.5 * inch, height - 7 * inch, width - inch, 5 * inch, 10, stroke=1, fill=1)

        # Movie Title
        p.setFillColor(cls.PRIMARY_COLOR)
        p.setFont("Helvetica-Bold", 18)
        title = booking.showtime.movie.title
        title = (title[:37] + "...") if len(title) > 40 else title
        p.drawString(1 * inch, height - 2.25 * inch, title)

        # Booking Reference
        p.setFillColor(cls.SECONDARY_COLOR)
        p.roundRect(width - 3.5 * inch, height - 2.4 * inch, 2 * inch, 0.4 * inch, 5, fill=1)
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(width - 3.3 * inch, height - 2.15 * inch, f"Ref: {booking.booking_reference}")

        # Separator
        p.setStrokeColor(cls.BORDER_COLOR)
        p.setLineWidth(1)
        p.line(1 * inch, height - 2.6 * inch, width - 1 * inch, height - 2.6 * inch)

        # Details
        cls._draw_label_value(p, "Date:", booking.showtime.date.strftime('%A, %B %d, %Y'), height - 3.1 * inch)
        cls._draw_label_value(p, "Time:", booking.showtime.time.strftime('%I:%M %p'), height - 3.5 * inch)
        cls._draw_label_value(p, "Theater:", booking.showtime.theater.name, height - 3.9 * inch)
        cls._draw_label_value(p, "Seats:", booking.get_seats_display(), height - 4.3 * inch)
        cls._draw_label_value(p, "Total Price:", f"${booking.total_price:.2f}", height - 4.7 * inch)

    @classmethod
    def _draw_label_value(cls, p, label, value, y):
        p.setFont("Helvetica-Bold", 12)
        p.setFillColor(cls.TEXT_COLOR)
        p.drawString(1 * inch, y, label)
        p.setFont("Helvetica", 12)
        p.drawString(2 * inch, y, value)

    @classmethod
    def _draw_qr_code(cls, p, qr_path, width, height):
        p.drawImage(qr_path, width - 3.5 * inch, height - 4.7 * inch, width=2 * inch, height=2 * inch)
        p.setFillColor(cls.SECONDARY_COLOR)
        p.setFont("Helvetica", 8)
        p.drawCentredString(width - 2.5 * inch, height - 5 * inch, "Scan at the theater entrance")

        # Tear-off line
        p.setDash([6, 3], 0)
        p.setStrokeColor(cls.BORDER_COLOR)
        p.line(0.5 * inch, height - 5.25 * inch, width - 0.5 * inch, height - 5.25 * inch)

    @classmethod
    def _draw_footer(cls, p, booking, width, height):
        p.setFont("Helvetica", 8)
        p.setFillColor(cls.TEXT_COLOR)
        p.drawString(1 * inch, height - 5.75 * inch, f"Booked by: {booking.user.username}")
        p.drawString(1 * inch, height - 6 * inch, f"Booking Date: {booking.booking_time.strftime('%B %d, %Y, %I:%M %p')}")
        p.drawRightString(width - 1 * inch, height - 5.75 * inch, "MovieTime - Your ultimate movie experience")
        p.drawRightString(width - 1 * inch, height - 6 * inch, "For assistance, contact: support@movietime.com")
        p.setFont("Helvetica-Oblique", 8)
        p.drawCentredString(width / 2, height - 6.5 * inch, "Please arrive 15 minutes before showtime. No refunds or exchanges.")

    @staticmethod
    def _generate_qr_code_image(data):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4
        )
        qr.add_data(data)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white")

    @staticmethod
    def generate_qr_code(booking):
        """Return QR code PNG bytes for use elsewhere (e.g., email)."""
        img = TicketGenerator._generate_qr_code_image(str(booking.booking_reference))
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    @staticmethod
    def _generate_fallback_pdf(booking):
        """Fallback minimal PDF in case of generation failure."""
        try:
            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            y = 750
            step = 50
            p.drawString(100, y, f"Booking Confirmation: {booking.booking_reference}")
            p.drawString(100, y - step, f"Movie: {booking.showtime.movie.title}")
            p.drawString(100, y - 2 * step, f"Date: {booking.showtime.date}")
            p.drawString(100, y - 3 * step, f"Time: {booking.showtime.time}")
            p.drawString(100, y - 4 * step, f"Seats: {booking.get_seats_display()}")
            p.save()
            return buffer.getvalue()
        except Exception as e:
            logger.error(f"Fallback PDF generation failed: {e}")
            return b"%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n..."