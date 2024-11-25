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
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User
from django.views import generic
from participant.models import Participant, Notification
from manager.views import logger
from .forms import KioskForm
from manager.utils.category_handler import CategoryHandlerFactory
from django.http import StreamingHttpResponse
import json
from manager.utils.send_email import generate_qr_code
from django.views import generic
from manager.models import Queue
from django.shortcuts import render
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.http import StreamingHttpResponse
from asgiref.sync import sync_to_async
import asyncio
import json
import threading

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_queues'] = Queue.objects.all().count()
        active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
        user_ids = [
            session.get_decoded().get('_auth_user_id')
            for session in active_sessions
        ]
        context['active_users'] = User.objects.filter(id__in=user_ids).count()

        return context

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
        qr_code_binary = generate_qr_code(check_queue_url)
        qr_code_base64 = base64.b64encode(qr_code_binary).decode()
        context['qr_image'] = qr_code_base64

        self.send_email_with_qr(participant, qr_code_base64, check_queue_url)

        return context


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


import threading
from queue import Queue as ThreadSafeQueue  # Renamed to ThreadSafeQueue for clarity
from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse
import json
import asyncio



def sse_queue_status(request, participant_code):
    """Server-sent Events endpoint to stream the queue status."""

    def event_stream():
        """Synchronous generator to stream events."""
        while True:
            try:
                message = event_queue.get()
                if message is None:  # Sentinel value to terminate the stream
                    break
                yield f"data: {message}\n\n"
            except Exception as e:
                print("Error in synchronous event stream:", e)
                break

    async def async_event_producer():
        """Asynchronous task to fetch and send data."""
        last_data = None
        while True:
            try:
                # Wrap all sync database or blocking operations in `sync_to_async`
                participant, queue, handler = await fetch_participant_and_queue()

                # Fetch participant data
                participant_data = await sync_to_async(handler.get_participant_data)(participant)

                # Fetch notifications
                notifications = await fetch_notifications(participant)

                # Mark notifications as played
                notification_ids = [notif['id'] for notif in notifications if not notif['played_sound']]
                if notification_ids:
                    await mark_notifications_played(notification_ids)

                participant_data['notification_set'] = notifications

                if last_data != participant_data:
                    message = json.dumps(participant_data)
                    event_queue.put(message)
                    last_data = participant_data

                # await asyncio.sleep(15)
            except Exception as e:
                print("Error in async event producer:", e)
                break
        event_queue.put(None)  # Send sentinel value to stop the stream

    @sync_to_async
    def fetch_participant_and_queue():
        """Fetch participant and queue details synchronously."""
        participant_instance = get_object_or_404(Participant, code=participant_code)
        queue = participant_instance.queue
        handler = CategoryHandlerFactory.get_handler(queue.category)
        participant = handler.get_participant_set(queue_id=queue.id).get(code=participant_code)
        return participant, queue, handler

    @sync_to_async
    def fetch_notifications(participant):
        """Fetch notifications for the participant."""
        notifications = Notification.objects.filter(participant=participant)
        return [
            {
                'message': notif.message,
                'created_at': timezone.localtime(notif.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                'is_read': notif.is_read,
                'played_sound': notif.played_sound,
                'id': notif.id,
            }
            for notif in notifications
        ]

    @sync_to_async
    def mark_notifications_played(notification_ids):
        """Mark notifications as played."""
        Notification.objects.filter(id__in=notification_ids).update(played_sound=True)

    # Set up a thread-safe queue to bridge async and sync contexts
    event_queue = ThreadSafeQueue()

    # Start the async event producer in a separate thread
    producer_thread = threading.Thread(target=lambda: asyncio.run(async_event_producer()))
    producer_thread.start()

    # Return the StreamingHttpResponse that consumes the sync iterator
    return StreamingHttpResponse(event_stream(), content_type="text/event-stream")

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