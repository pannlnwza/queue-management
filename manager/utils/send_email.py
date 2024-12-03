from io import BytesIO
from django.conf import settings
from django.core.mail import EmailMessage
import qrcode
from django.template.loader import render_to_string
from django.urls import reverse
from manager.utils.aws_s3_storage import upload_to_s3
from django.core.files.base import ContentFile
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives
from django.contrib.sites.models import Site

def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def send_html_email(subject, to_email, template_name, context):
    html_message = render_to_string(template_name, context)
    email = EmailMessage(
        subject=subject,
        body=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    email.content_subtype = "html"
    email.send()


def generate_participant_qr_code_url(participant):
    """
    Generate QR code for the participant, upload to S3, and return the S3 URL.
    """
    try:
        # Generate the QR code binary
        qr_code_binary = generate_qr_code(participant.get_status_link())

        # Create a file object for uploading
        file = ContentFile(qr_code_binary)
        file.name = f"{participant.code}.png"

        # Upload to S3 and return the URL
        return upload_to_s3(file, folder="qrcode")
    except Exception as e:
        raise RuntimeError(f"Error generating QR code: {e}")



def send_email_with_qr(participant, qr_code_url):
    """
    Send an email to the participant with their QR code using an HTML template.
    """
    try:
        # Ensure QR code URL exists
        if not qr_code_url:
            raise ValueError("QR code URL is not available.")

        # Render the HTML email template
        context = {
            'participant': participant,
            'qr_code_image_url': qr_code_url,
        }
        html_message = render_to_string('participant/qrcode_for_mail.html', context)
        plain_message = strip_tags(html_message)  # Fallback plain text version

        # Prepare and send the email
        subject = f"Your Queue Ticket for {participant.queue.name}"
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,  # Plain text version
            from_email="noreply@yourdomain.com",  # Replace with your sender email
            to=[participant.email],
        )
        email.attach_alternative(html_message, "text/html")  # Attach the HTML version
        email.send()

        # Return success
        return True
    except Exception as e:
        raise RuntimeError(f"Error sending QR code email: {e}")
