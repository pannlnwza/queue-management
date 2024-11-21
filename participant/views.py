from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
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
from .models import RestaurantParticipant

# Create your views here.

from django.views import generic
from manager.models import Queue
from django.shortcuts import render


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


@login_required
def mark_notification_as_read(request, notification_id):
    if request.method == "POST":
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.is_read = True  # Adjust according to your model's field
            notification.save()
            return JsonResponse({"status": "success"})
        except Notification.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Notification not found"},
                status=404
            )

    return JsonResponse({"status": "error", "message": "Invalid request"},
                        status=400)


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


# @login_required
# def join_queue(request):
#     """Customer joins queue using their ticket code."""
#
#     queue_code = request.POST.get("queue_code")
#     try:
#         participant_slot = Participant.objects.get(queue_code=queue_code)
#         queue = participant_slot.queue
#         if Participant.objects.filter(user=request.user).exists():
#             messages.error(request, "You're already in a queue.")
#             logger.info(
#                 f"User: {request.user} attempted to join queue: {queue.name} when they're already in one."
#             )
#         elif queue.is_closed:
#             messages.error(request, "The queue is closed.")
#             logger.info(
#                 f"User {request.user.username} attempted to join queue {queue.name} that has been closed."
#             )
#         elif participant_slot.user:
#             messages.error(
#                 request,
#                 "Sorry, this slot is already filled by another participant. Are you sure"
#                 " that you have the right code?",
#             )
#             logger.info(
#                 f"User {request.user.username} attempted to join queue {queue.name}, but the participant slot is "
#                 f"already occupied."
#             )
#         else:
#             participant_slot.insert_user(user=request.user)
#             participant_slot.save()
#             messages.success(
#                 request,
#                 f"You have successfully joined the queue with code {queue_code}.",
#             )
#     except Participant.DoesNotExist:
#         messages.error(request, "Invalid queue code. Please try again.")
#         return redirect("participant:index")
#     return redirect("participant:index")

class IndexView(generic.ListView):
    """
    Display the index page for the user's queues.
    Lists the queues the authenticated user is participating in.

    :param template_name: The name of the template to render.
    :param context_object_name: The name of the context variable to hold the queue list.
    """

    template_name = "participant/index.html"
    context_object_name = "queue_list"

    def get_queryset(self):
        """
        Get the list of queues for the authenticated user.
        :returns: A queryset of queues the user is participating in, or an empty queryset if not authenticated.
        """
        if self.request.user.is_authenticated:
            return Queue.objects.filter(participant__user=self.request.user)
        return Queue.objects.none()

    def get_context_data(self, **kwargs):
        """
        Add additional context data to the template.

        :param kwargs: Additional keyword arguments passed to the method.
        :returns: The updated context dictionary with user's queue positions.
        """
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            user_participants = Participant.objects.filter(
                user=self.request.user)
            queue_positions = {
                participant.queue.id: participant.position
                for participant in user_participants
            }
            estimated_wait_time = {
                participant.queue.id: participant.calculate_estimated_wait_time()
                for participant in user_participants
            }
            active_participants = {
                participant.queue.id: participant.id
                for participant in user_participants
            }
            expected_service_time = {
                participant.queue.id: datetime.now()
                                      + timedelta(
                    minutes=participant.calculate_estimated_wait_time())
                for participant in user_participants
            }
            notification = Notification.objects.filter(
                participant__user=self.request.user
            ).order_by("-created_at")
            context["queue_positions"] = queue_positions
            context["estimated_wait_time"] = estimated_wait_time
            context["expected_service_time"] = expected_service_time
            context["notification"] = notification
            context["active_participants"] = active_participants
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
        # Fetch participant using the `participant_code` passed in the URL
        participant_code = self.kwargs.get('participant_code')
        return get_object_or_404(Participant, code=participant_code)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        participant = self.get_object()
        context['participant'] = participant
        context['queue'] = participant.queue
        check_queue_url = self.request.build_absolute_uri(
            reverse('participant:queue_status', kwargs={'participant_code': participant.code})
        )

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(check_queue_url)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_image = base64.b64encode(buffer.getvalue()).decode()

        context['qr_image'] = qr_image
        return context


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
                queue = get_object_or_404(Participant,
                                          code=participant_code).queue
                handler = CategoryHandlerFactory.get_handler(queue.category)
                participant = handler.get_participant_set(queue.id).get(
                    code=participant_code)

                current_data = handler.get_participant_data(participant)
                if last_data != current_data:
                    # Prepare the data to send in the SSE stream

                    message = json.dumps(current_data)

                    yield f"data: {message}\n\n"
                    last_data = current_data
                time.sleep(5)
            except Exception as e:
                print("Error in event stream:", e)
                break

    response = StreamingHttpResponse(event_stream(),
                                     content_type='text/event-stream')

    # Remove 'Connection: keep-alive' and set necessary headers for SSE
    response['Cache-Control'] = 'no-cache'

    return response


def participant_leave(request, participant_code):
    """Participant chose to leave the queue."""
    try:
        participant = Participant.objects.get(code=participant_code)
    except Participant.DoesNotExist:
        messages.error(request, "Couldn't find the participant in the queue.")
        logger.error(f"Couldn't find participant with {participant_code}")
        return redirect('participant:home')
    queue = participant.queue

    try:
        participant.delete()

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
