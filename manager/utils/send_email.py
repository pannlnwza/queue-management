from django.core.mail import send_mail
from django.conf import settings
from django.core.mail import EmailMessage

def send_notification_email(subject, message, recipient_list):
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=recipient_list,
        fail_silently=False,
    )


def send_html_email(subject, html_message, recipient_list):
    """
    Sends an HTML email to the specified recipients.

    Args:
        subject (str): The subject of the email.
        html_message (str): The HTML content of the email.
        recipient_list (list): List of recipient email addresses.

    Returns:
        None
    """
    email = EmailMessage(
        subject=subject,
        body=html_message,  # Use the HTML message as the email body
        from_email=settings.EMAIL_HOST_USER,
        to=recipient_list,
    )
    email.content_subtype = "html"  # Specify that the content is HTML
    email.send()
