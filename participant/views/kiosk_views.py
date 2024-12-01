from django.core.files.base import ContentFile
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from participant.models import Participant
from participant.forms import KioskForm
from manager.utils.category_handler import CategoryHandlerFactory
from manager.utils.aws_s3_storage import upload_to_s3
from manager.utils.send_email import generate_qr_code
from django.views import generic
from manager.models import Queue
from django.shortcuts import render
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib import messages


class KioskView(generic.FormView):
    template_name = 'participant/kiosk.html'
    form_class = KioskForm

    def dispatch(self, request, *args, **kwargs):
        self.queue = get_object_or_404(Queue, code=kwargs['queue_code'])
        self.handler = CategoryHandlerFactory.get_handler(self.queue.category)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['queue'] = self.queue
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['queue'] = self.queue
        return context

    def form_valid(self, form):
        try:
            # Check if the queue is closed
            if self.queue.is_queue_closed():
                # Add a message to inform the user
                messages.error(self.request, "This queue is currently closed. Please try again later.")
                return redirect('participant:home')  # Redirect to the home page or another page

            # Process the form and create the participant
            form_data = form.cleaned_data.copy()
            form_data['queue'] = self.queue
            participant = self.handler.create_participant(
                form_data,
            )
            participant.created_by = 'guest'
            participant.save()
            return redirect('participant:qrcode',
                            participant_code=participant.code)
        except Exception as e:
            messages.error(self.request, f"An error occurred: {str(e)}")
            return redirect('participant:welcome', queue_code=self.queue.code)

    def form_invalid(self, form):
        print(form.errors)
        return super().form_invalid(form)


class QRcodeView(generic.DetailView):
    model = Participant
    template_name = 'participant/qrcode.html'

    def get_object(self, queryset=None):
        """
        Override the get_object method to retrieve the participant by `participant_code`
        instead of `pk`.
        """
        participant_code = self.kwargs.get('participant_code')
        return get_object_or_404(Participant, code=participant_code)

    def get_context_data(self, **kwargs):
        """
        Populate the context with the participant, queue, and generated QR code.
        """
        context = super().get_context_data(**kwargs)
        participant = self.get_object()
        context['participant'] = participant
        context['queue'] = participant.queue

        # Generate the QR code URL
        check_queue_url = self.request.build_absolute_uri(
            reverse('participant:queue_status',
                    kwargs={'participant_code': participant.code})
        )

        qr_code_binary = generate_qr_code(check_queue_url)
        file = ContentFile(qr_code_binary)
        file.name = f"{participant.code}.png"

        qr_code_s3_url = upload_to_s3(file, folder="qrcode")
        participant.qrcode_url = qr_code_s3_url
        participant.save()

        context['qr_image_url'] = qr_code_s3_url

        self.send_email_with_qr(participant, qr_code_s3_url, check_queue_url)

        return context

    def send_email_with_qr(self, participant, qr_code_s3_url, check_queue_url):
        """
        Sends an email to the participant with the QR code embedded.
        """
        if not participant.email:
            return  # Skip if the participant doesn't have an email

        # Render the email template
        html_message = render_to_string(
            'participant/qrcode_for_mail.html',
            {
                'participant': participant,
                'qr_code_image_url': qr_code_s3_url,
                'status_link': check_queue_url,
            }
        )

        # Create and send the email
        email = EmailMessage(
            subject=f"Your Queue Ticket for {participant.queue.name}",
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[participant.email],
        )
        email.content_subtype = "html"  # Send as HTML email
        email.send()


def welcome(request, queue_code):
    queue = get_object_or_404(Queue, code=queue_code)
    return render(request, 'participant/welcome.html', {'queue': queue})
