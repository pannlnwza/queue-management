from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views import generic

from participant.models import Participant, Notification
from manager.models import Queue
from manager.views import logger
from .forms import ReservationForm
from participant.utils.participant_handler import ParticipantHandlerFactory
import time
from django.http import StreamingHttpResponse
import json


# Create your views here.

class HomePageView(generic.TemplateView):
    template_name = 'participant/get_started.html'



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
                {"status": "error", "message": "Notification not found"}, status=404
            )

    return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)


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
            user_participants = Participant.objects.filter(user=self.request.user)
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
                + timedelta(minutes=participant.calculate_estimated_wait_time())
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
    form_class = ReservationForm

    def dispatch(self, request, *args, **kwargs):
        # Retrieve the queue object based on the queue_code from the URL
        self.queue = get_object_or_404(Queue, code=kwargs['queue_code'])
        self.participant_handler = ParticipantHandlerFactory.get_handler(self.queue.category)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        # Add the queue object to the context for rendering
        context = super().get_context_data(**kwargs)
        context['queue'] = self.queue
        return context

    def form_valid(self, form):
        # Create a new participant associated with the queue
        form_data = form.cleaned_data.copy()
        form_data['queue'] = self.queue
        participant = self.participant_handler.create_participant(
            form_data,
        )
        participant.save()
        # self.queue.update_participants_positions()
        messages.success(self.request, f"You have successfully joined {self.queue.name}.")
        return redirect('participant:queue_status', participant.code)

    def form_invalid(self, form):
        # Optional: Log or print errors for debugging
        print(form.errors)
        return super().form_invalid(form)


class QueueStatusView(generic.TemplateView):
    template_name = 'participant/status.html'

    def get_context_data(self, **kwargs):
        """Add the queue and participants context to template."""
        context = super().get_context_data(**kwargs)
        # look for 'participant_code' in the url
        participant_code = kwargs['participant_code']
        # get the participant
        participant = get_object_or_404(Participant ,code=participant_code)
        # get the queue
        queue = participant.queue
        # add in context data
        context['queue'] = queue
        context['participant'] = participant
        # Get the list of all participants in the same queue
        participants_in_queue = queue.participant_set.all().order_by('joined_at')
        context['participants_in_queue'] = participants_in_queue
        return context


import json
import time
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from .models import Participant


def sse_queue_status(request, participant_code):
    """Server-sent Events endpoint to stream the queue status."""

    def event_stream():
        # Get the participant by their code
        while True:
            try:
                participant = get_object_or_404(Participant, code=participant_code)
                queue = participant.queue
                # Prepare the data to send in the SSE stream
                data = {
                    'queue_name': queue.name,
                    'participant': [
                        {
                            'name': participant.name,
                            'position': participant.position,
                            'estimated_wait_time': participant.calculate_estimated_wait_time()
                        }
                    ]
                }
                message = json.dumps(data)

                # Yield the SSE formatted message
                yield f"data: {message}\n\n"
                print(message)

                # Wait for 5 seconds before sending the next update
                time.sleep(5)
            except Exception as e:
                print("Error in event stream:", e)
                break

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')

    # Remove 'Connection: keep-alive' and set necessary headers for SSE
    response['Cache-Control'] = 'no-cache'

    return response
