from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views import generic

from participant.models import Participant, Notification
from manager.models import Queue
from manager.views import logger
from .forms import KioskForm
from manager.utils.category_handler import CategoryHandlerFactory
import time
from django.http import StreamingHttpResponse
import json

# Create your views here.


from django.views import generic
from manager.models import Queue
from django.shortcuts import render
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from manager.utils.send_email import send_html_email
from django.conf import settings
from django.core.files.base import ContentFile
from django.views.decorators.http import require_POST
from django.utils import timezone

class HomePageView(generic.TemplateView):
    template_name = 'participant/get_started.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categories = ['restaurant', 'general', 'hospital', 'bank']
        user_lat = self.request.session.get('user_lat', None)
        user_lon = self.request.session.get('user_lon', None)
        if user_lat and user_lon:
            try:
                user_lat = float(user_lat)
                user_lon = float(user_lon)
                context['nearby_queues'] = Queue.get_nearby_queues(user_lat, user_lon)
                context['num_nearby_queues'] = len(Queue.get_nearby_queues(user_lat, user_lon))

                for category in categories:
                    category_featured_queues = Queue.get_top_featured_queues(
                        category=category)
                    context[
                        f'{category}_featured_queues'] = category_featured_queues
            except ValueError:
                context['error'] = "Invalid latitude or longitude provided."
        else:
            context['error'] = "Location not provided. Please enable location services."
        return context



@require_POST
def mark_notification_as_read(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id)
        notification.is_read = True
        notification.save()
        return JsonResponse({"status": "success"})
    except Notification.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Notification not found"},
            status=404
        )
    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": str(e)},
            status=500
        )


class BaseQueueView(generic.ListView):
    model = Queue
    template_name = "participant/list_queues.html"
    context_object_name = "queues"
    queue_category = None

    def get_queryset(self):
        return Queue.objects.filter(category=self.queue_category)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["queue_type"] = self.queue_category.capitalize()
        context["queues"] = self.get_queryset()
        return context


class RestaurantQueueView(BaseQueueView):
    queue_category = "restaurant"


class GeneralQueueView(BaseQueueView):
    queue_category = "general"


class HospitalQueueView(BaseQueueView):
    queue_category = "hospital"


class BankQueueView(BaseQueueView):
    queue_category = "bank"


class ServiceCenterQueueView(BaseQueueView):
    queue_category = "service center"


class BrowseQueueView(generic.ListView):
    model = Queue
    template_name = "participant/browse_queue.html"


def welcome(request, queue_code):
    queue = get_object_or_404(Queue, code=queue_code)
    return render(request, 'participant/welcome.html', {'queue': queue})


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
        form_data = form.cleaned_data.copy()
        form_data['queue'] = self.queue
        participant = self.handler.create_participant(
            form_data,
        )
        participant.created_by = 'guest'
        participant.save()
        return redirect('participant:qrcode', participant_code=participant.code)

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
            reverse('participant:queue_status', kwargs={'participant_code': participant.code})
        )

        # Generate and save QR code
        qr_code_binary = self.generate_qr_code(check_queue_url)
        qr_code_base64 = base64.b64encode(qr_code_binary).decode()
        context['qr_image'] = qr_code_base64

        # Send email with QR code if participant has an email
        self.send_email_with_qr(participant, qr_code_base64, check_queue_url)

        return context

    @staticmethod
    def generate_qr_code(data):
        """
        Generate a QR code as binary data.
        """
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    def send_email_with_qr(self, participant, qr_code_base64, check_queue_url):
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
                'qr_code_image_url': f"data:image/png;base64,{qr_code_base64}",
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


class QueueStatusView(generic.TemplateView):
    template_name = 'participant/status.html'

    def get_context_data(self, **kwargs):
        """Add the queue and participants context to template."""
        context = super().get_context_data(**kwargs)
        # look for 'participant_code' in the url
        participant_code = kwargs['participant_code']
        # get the participant
        participant = get_object_or_404(Participant, code=participant_code)
        # get the queue
        queue = participant.queue
        # add in context data
        context['queue'] = queue
        context['participant'] = participant
        # Get the list of all participants in the same queue
        participants_in_queue = queue.participant_set.all().order_by(
            'joined_at')
        context['participants_in_queue'] = participants_in_queue
        return context


def sse_queue_status(request, participant_code):
    """Server-sent Events endpoint to stream the queue status."""

    def event_stream():
        last_data = None
        while True:
            try:
                # Get the queue and participant details
                queue = get_object_or_404(Participant, code=participant_code).queue
                handler = CategoryHandlerFactory.get_handler(queue.category)
                participant = handler.get_participant_set(queue.id).get(code=participant_code)

                # Fetch participant data
                current_data = handler.get_participant_data(participant)

                # Fetch notifications for the participant
                notification_set = Notification.objects.filter(participant=participant)
                notification_list = []

                for notification in notification_set:
                    # Add notification details to the list
                    notification_list.append({
                        'message': notification.message,
                        'created_at': timezone.localtime(notification.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                        'is_read': notification.is_read,
                        'played_sound': notification.played_sound,
                        'id': notification.id,
                    })

                    # If sound hasn't been played yet, mark it as played
                    if not notification.played_sound:
                        notification.played_sound = True
                        notification.save()

                # Add the notifications to the current data
                current_data['notification_set'] = notification_list

                if last_data != current_data:
                    # Prepare the data to send in the SSE stream
                    message = json.dumps(current_data)
                    yield f"data: {message}\n\n"
                    last_data = current_data

                time.sleep(5)
            except Exception as e:
                print("Error in event stream:", e)
                break

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response



def participant_leave(request, participant_code):
    """Participant choose to leave the queue."""
    try:
        participant = Participant.objects.get(code=participant_code)
    except Participant.DoesNotExist:
        messages.error(request, "Couldn't find the participant in the queue.")
        logger.error(f"Couldn't find participant with {participant_code}")
        return redirect('participant:home')
    queue = participant.queue

    try:
        participant.state = 'cancelled'
        participant.save()
        messages.success(request,
                         f"We are sorry to see you leave {participant.name}. See you next time!")
        logger.info(
            f"Participant {participant.name} successfully left queue: {queue.name}.")
    except Exception as e:
        messages.error(request, f"Error removing participant: {e}")
        logger.error(
            f"Failed to delete participant {participant_code} from queue: {queue.name} code: {queue.code} ")
    return redirect('participant:welcome', queue_code=queue.code)

def set_location(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        lat = data.get('lat')
        lon = data.get('lon')
        if lat and lon:
            request.session['user_lat'] = lat
            request.session['user_lon'] = lon
            print(f"Saved to session: Lat = {lat}, Lon = {lon}")
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'failed'}, status=400)