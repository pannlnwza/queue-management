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
from manager.utils.send_email import generate_participant_qr_code_url, send_email_with_qr


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
            form_data['resource'] = None
            participant = self.handler.create_participant(
                form_data,
            )
            participant.created_by = 'guest'
            print(participant.code)
            participant.qrcode_url = generate_participant_qr_code_url(participant)
            send_email_with_qr(participant, participant.qrcode_url)
            participant.qrcode_email_sent = True
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

        context['qr_image_url'] = participant.qrcode_url
        return context


def welcome(request, queue_code):
    queue = get_object_or_404(Queue, code=queue_code)
    return render(request, 'participant/welcome.html', {'queue': queue})
