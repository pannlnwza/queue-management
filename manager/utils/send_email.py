from io import BytesIO
from django.conf import settings
from django.core.mail import EmailMessage
import qrcode
from django.template.loader import render_to_string
from manager.utils.aws_s3_storage import upload_to_s3
from django.core.files.base import ContentFile
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives

def generate_qr_code(data):
    """
    Generates a QR code image for the given data.

    :param data: The data to encode into the QR code.
    :return: The binary content of the QR code image in PNG format.
    """
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def send_html_email(subject, to_email, template_name, context):
    """
    Sends an HTML email with the provided subject, template, and context.

    :param subject: The subject of the email.
    :param to_email: The recipient's email address.
    :param template_name: The name of the email template to use.
    :param context: The context dictionary to render the template.
    """
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
    Generates a QR code for a participant, uploads it to S3, and returns the S3 URL.

    :param participant: The participant for whom the QR code is being generated.
    :return: The URL of the uploaded QR code image on S3.
    :raises RuntimeError: If there's an error generating or uploading the QR code.
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
    Sends an email to the participant with their QR code attached.

    :param participant: The participant to send the email to.
    :param qr_code_url: The URL of the QR code image to include in the email.
    :return: True if the email was sent successfully.
    :raises RuntimeError: If there's an error sending the email.
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
