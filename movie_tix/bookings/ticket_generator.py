from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
import qrcode
from PIL import Image
import io
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

class TicketGenerator:
    @staticmethod
    def generate_ticket_pdf(booking):
        """Generate a modern PDF ticket for a booking"""
        try:
            # Create a BytesIO buffer for the PDF
            buffer = BytesIO()
            
            # Create the PDF object using ReportLab
            p = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4
            
            # Define colors
            primary_color = colors.HexColor('#ff0040')  # Movie logo color
            secondary_color = colors.HexColor('#141824')  # Dark background
            text_color = colors.black
            border_color = colors.HexColor('#dddddd')
            
            # Create a nice background
            p.setFillColor(colors.white)
            p.rect(0, 0, width, height, fill=1)
            
            # Add header/logo
            p.setFillColor(primary_color)
            p.rect(0.5*inch, height-1.5*inch, width-inch, 0.75*inch, fill=1)
            p.setFillColor(colors.white)
            p.setFont("Helvetica-Bold", 24)
            p.drawString(1*inch, height-1*inch, "MovieTime Ticket")
            
            # Draw main ticket container
            p.setFillColor(colors.white)
            p.setStrokeColor(border_color)
            p.setLineWidth(2)
            p.roundRect(0.5*inch, height-7*inch, width-inch, 5*inch, 10, stroke=1, fill=1)
            
            # Add movie title
            p.setFillColor(primary_color)
            p.setFont("Helvetica-Bold", 18)
            title_text = booking.showtime.movie.title
            # Truncate if too long
            if len(title_text) > 40:
                title_text = title_text[:37] + "..."
            p.drawString(1*inch, height-2.25*inch, title_text)
            
            # Add booking reference in a badge
            p.setFillColor(secondary_color)
            p.roundRect(width-3.5*inch, height-2.4*inch, 2*inch, 0.4*inch, 5, stroke=0, fill=1)
            p.setFillColor(colors.white)
            p.setFont("Helvetica-Bold", 12)
            p.drawString(width-3.3*inch, height-2.15*inch, f"Ref: {booking.booking_reference}")
            
            # Add separator line
            p.setStrokeColor(border_color)
            p.setLineWidth(1)
            p.line(1*inch, height-2.6*inch, width-1*inch, height-2.6*inch)
            
            # Add showtime details with icons
            p.setFillColor(text_color)
            
            # Date
            p.setFont("Helvetica-Bold", 12)
            p.drawString(1*inch, height-3.1*inch, "Date:")
            p.setFont("Helvetica", 12)
            p.drawString(2*inch, height-3.1*inch, f"{booking.showtime.date.strftime('%A, %B %d, %Y')}")
            
            # Time
            p.setFont("Helvetica-Bold", 12)
            p.drawString(1*inch, height-3.5*inch, "Time:")
            p.setFont("Helvetica", 12)
            p.drawString(2*inch, height-3.5*inch, f"{booking.showtime.time.strftime('%I:%M %p')}")
            
            # Theater
            p.setFont("Helvetica-Bold", 12)
            p.drawString(1*inch, height-3.9*inch, "Theater:")
            p.setFont("Helvetica", 12)
            p.drawString(2*inch, height-3.9*inch, f"{booking.showtime.theater.name}")
            
            # Seats
            p.setFont("Helvetica-Bold", 12)
            p.drawString(1*inch, height-4.3*inch, "Seats:")
            p.setFont("Helvetica", 12)
            p.drawString(2*inch, height-4.3*inch, f"{booking.get_seats_display()}")
            
            # Price
            p.setFont("Helvetica-Bold", 12)
            p.drawString(1*inch, height-4.7*inch, "Total Price:")
            p.setFont("Helvetica", 12)
            p.drawString(2*inch, height-4.7*inch, f"${booking.total_price:.2f}")
            
            # Generate QR code and save to temp file using context manager
            qr_img = TicketGenerator._generate_qr_code_image(str(booking.booking_reference))
            
            # Use context manager to ensure temp file cleanup
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as qr_temp_file:
                qr_img.save(qr_temp_file.name)
                qr_temp_file_path = qr_temp_file.name
                
            try:
                # Add QR code to PDF
                p.drawImage(qr_temp_file_path, width-3.5*inch, height-4.7*inch, width=2*inch, height=2*inch)
                
                # Add QR code label
                p.setFillColor(secondary_color)
                p.setFont("Helvetica", 8)
                p.drawCentredString(width-2.5*inch, height-5*inch, "Scan at the theater entrance")
                
                # Add tear-off line (dashed)
                p.setDash([6, 3], 0)
                p.setStrokeColor(border_color)
                p.line(0.5*inch, height-5.25*inch, width-0.5*inch, height-5.25*inch)
                
                # Add footer
                p.setFillColor(text_color)
                p.setFont("Helvetica", 8)
                p.drawString(1*inch, height-5.75*inch, f"Booked by: {booking.user.username}")
                p.drawString(1*inch, height-6*inch, f"Booking Date: {booking.booking_time.strftime('%B %d, %Y, %I:%M %p')}")
                
                p.drawRightString(width-1*inch, height-5.75*inch, "MovieTime - Your ultimate movie experience")
                p.drawRightString(width-1*inch, height-6*inch, "For assistance, contact: support@movietime.com")
                
                # Add note
                p.setFont("Helvetica-Oblique", 8)
                p.drawCentredString(width/2, height-6.5*inch, "Please arrive 15 minutes before showtime. No refunds or exchanges.")
                
                p.showPage()
                p.save()
                
                # Get the bytes value
                pdf_bytes = buffer.getvalue()
                buffer.close()
            finally:
                # Always clean up the temp file
                try:
                    os.unlink(qr_temp_file_path)
                except Exception as e:
                    logger.error(f"Error removing temporary file: {e}")
                
            logger.info(f"Successfully generated PDF ticket of size {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Error in generate_ticket_pdf: {str(e)}")
            # Create a very simple fallback PDF
            return TicketGenerator._generate_fallback_pdf(booking)

    @staticmethod
    def _generate_fallback_pdf(booking):
        """Generate a simple fallback PDF if the main generation fails"""
        try:
            logger.info("Using fallback PDF generation")
            from reportlab.lib.pagesizes import letter
            
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            c.drawString(100, 750, f"Booking Confirmation: {booking.booking_reference}")
            c.drawString(100, 700, f"Movie: {booking.showtime.movie.title}")
            c.drawString(100, 650, f"Date: {booking.showtime.date}")
            c.drawString(100, 600, f"Time: {booking.showtime.time}")
            c.drawString(100, 550, f"Seats: {booking.get_seats_display()}")
            c.save()
            
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            logger.info(f"Successfully generated fallback PDF ticket of size {len(pdf_bytes)} bytes")
            return pdf_bytes
        except Exception as e:
            logger.error(f"Error in fallback PDF generation: {str(e)}")
            # If even the fallback fails, return an empty PDF
            return b'%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000111 00000 n \n\ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF\n'

    @staticmethod
    def _generate_qr_code_image(data):
        """Generate a QR code PIL Image for the given data string"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white")

    @staticmethod
    def generate_qr_code(booking):
        """Generate a QR code as bytes for a booking"""
        img = TicketGenerator._generate_qr_code_image(str(booking.booking_reference))
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()